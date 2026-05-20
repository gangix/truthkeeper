"""BigQuery profiling tool exposed to the ProfilingAgent via FunctionTool.

For each column, runs:
  SELECT col, COUNT(*) FROM dataset.table GROUP BY col
    ORDER BY COUNT(*) DESC LIMIT 20
Plus COUNT(DISTINCT col). If distinct cardinality > CARDINALITY_CAP, the
column is reported as `{cardinality: "high"}` without enumerating values
(prevents dumping primary keys into the LLM prompt).
"""

from __future__ import annotations

import logging
from typing import Any

from google.adk.tools import FunctionTool
from google.cloud import bigquery

logger = logging.getLogger(__name__)

_DEFAULT_PROJECT = "truthkeeper-hack-2026"
CARDINALITY_CAP = 50
TOP_VALUES_LIMIT = 20


def profile_columns(
    dataset: str,
    table: str,
    columns: list[str],
    *,
    project: str = _DEFAULT_PROJECT,
) -> dict[str, Any]:
    """Profile each column for distinct values and cardinality.

    Returns a dict shaped like:
      {
        "dataset": "salesforce", "table": "account",
        "columns": {
          "status": {"cardinality": 3, "distinct_values": [
              {"value": "Active", "count": 32}, {"value": "Trial", "count": 12}, ...
          ]},
          "id":     {"cardinality": "high", "distinct_values": None}
        }
      }
    """
    client = bigquery.Client(project=project)
    out: dict[str, Any] = {"dataset": dataset, "table": table, "columns": {}}
    fq = f"`{project}.{dataset}.{table}`"

    for col in columns:
        try:
            card_row = next(
                iter(
                    client.query(
                        f"SELECT COUNT(DISTINCT `{col}`) AS c FROM {fq}"
                    ).result()
                )
            )
            cardinality = int(card_row["c"])
        except Exception as exc:
            logger.warning("profile_columns: cardinality query failed for %s.%s.%s: %s",
                           dataset, table, col, exc)
            out["columns"][col] = {"error": str(exc)}
            continue

        if cardinality > CARDINALITY_CAP:
            out["columns"][col] = {"cardinality": "high", "distinct_values": None}
            continue

        try:
            rows = client.query(
                f"SELECT `{col}` AS v, COUNT(*) AS c FROM {fq} "
                f"GROUP BY `{col}` ORDER BY c DESC LIMIT {TOP_VALUES_LIMIT}"
            ).result()
            distinct_values = [
                {"value": None if r["v"] is None else str(r["v"]), "count": int(r["c"])}
                for r in rows
            ]
        except Exception as exc:
            logger.warning("profile_columns: distinct query failed for %s.%s.%s: %s",
                           dataset, table, col, exc)
            out["columns"][col] = {"error": str(exc)}
            continue

        out["columns"][col] = {
            "cardinality": cardinality,
            "distinct_values": distinct_values,
        }

    return out


bigquery_profile_tool = FunctionTool(func=profile_columns)
