"""Small, in-process abuse guard for the current single-backend deployment."""

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0


class AuthRateLimiter:
    """Sliding-window limiter; use a shared store when running more than one backend replica."""

    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, max_attempts: int, window_seconds: int) -> RateLimitResult:
        now = monotonic()
        with self._lock:
            attempts = self._prune(key, now, window_seconds)
            if len(attempts) < max_attempts:
                return RateLimitResult(allowed=True)
            retry_after = max(1, int(window_seconds - (now - attempts[0])))
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

    def record(self, key: str, window_seconds: int) -> None:
        now = monotonic()
        with self._lock:
            self._prune(key, now, window_seconds).append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()

    def _prune(self, key: str, now: float, window_seconds: int) -> deque[float]:
        attempts = self._attempts[key]
        while attempts and now - attempts[0] >= window_seconds:
            attempts.popleft()
        return attempts


auth_rate_limiter = AuthRateLimiter()
