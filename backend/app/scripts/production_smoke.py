"""Verify that a running GameMind API is live and dependency-ready."""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _fetch_json(url: str, timeout_seconds: float) -> tuple[int, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Request-ID": "production-smoke",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw_body": body[:500]}
        return error.code, payload


def run_smoke(
    base_url: str,
    timeout_seconds: float = 5.0,
    attempts: int = 20,
    retry_delay_seconds: float = 1.0,
) -> dict[str, Any]:
    """Retry startup briefly, then require healthy liveness and readiness."""
    normalized_base_url = base_url.rstrip("/")
    results: dict[str, Any] = {}
    last_error: str | None = None

    for attempt in range(1, attempts + 1):
        try:
            health_status, health = _fetch_json(
                f"{normalized_base_url}/health",
                timeout_seconds,
            )
            ready_status, ready = _fetch_json(
                f"{normalized_base_url}/ready",
                timeout_seconds,
            )
            results = {
                "base_url": normalized_base_url,
                "attempt": attempt,
                "health": {"status_code": health_status, "body": health},
                "ready": {"status_code": ready_status, "body": ready},
            }
            if (
                health_status == 200
                and health.get("status") == "healthy"
                and ready_status == 200
                and ready.get("status") == "healthy"
            ):
                return results
            last_error = "API responded but is not ready"
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = f"{type(error).__name__}: {error}"

        if attempt < attempts:
            time.sleep(retry_delay_seconds)

    raise RuntimeError(
        f"GameMind production smoke failed after {attempts} attempts: "
        f"{last_error}; last_result={json.dumps(results, default=str)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("GAMEMIND_BASE_URL", "http://localhost:8000"),
    )
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--attempts", type=int, default=20)
    parser.add_argument("--retry-delay", type=float, default=1.0)
    args = parser.parse_args()

    result = run_smoke(
        args.base_url,
        timeout_seconds=args.timeout,
        attempts=args.attempts,
        retry_delay_seconds=args.retry_delay,
    )
    print(json.dumps({"status": "passed", **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
