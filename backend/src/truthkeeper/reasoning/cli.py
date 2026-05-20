"""Run one rule's reconciliation reasoning loop against DEMO_SPEC.

Usage:
  cd backend && uv run python -m truthkeeper.reasoning.cli D1
  cd backend && uv run python -m truthkeeper.reasoning.cli D1 --max-violations 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from truthkeeper.reasoning.agent import reason_about_violation
from truthkeeper.reasoning.bigquery import execute_rule_sql
from truthkeeper.spec.demo import DEMO_SPEC


def _load_env() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    candidates = [repo_root / "validation" / ".env", repo_root / ".env"]
    for c in candidates:
        if c.exists():
            load_dotenv(c, override=False)

    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "truthkeeper-hack-2026")
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")


async def _amain() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile one rule from DEMO_SPEC end-to-end (BigQuery + Gemini)."
    )
    parser.add_argument("rule_id", help="Rule ID, e.g. D1")
    parser.add_argument(
        "--max-violations",
        type=int,
        default=3,
        help="Cap how many violations get reasoned about (default 3, cost control).",
    )
    args = parser.parse_args()

    _load_env()

    rule = next((r for r in DEMO_SPEC.rules if r.id == args.rule_id), None)
    if rule is None:
        print(f"ERROR: rule {args.rule_id} not found in DEMO_SPEC", file=sys.stderr)
        return 2

    print(f"[1/3] Executing SQL for rule {rule.id}: {rule.name}", file=sys.stderr)
    rows = execute_rule_sql(rule)
    print(f"      -> {len(rows)} violation row(s)", file=sys.stderr)
    if not rows:
        print("      No violations detected; nothing to reason about.", file=sys.stderr)
        return 0

    rows = rows[: args.max_violations]
    print(
        f"[2/3] Reasoning over {len(rows)} violation(s) with Gemini via ADK...",
        file=sys.stderr,
    )

    for i, row in enumerate(rows, start=1):
        print(f"\n----- Violation {i}/{len(rows)} -----", file=sys.stderr)
        result = await reason_about_violation(rule=rule, violation=row, spec=DEMO_SPEC)
        print(
            json.dumps(
                {
                    "rule_id": rule.id,
                    "violation_row": row,
                    "reasoning": result.model_dump(),
                },
                indent=2,
                default=str,
            )
        )

    print("\n[3/3] Done.", file=sys.stderr)
    return 0


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
