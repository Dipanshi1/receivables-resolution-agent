import json
from dataclasses import replace

import pytest

from app.domain.enums import RecoveryCaseStatus
from app.services.audit import AuditRepository, AuditService
from app.services.reconciliation import (
    ReconciliationContext,
    ReconciliationError,
    ReconciliationRepository,
    ReconciliationService,
)
from app.services.state_machine import StateMachineService
from app.services.webhook_processor import VerifiedWebhookEvent


class MockAuditRepo(AuditRepository):
    def __init__(self):
        self.events = []

    def save_event(self, event_record: dict) -> None:
        self.events.append(event_record)


class MockReconciliationRepo(ReconciliationRepository):
    def __init__(self):
        self.context = ReconciliationContext(
            case_id="CASE_123",
            action_id="ACT_123",
            payment_id="PAY_123",
            current_case_state=RecoveryCaseStatus.PAYMENT_PENDING,
            expected_currency="INR",
            expected_amount_minor=50000,
            gross_invoice_amount_minor=1000000,
            valid_adjustments_minor=0,
            verified_payments_minor_before=0,
            verified_recovered_amount_minor_before=0,
            claimed_disputed_amount_minor=100000,
            verified_disputed_amount_minor=100000,  # Safely recoverable will be 900,000
            is_already_reconciled=False,
        )
        self.saved_results = []

    def get_context_by_provider_identifiers(
        self, provider_payment_link_id: str | None, provider_reference_id: str | None
    ):
        if provider_payment_link_id == "unknown_link":
            return None
        return self.context

    def save_reconciliation(
        self, case_id: str, payment_id: str, new_state: RecoveryCaseStatus, calc_result
    ) -> None:
        self.saved_results.append((case_id, payment_id, new_state, calc_result))


@pytest.fixture
def audit_repo():
    return MockAuditRepo()


@pytest.fixture
def recon_repo():
    return MockReconciliationRepo()


@pytest.fixture
def service(audit_repo, recon_repo):
    audit_svc = AuditService(audit_repo)
    sm_svc = StateMachineService()
    return ReconciliationService(recon_repo, sm_svc, audit_svc)


@pytest.fixture
def base_event():
    return VerifiedWebhookEvent(
        event_id="evt_test",
        event_type="payment_link.paid",
        provider_payment_id="pay_prov_123",
        provider_payment_link_id="link_123",
        provider_reference_id="ref_123",
        amount_minor=50000,
        currency="INR",
        created_at=1000000,
        raw_payload={"secret_key": "hidden"},
    )


def test_valid_partial_payment(service, base_event, audit_repo, recon_repo):
    # Recoverable is 900,000. Payment is 50,000.
    result = service.reconcile_payment(base_event)

    assert result.verified_recovered_amount_minor == 50000
    assert result.remaining_amount_minor == 850000

    saved = recon_repo.saved_results[0]
    assert saved[2] == RecoveryCaseStatus.PARTIALLY_RECOVERED

    # Check audits
    event_types = [e["event_type"] for e in audit_repo.events]
    assert "PAYMENT_CONFIRMED" in event_types
    assert "STATE_TRANSITION" in event_types
    assert "RECONCILIATION_COMPLETED" in event_types

    # Audit secrets check
    for e in audit_repo.events:
        assert "secret_key" not in json.dumps(e["payload_json"])


def test_valid_full_payment(service, base_event, recon_repo):
    recon_repo.context = replace(recon_repo.context, expected_amount_minor=900000)
    event = replace(base_event, amount_minor=900000)

    result = service.reconcile_payment(event)
    assert result.verified_recovered_amount_minor == 900000
    assert result.remaining_amount_minor == 0

    saved = recon_repo.saved_results[0]
    assert saved[2] == RecoveryCaseStatus.FULLY_RECOVERED


def test_amount_mismatch(service, base_event):
    event = replace(base_event, amount_minor=40000)
    with pytest.raises(ReconciliationError, match="Amount mismatch"):
        service.reconcile_payment(event)


def test_currency_mismatch(service, base_event):
    event = replace(base_event, currency="USD")
    with pytest.raises(ReconciliationError, match="Currency mismatch"):
        service.reconcile_payment(event)


def test_unknown_payment(service, base_event):
    event = replace(base_event, provider_payment_link_id="unknown_link")
    with pytest.raises(ReconciliationError, match="Unknown payment or case"):
        service.reconcile_payment(event)


def test_duplicate_payment(service, base_event, recon_repo):
    recon_repo.context = replace(recon_repo.context, is_already_reconciled=True)
    with pytest.raises(ReconciliationError, match="Payment is already reconciled"):
        service.reconcile_payment(base_event)


def test_over_recovery(service, base_event, recon_repo):
    # Recoverable is 900,000. Before payment is 900,000. Payment is 50,000.
    # Total = 950,000, which is > 900,000
    recon_repo.context = replace(recon_repo.context, verified_recovered_amount_minor_before=900000)

    with pytest.raises(ReconciliationError, match="Over-recovery"):
        service.reconcile_payment(base_event)


def test_state_transition_guarded(service, base_event, recon_repo):
    # Try reconciling when the case is CLOSED (terminal)
    recon_repo.context = replace(recon_repo.context, current_case_state=RecoveryCaseStatus.CLOSED)

    with pytest.raises(ReconciliationError, match="State transition failed"):
        service.reconcile_payment(base_event)
