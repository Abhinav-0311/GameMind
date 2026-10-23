"""Quota contracts: real SDK, mocked HTTP, disposable PostgreSQL, no hosted calls."""
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.design_agent.gemini_provider import GeminiProvider
from app.design_agent.llm_provider import NvidiaProviderError
from test_gemini_provider import config, sdk, interaction, request


class Clock:
    def __init__(self, instant="2026-10-23T12:00:00+00:00"):
        self.instant = datetime.fromisoformat(instant)
        self.elapsed = 0.0
        self.sleeps = []

    def now(self):
        return self.instant

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.elapsed += seconds
        self.instant += timedelta(seconds=seconds)


@pytest.fixture(autouse=True)
def isolated_budget(db_session, monkeypatch):
    from app.design_agent import gemini_budget as budgets
    from app.models.gemini_usage import GeminiDailyUsage
    db_session.query(GeminiDailyUsage).delete()
    db_session.commit()
    monkeypatch.setattr(budgets, "process_window", budgets.SlidingWindow())
    monkeypatch.setattr(GeminiProvider, "_verified_models", set())
    yield
    db_session.rollback()
    db_session.query(GeminiDailyUsage).delete()
    db_session.commit()


def budget(settings=None, clock=None):
    from app.design_agent.gemini_budget import GeminiBudget, SlidingWindow
    clock = clock or Clock()
    settings = settings or config()
    return GeminiBudget(settings, clock=clock.now,
        window=SlidingWindow(monotonic=clock.monotonic, sleep=clock.sleep)), clock


def transport(respond, settings=None, clock=None, **kwargs):
    limits, clock = budget(settings, clock)
    return GeminiProvider(settings or config(), client=sdk(respond), budget=limits,
        sleep=clock.sleep, jitter=lambda low, high: 0, **kwargs), limits, clock


@pytest.mark.parametrize("status", [400, 401, 403])
def test_authentication_failures_are_not_generic_rejections_or_retried(status):
    calls = []
    def respond(r):
        calls.append(r)
        return httpx.Response(status, json=[{"error": {"code": status, "message": "SECRET",
            "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}]}}])
    provider = GeminiProvider(config(), client=sdk(respond))
    with pytest.raises(NvidiaProviderError) as caught:
        provider.complete(request())
    assert caught.value.code == "authentication_error"
    assert "GEMINI_API_KEY" in str(caught.value) and "SECRET" not in str(caught.value)
    assert len(calls) == 1
    provider.close()


@pytest.mark.parametrize("before,after", [
    ("2026-03-08T07:59:59+00:00", "2026-03-08T08:00:00+00:00"),
    ("2026-03-09T06:59:59+00:00", "2026-03-09T07:00:00+00:00"),
    ("2026-11-01T06:59:59+00:00", "2026-11-01T07:00:00+00:00"),
    ("2026-11-02T07:59:59+00:00", "2026-11-02T08:00:00+00:00"),
])
def test_daily_exhaustion_resets_at_pacific_midnight_across_dst(before, after):
    clock = Clock(before)
    provider, limits, _ = transport(lambda r: interaction('{"answer":"ok"}'), clock=clock)
    provider.complete(request())
    limits.exhaust("dev-env-model")
    with pytest.raises(NvidiaProviderError):
        provider.complete(request())
    assert limits.usage()[0]["requests"] == 1
    clock.instant = datetime.fromisoformat(after)
    provider.complete(request())
    today = limits.usage()[0]
    assert today["requests"] == 1 and today["exhausted"] is False
    provider.close()


def test_rpm_sliding_window_waits_and_is_bounded():
    settings = config(GEMINI_DEV_RPM=1, GEMINI_RPM_MAX_WAIT_SECONDS=60)
    provider, limits, clock = transport(lambda r: interaction('{"answer":"ok"}'), settings)
    provider.complete(request())
    provider.complete(request())
    assert clock.sleeps == [60.0] and limits.usage()[0]["requests"] == 2
    limited, _, short_clock = transport(lambda r: interaction('{"answer":"ok"}'),
        config(GEMINI_DEV_RPM=1, GEMINI_RPM_MAX_WAIT_SECONDS=2))
    limited.complete(request())
    with pytest.raises(NvidiaProviderError) as caught:
        limited.complete(request())
    assert caught.value.code == "rpm_wait_exceeded" and short_clock.sleeps == []
    provider.close()
    limited.close()


def test_reservation_is_committed_before_http_and_counts_retries_repairs_and_truncation():
    from app.database import SessionLocal
    from app.models.gemini_usage import GeminiDailyUsage
    seen = []
    def respond(r):
        with SessionLocal() as db:
            seen.append(db.query(GeminiDailyUsage).one().requests)
        if len(seen) == 1:
            return httpx.Response(503, json={"error": {"code": 503}})
        if len(seen) == 2:
            return interaction('{"answer":', status="incomplete")
        return interaction("broken" if len(seen) == 3 else '{"answer":"repaired"}')
    provider, _, _ = transport(respond)
    assert provider.complete(request()).content == {"answer": "repaired"}
    assert seen == [1, 2, 3, 4]
    provider.close()


def test_run_cap_survives_a_new_provider_and_prevents_any_extra_http(db_session):
    from app.models.design_agent import DesignAgentRun
    from app.models.project import GameProject
    import uuid
    project = "budget_" + uuid.uuid4().hex[:12]
    db_session.add(GameProject(id=project, name="Budget test"))
    run = DesignAgentRun(game_project_id=project, objective="Synthetic", document_ids=[], provider_name="gemini")
    db_session.add(run)
    db_session.commit()
    run_id = run.id
    settings = config(GEMINI_MAX_REQUESTS_PER_RUN=1)
    calls = []
    def respond(r):
        calls.append(r)
        return interaction('{"answer":"ok"}')
    first, _, _ = transport(respond, settings)
    with first.run_context(run_id):
        first.complete(request())
    second, _, _ = transport(respond, settings)
    with second.run_context(run_id), pytest.raises(NvidiaProviderError) as caught:
        second.complete(request())
    assert caught.value.code == "run_request_limit" and caught.value.diagnostics["degraded"]
    assert len(calls) == 1
    db_session.refresh(run)
    assert run.gemini_request_count == 1
    first.close()
    second.close()


def test_preflight_refuses_if_either_configured_model_has_too_little_daily_budget():
    settings = config("showcase", GEMINI_SHOWCASE_RPD=8)
    provider, limits, _ = transport(lambda r: interaction('{"answer":"ok"}'), settings)
    provider.complete(request("critique"))
    with pytest.raises(NvidiaProviderError) as caught:
        provider.preflight()
    assert caught.value.code == "daily_budget_preflight"
    assert "showcase-env-model" in str(caught.value) and "7" in str(caught.value)
    provider.close()


@pytest.mark.parametrize("retry_info,delay", [("12.5s", 12.5), ("90s", 60), (None, 60)])
def test_429_retry_delay_is_read_from_real_sdk_body_and_retry_is_counted(retry_info, delay):
    calls = []
    def respond(r):
        calls.append(r)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"code": 429, "details":
                [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_info}] if retry_info else []}})
        return interaction('{"answer":"ok"}')
    provider, limits, clock = transport(respond)
    assert provider.complete(request()).content == {"answer": "ok"}
    assert len(calls) == 2 and clock.sleeps == [delay]
    assert limits.usage()[0]["requests"] == 2
    provider.close()


def test_second_429_exhausts_model_durably_and_showcase_falls_back_with_honest_trace():
    calls = []
    def respond(r):
        model = json.loads(r.content)["model"]
        calls.append(model)
        return (interaction('{"answer":"cheaper"}') if model == "dev-env-model" else
            httpx.Response(429, json={"error": {"code": 429}}))
    settings = config("showcase")
    provider, limits, _ = transport(respond, settings)
    result = provider.complete(request("critique"))
    assert result.content == {"answer": "cheaper"} and result.model_name == "dev-env-model"
    assert result.metadata["degraded"] and result.metadata["fallback_from_model"] == "showcase-env-model"
    assert result.metadata["request_attempts"] == 3
    provider.close()
    fresh, _, _ = transport(respond, settings)
    fresh.complete(request("critique"))
    assert calls == ["showcase-env-model", "showcase-env-model", "dev-env-model", "dev-env-model"]
    assert next(row for row in limits.usage() if row["model"] == "showcase-env-model")["exhausted"]
    fresh.close()


def test_failed_400_counts_but_is_not_retried_and_no_cheap_fallback_for_auth():
    calls = []
    def respond(r):
        calls.append(r)
        return httpx.Response(400, json={"error": {"code": 400, "message": "schema rejected"}})
    provider, limits, clock = transport(respond, config("showcase"))
    with pytest.raises(NvidiaProviderError) as caught:
        provider.complete(request("critique"))
    assert caught.value.code == "request_rejected" and len(calls) == 1 and clock.sleeps == []
    assert next(row for row in limits.usage() if row["model"] == "showcase-env-model")["requests"] == 1
    provider.close()


def test_startup_model_lookup_is_counted_once_per_process_across_provider_instances():
    calls = []
    def respond(r):
        calls.append(r)
        return httpx.Response(200, json={"name": "models/dev-env-model"})
    first, limits, _ = transport(respond)
    first.validate_models()
    first.close()
    second, _, _ = transport(respond)
    second.validate_models()
    assert len(calls) == 1 and calls[0].method == "GET"
    assert limits.usage()[0]["requests"] == 1
    second.close()


def test_rpd_reservation_is_atomic_across_concurrent_providers():
    from concurrent.futures import ThreadPoolExecutor
    settings = config(GEMINI_DEV_RPD=1)
    calls = []
    def respond(r):
        calls.append(r)
        return interaction('{"answer":"ok"}')
    providers = [transport(respond, settings)[0] for _ in range(2)]
    def invoke(provider):
        try:
            return provider.complete(request()).content
        except NvidiaProviderError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(invoke, providers))
    assert results.count("daily_budget_exhausted") == 1 and len(calls) == 1
    assert providers[0].budget.usage()[0]["requests"] == 1
    for provider in providers:
        provider.close()


def test_database_failure_prevents_http_and_does_not_leak_connection_details():
    from sqlalchemy.exc import SQLAlchemyError
    calls = []
    provider, limits, _ = transport(lambda r: calls.append(r))
    class Unavailable:
        def __call__(self):
            raise SQLAlchemyError("PRIVATE_CONNECTION_SECRET")

        def begin(self):
            raise SQLAlchemyError("PRIVATE_CONNECTION_SECRET")
    limits.session_factory = Unavailable()
    with pytest.raises(NvidiaProviderError) as caught:
        provider.complete(request())
    assert caught.value.code == "budget_unavailable" and calls == []
    assert "PRIVATE_CONNECTION_SECRET" not in str(caught.value)
    provider.close()


@pytest.mark.parametrize("mode,stop", [("inline", "preflight"), ("queued", "preflight"), ("inline", "run_cap")])
def test_dashboard_checks_preflight_before_saving_and_persists_run_cap_degradation(db_session, monkeypatch, mode, stop):
    import uuid
    from app.config import settings as app_settings
    from app.api.v1.design_agent import get_design_agent_service
    from app.design_agent.gemini_provider import GeminiDesignAgentProvider
    from app.design_agent.nvidia_provider import ResilientDesignAgentProvider
    from app.design_agent.provider import MockDesignAgentProvider
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS
    from app.models.design_agent import DesignAgentRun
    from test_design_agent_workflow import create_source, make_service, CountingRAG, client
    from main import app
    project = "budget_flow_" + uuid.uuid4().hex[:10]
    document, chunks = create_source(db_session, project)
    calls = []
    def respond(r):
        calls.append(r)
        return interaction(json.dumps({"section_queries": {key: "scout missions game design" for key in BLUEPRINT_SECTION_KEYS}}))
    chosen = config(GEMINI_DEV_RPD=8, GEMINI_MAX_REQUESTS_PER_RUN=1)
    provider, limits, _ = transport(respond, chosen)
    if stop == "preflight":
        limits.reserve("dev-env-model")
    resilient = ResilientDesignAgentProvider(primary=GeminiDesignAgentProvider(llm_provider=provider), fallback=MockDesignAgentProvider())
    service = make_service(db_session, CountingRAG(chunks), resilient)
    app.dependency_overrides[get_design_agent_service] = lambda: service
    monkeypatch.setattr(app_settings, "DESIGN_AGENT_EXECUTION_MODE", mode)
    try:
        response = client.post("/api/v1/design-agent/runs", headers={"X-Game-Project-ID": project}, json={
            "objective": "Review game design", "document_ids": [str(document.id)], "hosted_provider_consent": True})
        if stop == "preflight":
            assert response.status_code == 429 and response.json()["detail"]["code"] == "daily_budget_preflight"
            assert db_session.query(DesignAgentRun).filter_by(game_project_id=project).count() == 0 and calls == []
        else:
            assert response.status_code == 503 and len(calls) == 1
            db_session.expire_all()
            run = db_session.query(DesignAgentRun).filter_by(game_project_id=project).one()
            assert run.status == "failed" and run.model_config["degraded"] and run.gemini_request_count == 1
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)
        provider.close()


def test_usage_cli_prints_counts_and_limits_without_google_or_secrets(monkeypatch, capsys):
    import gemini_usage
    limits, _ = budget()
    limits.reserve("dev-env-model")
    monkeypatch.setattr(gemini_usage, "GeminiBudget", lambda _: limits)
    assert gemini_usage.main() == 0
    output = capsys.readouterr().out
    rows = json.loads(output)
    assert rows[0]["requests"] == 1 and rows[0]["rpd"] == 500 and rows[0]["rpm"] == 5
    assert rows[0]["pacific_day"] == "2026-10-23" and "offline-key" not in output


def test_model_lookup_auth_error_uses_genai_details_dict_not_interactions_body():
    calls = []
    def respond(r):
        calls.append(r)
        return httpx.Response(400, json={"error": {"code": 400, "details": [{"reason": "API_KEY_INVALID"}]}})
    provider, limits, _ = transport(respond)
    with pytest.raises(NvidiaProviderError) as caught:
        provider.validate_models()
    assert caught.value.code == "authentication_error" and len(calls) == 1
    assert limits.usage()[0]["requests"] == 1
    provider.close()


def test_exhausted_model_is_rejected_before_an_unnecessary_rpm_wait():
    settings = config("showcase", GEMINI_SHOWCASE_RPM=1)
    def respond(r):
        return (interaction('{"answer":"cheap"}') if json.loads(r.content)["model"] == "dev-env-model"
            else httpx.Response(429, json={"error": {"code": 429}}))
    provider, _, clock = transport(respond, settings)
    provider.complete(request("critique"))
    provider.complete(request("critique"))
    assert clock.sleeps == [60.0]
    provider.close()
