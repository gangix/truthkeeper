"""Cross-rule reconciliation orchestrator.

Runs every rule in a CompanyAgentSpec: for each rule, executes the BigQuery
SQL (deterministic), then fans out per-violation Gemini reasoning calls and
collects them into a ReconciliationReport. Per the brief §4 runtime loop:
SQL surfaces violations cheaply, Gemini does the per-violation reasoning.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from truthkeeper.reasoning.agent import reason_about_violation
from truthkeeper.reasoning.bigquery import execute_rule_sql
from truthkeeper.reasoning.output import (
    ReconciliationReport,
    RuleReconciliation,
    ViolationReasoning,
)
from truthkeeper.spec.models import CompanyAgentSpec, Rule

logger = logging.getLogger(__name__)


async def _reconcile_one_rule(
    rule: Rule,
    spec: CompanyAgentSpec,
    *,
    max_violations: int,
) -> RuleReconciliation:
    rows = execute_rule_sql(rule)
    sampled = rows[:max_violations]
    logger.info(
        "rule=%s violations=%d sampled=%d", rule.id, len(rows), len(sampled)
    )

    violations: list[ViolationReasoning] = []
    if sampled:
        coros = [
            reason_about_violation(rule=rule, violation=row, spec=spec)
            for row in sampled
        ]
        outputs = await asyncio.gather(*coros)
        violations = [
            ViolationReasoning(violation=row, reasoning=out)
            for row, out in zip(sampled, outputs, strict=True)
        ]

    return RuleReconciliation(
        rule_id=rule.id,
        rule_name=rule.name,
        severity=rule.severity,
        violation_count=len(rows),
        sampled_count=len(sampled),
        violations=violations,
    )


async def reconcile_all_rules(
    spec: CompanyAgentSpec,
    *,
    max_violations_per_rule: int = 3,
    rule_ids: Iterable[str] | None = None,
) -> ReconciliationReport:
    """Run every rule in `spec` (optionally filtered) and return the report."""
    filter_set = set(rule_ids) if rule_ids is not None else None
    rules = [r for r in spec.rules if filter_set is None or r.id in filter_set]

    coros = [
        _reconcile_one_rule(
            rule=r, spec=spec, max_violations=max_violations_per_rule
        )
        for r in rules
    ]
    results = await asyncio.gather(*coros)

    return ReconciliationReport(
        company_id=spec.company_id,
        company_name=spec.company_name,
        rules=results,
    )
