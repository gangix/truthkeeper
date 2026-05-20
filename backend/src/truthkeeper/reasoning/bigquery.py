"""Execute a rule's SQL against BigQuery and return violation rows."""

from __future__ import annotations

from typing import Any

from google.cloud import bigquery

from truthkeeper.spec.models import Rule

_DEFAULT_PROJECT = "truthkeeper-hack-2026"


def execute_rule_sql(
    rule: Rule,
    project: str = _DEFAULT_PROJECT,
    max_rows: int = 50,
) -> list[dict[str, Any]]:
    client = bigquery.Client(project=project)
    job = client.query(rule.sql)
    return [dict(row) for row in job.result(max_results=max_rows)]
