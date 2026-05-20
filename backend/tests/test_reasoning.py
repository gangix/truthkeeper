from truthkeeper.reasoning.agent import resolve_action_parameters
from truthkeeper.spec.models import CorrectiveActionTemplate, SystemName


def test_resolve_action_parameters_substitutes_column_values() -> None:
    template = CorrectiveActionTemplate(
        target_system=SystemName.stripe,
        action_type="cancel_subscription",
        parameter_mapping={"subscription_id": "stripe_subscription_id"},
        description="Cancel Stripe subscription {stripe_subscription_id}",
    )
    violation = {"stripe_subscription_id": "sub_ABC", "noise": "ignored"}
    resolved = resolve_action_parameters(template, violation)
    assert resolved == {"subscription_id": "sub_ABC"}


def test_resolve_action_parameters_passes_literals_through() -> None:
    template = CorrectiveActionTemplate(
        target_system=SystemName.salesforce,
        action_type="update_account_status",
        parameter_mapping={
            "account_id": "salesforce_account_id",
            "new_status": "Churned",
        },
        description="Set Salesforce Account status = Churned",
    )
    violation = {"salesforce_account_id": "001xyz"}
    resolved = resolve_action_parameters(template, violation)
    assert resolved == {"account_id": "001xyz", "new_status": "Churned"}


def test_resolve_action_parameters_coerces_non_strings() -> None:
    template = CorrectiveActionTemplate(
        target_system=SystemName.hubspot,
        action_type="merge_contacts",
        parameter_mapping={"duplicate_contact_id": "hubspot_contact_id"},
        description="Merge HubSpot contact",
    )
    violation = {"hubspot_contact_id": 781371029735}
    resolved = resolve_action_parameters(template, violation)
    assert resolved == {"duplicate_contact_id": "781371029735"}


def test_resolve_action_parameters_handles_none_as_empty_string() -> None:
    template = CorrectiveActionTemplate(
        target_system=SystemName.stripe,
        action_type="cancel_subscription",
        parameter_mapping={"subscription_id": "stripe_subscription_id"},
        description="Cancel subscription",
    )
    violation = {"stripe_subscription_id": None}
    resolved = resolve_action_parameters(template, violation)
    assert resolved == {"subscription_id": ""}
