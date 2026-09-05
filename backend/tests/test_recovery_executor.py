import uuid

import pytest

from app.domain.enums import RecoveryActionType, RecoveryCaseStatus
from app.services.razorpay_adapter import MockPaymentProvider
from app.services.recovery_executor import ExecutionInput, RecoveryExecutor


@pytest.fixture
def valid_input():
    return ExecutionInput(
        action_id=str(uuid.uuid4()),
        action_type=RecoveryActionType.CREATE_PAYMENT_LINK,
        amount_minor=9000000,
        currency="INR",
        case_id="CASE-123",
        merchant_id="MERCH-123",
        invoice_id="INV-123",
        current_case_state=RecoveryCaseStatus.RECOVERY_INITIATED,
        is_legal_locked=False,
        is_automation_locked=False,
        verified_collectible_amount_minor=9000000,
        safely_recoverable_amount_minor=9000000,
        autonomous_authority_minor=5000000,
        is_policy_approved=True,
        has_valid_human_approval=True,
        action_already_executed=False,
    )


def test_executor_success(valid_input):
    provider = MockPaymentProvider()
    executor = RecoveryExecutor(provider)

    result = executor.execute_action(valid_input)
    assert result.success is True
    assert result.provider_id is not None
    assert result.payment_link_url is not None
    assert result.error_message is None


def test_executor_rejects_unauthorized_action(valid_input):
    from dataclasses import replace

    provider = MockPaymentProvider()
    executor = RecoveryExecutor(provider)

    invalid_input = replace(valid_input, is_policy_approved=False)
    result = executor.execute_action(invalid_input)

    assert result.success is False
    assert result.provider_id is None
    assert "Policy decision does not approve" in result.error_message


def test_executor_rejects_invalid_amount(valid_input):
    from dataclasses import replace

    provider = MockPaymentProvider()
    executor = RecoveryExecutor(provider)

    invalid_input = replace(valid_input, amount_minor=10000000)  # greater than collectible
    result = executor.execute_action(invalid_input)

    assert result.success is False
    assert "exceeds verified collectible" in result.error_message


def test_executor_rejects_no_human_approval(valid_input):
    from dataclasses import replace

    provider = MockPaymentProvider()
    executor = RecoveryExecutor(provider)

    invalid_input = replace(valid_input, has_valid_human_approval=False)  # amount 9M > authority 5M
    result = executor.execute_action(invalid_input)

    assert result.success is False
    assert "exceeds autonomous authority" in result.error_message


def test_executor_allows_within_authority(valid_input):
    from dataclasses import replace

    provider = MockPaymentProvider()
    executor = RecoveryExecutor(provider)

    valid_input_auth = replace(
        valid_input,
        amount_minor=4000000,
        verified_collectible_amount_minor=4000000,
        safely_recoverable_amount_minor=4000000,
        has_valid_human_approval=False,
    )
    result = executor.execute_action(valid_input_auth)

    assert result.success is True


def test_executor_rejects_locked_case(valid_input):
    from dataclasses import replace

    provider = MockPaymentProvider()
    executor = RecoveryExecutor(provider)

    invalid_input = replace(valid_input, is_legal_locked=True)
    result = executor.execute_action(invalid_input)

    assert result.success is False
    assert "legally locked" in result.error_message


def test_executor_rejects_duplicate_execution(valid_input):
    from dataclasses import replace

    provider = MockPaymentProvider()
    executor = RecoveryExecutor(provider)

    invalid_input = replace(valid_input, action_already_executed=True)
    result = executor.execute_action(invalid_input)

    assert result.success is False
    assert "already been executed" in result.error_message


def test_executor_provider_failure(valid_input):
    provider = MockPaymentProvider(failure_mode=True)
    executor = RecoveryExecutor(provider)

    result = executor.execute_action(valid_input)

    assert result.success is False
    assert "Simulated provider failure" in result.error_message


def test_executor_rejects_non_inr(valid_input):
    from dataclasses import replace

    provider = MockPaymentProvider()
    executor = RecoveryExecutor(provider)

    invalid_input = replace(valid_input, currency="USD")
    result = executor.execute_action(invalid_input)

    assert result.success is False
    assert "Currency USD not supported" in result.error_message


def test_executor_idempotency(valid_input):
    provider = MockPaymentProvider()
    executor = RecoveryExecutor(provider)

    result1 = executor.execute_action(valid_input)
    assert result1.success is True

    # Second call with same inputs should return cached result
    result2 = executor.execute_action(valid_input)
    assert result2.success is True
    assert result2.provider_id == result1.provider_id

    # The MockPaymentProvider increments IDs, so if it made a second call,
    # the provider_id would be different.
    assert result2.provider_id == "plink_mock_0001"


def test_executor_idempotency_collision(valid_input):
    from dataclasses import replace

    provider = MockPaymentProvider()
    executor = RecoveryExecutor(provider)

    result1 = executor.execute_action(valid_input)
    assert result1.success is True

    # Second call with same action_id but different amount
    invalid_input = replace(valid_input, amount_minor=1000)
    result2 = executor.execute_action(invalid_input)

    assert result2.success is False
    assert "Idempotency key collision" in result2.error_message
