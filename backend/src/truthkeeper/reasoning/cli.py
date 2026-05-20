"""Run reconciliation reasoning against DEMO_SPEC.

Usage:
  cd backend && uv run python -m truthkeeper.reasoning.cli D1
  cd backend && uv run python -m truthkeeper.reasoning.cli D1 --max-violations 1
  cd backend && uv run python -m truthkeeper.reasoning.cli all --max-violations 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from truthkeeper.config import load_runtime_env
from truthkeeper.reasoning.agent import reason_about_violation
from truthkeeper.reasoning.bigquery import execute_rule_sql
from truthkeeper.reasoning.orchestrator import reconcile_all_rules
from truthkeeper.spec.demo import DEMO_SPEC


async def _amain() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile one rule or every rule from DEMO_SPEC end-to-end "
            "(BigQuery + Gemini)."
        )
    )
    parser.add_argument(
        "rule_id",
        help="Rule ID (e.g. D1) or the literal 'all' to reconcile every rule.",
    )
    parser.add_argument(
        "--max-violations",
        type=int,
        default=3,
        help="Cap how many violations get reasoned about per rule (cost control).",
    )
    args = parser.parse_args()

    load_runtime_env()

    if args.rule_id.lower() == "all":
        print(
            f"Reconciling all {len(DEMO_SPEC.rules)} rules for "
            f"{DEMO_SPEC.company_name}...",
            file=sys.stderr,
        )
        report = await reconcile_all_rules(
            spec=DEMO_SPEC, max_violations_per_rule=args.max_violations
        )
        print(report.model_dump_json(indent=2))
        for rule in report.rules:
            print(
                f"  {rule.rule_id} [{rule.severity.value}] "
                f"{rule.violation_count} violation(s), "
                f"{rule.sampled_count} reasoned",
                file=sys.stderr,
            )
        return 0

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
