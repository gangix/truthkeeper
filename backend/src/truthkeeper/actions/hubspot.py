"""HubSpot action executor: remove_from_sequence.

Pragmatic implementation: HubSpot's v3 API doesn't expose a direct
"un-enroll from sequence" call without first looking up enrollment ids per
contact per sequence. For the demo, we PATCH the contact's `hs_lead_status`
property to a value the sequence's enrollment criteria excludes on. The
sequence stops sending at the next tick. The contact id is returned as
external_id so the audit row cross-references HubSpot.

Switch to a true unenroll endpoint if you find one during implementation;
the function signature stays the same.
"""

from __future__ import annotations

import asyncio
import logging
import os

from hubspot import HubSpot
from hubspot.crm.contacts import ApiException, SimplePublicObjectInput

from truthkeeper.actions.result import ExecutionResult

logger = logging.getLogger(__name__)

# Property + value combination that breaks sequence enrollment criteria.
# Configurable later if needed; for the demo, this is canonical.
_EXCLUDE_PROPERTY = "hs_lead_status"
_EXCLUDE_VALUE = "UNQUALIFIED"


def _client() -> HubSpot:
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if not token:
        raise RuntimeError(
            "HUBSPOT_ACCESS_TOKEN not set. Add to validation/.env (local) or "
            "Cloud Run env (prod)."
        )
    return HubSpot(access_token=token)


def _find_contact_id_by_email(client: HubSpot, email: str) -> str | None:
    """Look up a HubSpot contact by email, return its id or None."""
    from hubspot.crm.contacts import PublicObjectSearchRequest

    request = PublicObjectSearchRequest(
        filter_groups=[
            {
                "filters": [
                    {
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email,
                    }
                ]
            }
        ],
        properties=["email"],
        limit=1,
    )
    resp = client.crm.contacts.search_api.do_search(public_object_search_request=request)
    if not resp.results:
        return None
    return resp.results[0].id


async def remove_from_sequence(parameters: dict[str, str]) -> ExecutionResult:
    """Stop a HubSpot contact from receiving further sequence emails.

    `parameters["email"]` — the contact's email address.
    `parameters["sequence"]` — the sequence name (used only in the message
        for the audit log; the implementation excludes via property update,
        not via sequence-specific endpoint).
    """
    email = parameters.get("email")
    sequence = parameters.get("sequence", "<unknown>")
    if not email:
        return ExecutionResult(
            status="failed",
            error="parameter 'email' missing or empty",
        )

    try:
        client = _client()
    except Exception as exc:  # noqa: BLE001
        return ExecutionResult(status="failed", error=f"{type(exc).__name__}: {exc}")

    try:
        contact_id = await asyncio.wait_for(
            asyncio.to_thread(_find_contact_id_by_email, client, email),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        return ExecutionResult(
            status="failed",
            error=f"HubSpot contact search timeout (>15s) for {email}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("HubSpot search failed for %s: %s", email, exc)
        return ExecutionResult(status="failed", error=f"{type(exc).__name__}: {exc}")

    if contact_id is None:
        return ExecutionResult(
            status="failed",
            error=f"HubSpot contact not found for email {email}",
        )

    try:
        await asyncio.wait_for(
            asyncio.to_thread(
                client.crm.contacts.basic_api.update,
                contact_id=contact_id,
                simple_public_object_input=SimplePublicObjectInput(
                    properties={_EXCLUDE_PROPERTY: _EXCLUDE_VALUE}
                ),
            ),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        return ExecutionResult(
            status="failed",
            error=f"HubSpot patch timeout (>15s) for contact {contact_id}",
        )
    except ApiException as exc:
        logger.warning("HubSpot patch failed for %s: %s", contact_id, exc)
        return ExecutionResult(
            status="failed", error=f"ApiException: {exc.status} {exc.reason}"
        )
    except Exception as exc:  # noqa: BLE001
        return ExecutionResult(status="failed", error=f"{type(exc).__name__}: {exc}")

    return ExecutionResult(
        status="succeeded",
        external_id=contact_id,
        message=(
            f"HubSpot contact {contact_id} ({email}) marked "
            f"{_EXCLUDE_PROPERTY}={_EXCLUDE_VALUE}; sequence '{sequence}' will stop"
        ),
    )
