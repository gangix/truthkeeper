from truthkeeper.spec import CompanyAgentSpec, Severity, SystemName
from truthkeeper.spec.demo import DEMO_SPEC


def test_demo_spec_has_three_connected_systems() -> None:
    names = {cs.name for cs in DEMO_SPEC.connected_systems}
    assert names == {SystemName.salesforce, SystemName.stripe, SystemName.hubspot}


def test_demo_spec_covers_five_rules() -> None:
    ids = [r.id for r in DEMO_SPEC.rules]
    assert ids == ["D1", "D2", "D3", "D4", "D5"]


def test_every_rule_has_sql_and_at_least_one_action() -> None:
    for rule in DEMO_SPEC.rules:
        assert rule.sql.strip(), f"rule {rule.id} has empty SQL"
        assert "SELECT" in rule.sql.upper(), f"rule {rule.id} SQL has no SELECT"
        assert rule.corrective_action_templates, (
            f"rule {rule.id} has no corrective actions"
        )


def test_severity_distribution_includes_critical_rules() -> None:
    critical = [r.id for r in DEMO_SPEC.rules if r.severity == Severity.critical]
    assert "D1" in critical
    assert "D5" in critical


def test_entity_model_customer_maps_all_three_systems() -> None:
    customer = next(em for em in DEMO_SPEC.entity_model if em.name == "Customer")
    systems = {m.system for m in customer.mappings}
    assert systems == {SystemName.salesforce, SystemName.stripe, SystemName.hubspot}


def test_subscription_entity_uses_history_table_with_active_filter() -> None:
    sub = next(em for em in DEMO_SPEC.entity_model if em.name == "Subscription")
    stripe_mapping = next(m for m in sub.mappings if m.system == SystemName.stripe)
    assert stripe_mapping.table == "subscription_history"
    assert stripe_mapping.extra_fields.get("active_row_filter") == "_fivetran_active = TRUE"


def test_demo_spec_roundtrips_through_json() -> None:
    payload = DEMO_SPEC.model_dump_json()
    rebuilt = CompanyAgentSpec.model_validate_json(payload)
    assert rebuilt == DEMO_SPEC
