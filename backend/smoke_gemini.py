"""Manual dev-profile smoke: exactly one inference attempt, no GDD/database access."""
import json
import sys

from app.config import settings
from app.design_agent.gemini_provider import GeminiProvider, GeminiDesignAgentProvider
from app.design_agent.llm_provider import NvidiaProviderError


def main():
    if settings.LLM_PROFILE != "dev":
        print("Set LLM_PROFILE=dev before running this one-request smoke.", file=sys.stderr)
        return 1
    transport = None
    try:
        transport = GeminiProvider(settings, request_limit=1)
        result = GeminiDesignAgentProvider(llm_provider=transport).plan(
            "Find design evidence for a synthetic demo game.", [],
        )
        print(json.dumps(result.content, indent=2))
        return 0
    except NvidiaProviderError as error:
        print(f"{error.code}: {error}", file=sys.stderr)
        return 1
    finally:
        if transport is not None:
            transport.close()


if __name__ == "__main__":
    raise SystemExit(main())
