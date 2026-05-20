"""Smoke check: profile_columns returns a typed structure with capped cardinality."""

import os

import pytest


def _can_hit_bq() -> bool:
    return bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))


@pytest.mark.skipif(not _can_hit_bq(), reason="GOOGLE_CLOUD_PROJECT not set")
def test_profile_columns_returns_distincts_for_low_cardinality() -> None:
    from truthkeeper.onboarding.bigquery_profile import profile_columns

    result = profile_columns(
        dataset="salesforce", table="account", columns=["type"]
    )
    assert "type" in result["columns"]
    col = result["columns"]["type"]
    assert "cardinality" in col
    if col["cardinality"] != "high":
        assert isinstance(col["distinct_values"], list)
        assert len(col["distinct_values"]) <= 20


@pytest.mark.skipif(not _can_hit_bq(), reason="GOOGLE_CLOUD_PROJECT not set")
def test_profile_columns_caps_at_high_cardinality() -> None:
    from truthkeeper.onboarding.bigquery_profile import profile_columns

    result = profile_columns(
        dataset="salesforce", table="account", columns=["id"]
    )
    col = result["columns"]["id"]
    assert col["cardinality"] == "high"
    assert col["distinct_values"] is None
