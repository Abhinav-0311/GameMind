"""Commit reservations before HTTP; fail closed if the ledger is unavailable."""
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.design_agent import DesignAgentRun
from app.models.gemini_usage import GeminiDailyUsage
from app.design_agent.llm_provider import NvidiaProviderError

PACIFIC = ZoneInfo("America/Los_Angeles")


def limit_error(message, code):
    return NvidiaProviderError(message, code=code, attempts=0,
        diagnostics={"degraded": True, "stop_run": True})


class SlidingWindow:
    """One shared process window per model, not one window per provider/run."""
    def __init__(self, *, monotonic=time.monotonic, sleep=time.sleep):
        self.monotonic, self.sleep = monotonic, sleep
        self.windows, self.lock = defaultdict(deque), Lock()

    def reserve(self, model, rpm, max_wait):
        deadline = self.monotonic() + max_wait
        while True:
            with self.lock:
                now = self.monotonic()
                window = self.windows[model]
                while window and window[0] <= now - 60:
                    window.popleft()
                if len(window) < rpm:
                    window.append(now)
                    return
                delay = window[0] + 60 - now
                if now + delay > deadline:
                    raise limit_error(f"Gemini RPM wait for '{model}' exceeds the configured bound; run degraded.", "rpm_wait_exceeded")
            self.sleep(delay)


process_window = SlidingWindow()


class GeminiBudget:
    def __init__(self, settings, *, session_factory=SessionLocal,
                 clock=lambda: datetime.now(timezone.utc), window=None):
        self.settings, self.session_factory, self.clock = settings, session_factory, clock
        self.window = window if window is not None else process_window
        self.limits = {}
        for model, rpm, rpd in (
            (settings.GEMINI_DEV_MODEL.strip(), settings.GEMINI_DEV_RPM, settings.GEMINI_DEV_RPD),
            (settings.GEMINI_SHOWCASE_MODEL.strip(), settings.GEMINI_SHOWCASE_RPM, settings.GEMINI_SHOWCASE_RPD),
        ):
            if model:
                previous = self.limits.get(model, (rpm, rpd))
                self.limits[model] = (min(rpm, previous[0]), min(rpd, previous[1]))

    def day(self):
        return self.clock().astimezone(PACIFIC).date()

    def reserve(self, model, run_id=None):
        rpm, rpd = self.limits[model]
        try:
            # Fast refusal avoids waiting for RPM on a model already exhausted.
            with self.session_factory() as db:
                row = db.get(GeminiDailyUsage, (model, self.day()))
                if row is not None and (row.exhausted or row.requests >= rpd):
                    raise limit_error(f"Gemini daily budget for '{model}' is exhausted; no request sent.", "daily_budget_exhausted")
            self.window.reserve(model, rpm, self.settings.GEMINI_RPM_MAX_WAIT_SECONDS)
            # Separate committed transaction: workflow rollback/crash must not refund quota.
            with self.session_factory.begin() as db:
                if run_id is not None:
                    run = db.get(DesignAgentRun, run_id, with_for_update=True)
                    if run is None:
                        raise limit_error("Gemini run budget record is missing; no request sent.", "budget_unavailable")
                    if run.gemini_request_count >= self.settings.GEMINI_MAX_REQUESTS_PER_RUN:
                        raise limit_error("Gemini per-run request limit reached; run stopped degraded.", "run_request_limit")
                    run.gemini_request_count += 1
                statement = insert(GeminiDailyUsage).values(model_id=model, pacific_day=self.day(), requests=1)
                statement = statement.on_conflict_do_update(
                    index_elements=[GeminiDailyUsage.model_id, GeminiDailyUsage.pacific_day],
                    set_={"requests": GeminiDailyUsage.requests + 1},
                    where=(GeminiDailyUsage.requests < rpd) & ~GeminiDailyUsage.exhausted,
                ).returning(GeminiDailyUsage.requests)
                if db.execute(statement).scalar_one_or_none() is None:
                    raise limit_error(f"Gemini daily budget for '{model}' is exhausted; no request sent.", "daily_budget_exhausted")
        except SQLAlchemyError:
            raise limit_error("Gemini quota database unavailable; no request sent. Apply migrations and check database access.", "budget_unavailable") from None

    def exhaust(self, model):
        try:
            with self.session_factory.begin() as db:
                db.execute(insert(GeminiDailyUsage).values(model_id=model, pacific_day=self.day(), requests=0, exhausted=True)
                    .on_conflict_do_update(index_elements=[GeminiDailyUsage.model_id, GeminiDailyUsage.pacific_day],
                        set_={"exhausted": True}))
        except SQLAlchemyError:
            raise limit_error("Gemini exhaustion could not be persisted; run stopped degraded.", "budget_unavailable") from None

    def usage(self):
        day = self.day()
        try:
            with self.session_factory() as db:
                rows = {row.model_id: row for row in db.scalars(select(GeminiDailyUsage).where(GeminiDailyUsage.pacific_day == day))}
                result = []
                for model in sorted(self.limits.keys() | rows.keys()):
                    row, (rpm, rpd) = rows.get(model), self.limits.get(model, (None, None))
                    used, exhausted = (row.requests, row.exhausted) if row else (0, False)
                    result.append({"model": model, "pacific_day": day.isoformat(), "requests": used,
                        "rpm": rpm, "rpd": rpd, "remaining": (0 if exhausted else max(0, rpd - used)) if rpd is not None else None,
                        "exhausted": exhausted})
                return result
        except SQLAlchemyError:
            raise limit_error("Gemini quota database unavailable; check migrations and database access.", "budget_unavailable") from None

    def preflight(self, models):
        estimate = self.settings.GEMINI_RUN_BUDGET_ESTIMATE
        for row in self.usage():
            if row["model"] in models and (row["exhausted"] or row["remaining"] < estimate):
                raise limit_error(f"Gemini run refused: '{row['model']}' has {row['remaining']} daily requests remaining"
                    f"{' (marked exhausted)' if row['exhausted'] else ''}; at least {estimate} required.", "daily_budget_preflight")
