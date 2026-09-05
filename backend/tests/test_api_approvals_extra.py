from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import RecoveryActionStatus, RecoveryActionType, RecoveryCaseStatus
from app.domain.models import (
    HumanApproval,
    Invoice,
    MerchantPolicy,
    PolicyDecision,
    RecoveryAction,
    RecoveryCase,
    ResolutionProposal,
)
from app.main import app


def _mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _setup_app(session, merchant_id):
    app.dependency_overrides = {}
    from app.api.deps import get_db_session, get_merchant_id

    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_merchant_id] = lambda: merchant_id
    return TestClient(app)


def test_repeated_policy_check_does_not_regress():
    merchant_id = uuid4()
    case_id = uuid4()
    proposal_id = uuid4()
    action_id = uuid4()

    session = _mock_session()

    case = RecoveryCase(
        id=case_id,
        merchant_id=merchant_id,
        invoice_id=uuid4(),
        status=RecoveryCaseStatus.RECOVERY_INITIATED.value,
        claimed_disputed_amount=0,
        recovered_amount=0,
        verified_disputed_amount=0,
        touchpoint_count=0,
        locked=False,
        remaining_amount=1000,
        collectible_amount=1000,
        safely_recoverable_amount=1000,
    )

    proposal = ResolutionProposal(id=proposal_id, case_id=case_id, proposed_amount=500)
    policy_decision = PolicyDecision(
        id=uuid4(),
        case_id=case_id,
        proposal_id=proposal_id,
        decision="HUMAN_APPROVAL_REQUIRED",
        policy_version="1.0",
    )

    action = RecoveryAction(
        id=action_id,
        case_id=case_id,
        proposal_id=proposal_id,
        policy_decision_id=policy_decision.id,
        type=RecoveryActionType.CREATE_PARTIAL_RECOVERY.value,
        amount=500,
        status=RecoveryActionStatus.AUTHORIZED.value,
    )

    invoice = Invoice(currency="INR", total_amount=1000, amount_paid=0, customer_id=uuid4())

    def session_get_mock(model, pk):
        if model == RecoveryCase:
            return case
        if model == Invoice:
            return invoice
        return None

    session.get = AsyncMock(side_effect=session_get_mock)

    def mock_execute_side_effect(*args, **kwargs):
        stmt_str = str(args[0]).lower()
        res = MagicMock()
        if "merchantpolicy" in stmt_str or "merchant_polic" in stmt_str or "version" in stmt_str:
            res.scalars.return_value.first.return_value = MerchantPolicy(
                merchant_id=merchant_id,
                version="1.0",
                max_auto_recovery_amount=100000,
                max_concession_percent=0.0,
                max_concession_amount=0,
                max_touchpoints=5,
                touchpoint_window_days=7,
                quiet_hours_start=datetime.now().time(),
                quiet_hours_end=datetime.now().time(),
                high_value_threshold=1000000,
            )
        elif "resolutionproposal" in stmt_str or "resolution_proposals" in stmt_str:
            res.scalars.return_value.first.return_value = proposal
        elif "recoveryaction" in stmt_str or "recovery_actions" in stmt_str:
            res.scalars.return_value.first.return_value = action
        elif "policydecision" in stmt_str or "policy_decisions" in stmt_str:
            res.scalars.return_value.first.return_value = policy_decision
        else:
            res.scalars.return_value.first.return_value = MerchantPolicy(
                merchant_id=merchant_id,
                version="1.0",
                max_auto_recovery_amount=100000,
                max_concession_percent=0.0,
                max_concession_amount=0,
                max_touchpoints=5,
                touchpoint_window_days=7,
                quiet_hours_start=datetime.now().time(),
                quiet_hours_end=datetime.now().time(),
                high_value_threshold=1000000,
            )
        return res

    session.execute = AsyncMock(side_effect=mock_execute_side_effect)

    with pytest.MonkeyPatch.context() as m:
        import app.api.v1.endpoints.recovery_cases as rc_module

        mock_eval = MagicMock()
        mock_eval.decision.value = "HUMAN_APPROVAL_REQUIRED"
        mock_eval.checks = {}
        mock_eval.reason_code = None

        mock_engine = MagicMock()
        mock_engine.evaluate.return_value = mock_eval
        m.setattr(rc_module, "_policy_engine", mock_engine)

        def assign_ids(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = uuid4()
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime.now(UTC)

        session.flush.side_effect = lambda *args, **kwargs: [
            assign_ids(o[0][0]) for o in session.add.call_args_list
        ]
        client = _setup_app(session, merchant_id)

        response = client.post(
            f"/v1/recovery-cases/{case_id}/policy-check", json={"proposal_id": str(proposal_id)}
        )

        assert response.status_code == 200, response.text

        assert action.status == RecoveryActionStatus.AUTHORIZED.value
        assert action.policy_decision_id == policy_decision.id


def test_duplicate_execute_idempotency():
    merchant_id = uuid4()
    case_id = uuid4()
    proposal_id = uuid4()
    action_id = uuid4()
    approval_id = uuid4()

    session = _mock_session()

    case = RecoveryCase(
        id=case_id,
        merchant_id=merchant_id,
        invoice_id=uuid4(),
        status=RecoveryCaseStatus.PAYMENT_PENDING.value,
        claimed_disputed_amount=0,
        recovered_amount=0,
        verified_disputed_amount=0,
        touchpoint_count=0,
        locked=False,
        remaining_amount=1000,
    )

    proposal = ResolutionProposal(id=proposal_id, case_id=case_id, proposed_amount=500)
    policy_decision = PolicyDecision(
        id=uuid4(),
        case_id=case_id,
        proposal_id=proposal_id,
        decision="HUMAN_APPROVAL_REQUIRED",
        policy_version="1.0",
    )
    approval = HumanApproval(
        id=approval_id, case_id=case_id, action_id=action_id, decision="APPROVED"
    )

    action = RecoveryAction(
        id=action_id,
        case_id=case_id,
        proposal_id=proposal_id,
        policy_decision_id=policy_decision.id,
        type=RecoveryActionType.CREATE_PARTIAL_RECOVERY.value,
        amount=500,
        status=RecoveryActionStatus.PAYMENT_PENDING.value,
    )

    invoice = Invoice(currency="INR", total_amount=1000, amount_paid=0, customer_id=uuid4())

    def session_get_mock(model, pk):
        if model == RecoveryCase:
            return case
        if model == Invoice:
            return invoice
        return None

    session.get = AsyncMock(side_effect=session_get_mock)

    def mock_execute_side_effect(*args, **kwargs):
        stmt_str = str(args[0]).lower()
        res = MagicMock()
        if "resolutionproposal" in stmt_str or "resolution_proposals" in stmt_str:
            res.scalars.return_value.first.return_value = proposal
        elif "policydecision" in stmt_str or "policy_decisions" in stmt_str:
            res.scalars.return_value.first.return_value = policy_decision
        elif "humanapproval" in stmt_str or "human_approvals" in stmt_str:
            res.scalars.return_value.first.return_value = approval
        elif "recoveryaction" in stmt_str or "recovery_actions" in stmt_str:
            res.scalars.return_value.first.return_value = action
        else:
            res.scalars.return_value.first.return_value = None
        return res

    session.execute = AsyncMock(side_effect=mock_execute_side_effect)

    def assign_ids(obj):
        if hasattr(obj, "id") and obj.id is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = datetime.now(UTC)

    session.flush.side_effect = lambda *args, **kwargs: [
        assign_ids(o[0][0]) for o in session.add.call_args_list
    ]
    client = _setup_app(session, merchant_id)

    response = client.post(
        f"/v1/recovery-cases/{case_id}/execute",
        json={"proposal_id": str(proposal_id), "human_approval_id": str(approval_id)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PAYMENT_PENDING"
    assert action.status == "PAYMENT_PENDING"
