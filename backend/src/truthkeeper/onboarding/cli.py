"""End-to-end smoke runner: drive the onboarding pipeline against the live
Fivetran account + BigQuery, print each StageEvent to stdout. Mirrors
reasoning/cli.py.

Usage:
  cd backend && uv run python -m truthkeeper.onboarding.cli --company-id truthkeeper-demo
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from truthkeeper.config import load_runtime_env
from truthkeeper.onboarding.pipeline import run_onboarding


async def _amain() -> int:
    parser = argparse.ArgumentParser(description="Run the onboarding pipeline end-to-end.")
    parser.add_argument("--company-id", default="truthkeeper-demo")
    args = parser.parse_args()

    load_runtime_env()

    print(f"Running onboarding for {args.company_id}...", file=sys.stderr)
    async for event in run_onboarding(args.company_id):
        print(json.dumps(event.model_dump(), indent=2, default=str))
        if event.error:
            print(f"  ERROR at stage {event.stage}: {event.error}", file=sys.stderr)
            return 2
        if event.done:
            print("\nDone.", file=sys.stderr)
            return 0
    return 1


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
