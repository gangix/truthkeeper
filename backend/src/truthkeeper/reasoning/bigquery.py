"""Execute a rule's SQL against BigQuery and return violation rows."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from google.cloud import bigquery

from truthkeeper.spec.models import Rule

_DEFAULT_PROJECT = "truthkeeper-hack-2026"


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _normalize_value(v) for k, v in row.items()}


def execute_rule_sql(
    rule: Rule,
    project: str = _DEFAULT_PROJECT,
    max_rows: int = 50,
) -> list[dict[str, Any]]:
    client = bigquery.Client(project=project)
    job = client.query(rule.sql)
    return [_normalize_row(dict(row)) for row in job.result(max_results=max_rows)]
