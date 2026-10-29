"""Read today's local reservation ledger; no Google requests or secret output."""
import json
import sys
from app.config import settings
from app.design_agent.gemini_budget import GeminiBudget
from app.design_agent.llm_provider import NvidiaProviderError


def main():
    try:
        print(json.dumps(GeminiBudget(settings).usage(), indent=2))
        return 0
    except NvidiaProviderError as error:
        print(f"{error.code}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
