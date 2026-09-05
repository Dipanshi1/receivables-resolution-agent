"""Razorpay webhook endpoint.

Reads raw request body BEFORE any JSON parsing.
Verifies HMAC-SHA256 signature via WebhookProcessor.
Uses idempotency to prevent duplicate financial effects.
Drives reconciliation and state machine through existing services.

NEVER trusts client-supplied payment status.
NEVER exposes webhook secret.
"""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.api.errors import raise_domain_error
from app.api.v1.schemas.webhook_schemas import WebhookAckResponse
from app.core.config import get_settings
from app.domain.recovery import AuditEvent, Payment, RecoveryCase
from app.services.audit import AuditService
from app.services.reconciliation import ReconciliationContext, ReconciliationService
from app.services.state_machine import StateMachineService
from app.services.webhook_processor import (
    VerifiedWebhookEvent,
    WebhookProcessor,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# DB-backed idempotency store
# ---------------------------------------------------------------------------


class _SessionIdempotencyStore:
    """In-request idempotency store.

    Webhook event deduplication uses AuditEvent.external_event_id.
    Payment deduplication uses Payment.razorpay_payment_id.
    The sync Protocol interface is satisfied; async calls use asyncio.run()
    within the async route via run_in_executor.
    """

    def __init__(self, processed_events: set[str], processed_payments: set[str]) -> None:
        self._events = processed_events
        self._payments = processed_payments

    def is_processed(self, provider: str, event_id: str) -> bool:
        return event_id in self._events

    def mark_processed(self, provider: str, event_id: str) -> None:
        self._events.add(event_id)

    def is_payment_processed(self, provider: str, provider_payment_id: str) -> bool:
        return provider_payment_id in self._payments

    def mark_payment_processed(self, provider: str, provider_payment_id: str) -> None:
        self._payments.add(provider_payment_id)


class _SessionPaymentLookup:
    """Synchronous payment lookup backed by pre-loaded data from DB."""

    def __init__(self, context_by_link_id: dict) -> None:
        self._ctx = context_by_link_id

    def get_payment_context(
        self, provider_payment_link_id: str | None, provider_reference_id: str | None
    ) -> dict | None:
        if provider_payment_link_id:
            return self._ctx.get(provider_payment_link_id)
        return None


# ---------------------------------------------------------------------------
# DB-backed reconciliation repository (sync protocol)
# ---------------------------------------------------------------------------


class _SessionReconciliationRepo:
    """Captures reconciliation result for async persistence after sync call."""

    def __init__(
        self,
        context_by_link_id: dict,
        raw_context: ReconciliationContext | None,
    ) -> None:
        self._ctx = raw_context
        self._pending_update: dict | None = None

    def get_context_by_provider_identifiers(
        self, provider_payment_link_id: str | None, provider_reference_id: str | None
    ) -> ReconciliationContext | None:
        return self._ctx

    def save_reconciliation(self, case_id, payment_id, new_state, calc_result) -> None:
        # Store pending update for async persistence by the route handler
        self._pending_update = {
            "case_id": case_id,
            "payment_id": payment_id,
            "new_state": new_state,
            "calc_result": calc_result,
        }


# ---------------------------------------------------------------------------
# DB audit repository (sync protocol — fire-and-forget list)
# ---------------------------------------------------------------------------


class _ListAuditRepo:
    """Accumulates audit events in a list; caller persists them async."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def save_event(self, event_record: dict) -> None:
        self.events.append(event_record)


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------


@router.post("/razorpay", response_model=WebhookAckResponse)
async def razorpay_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    x_razorpay_signature: str | None = Header(default=None, alias="x-razorpay-signature"),
) -> WebhookAckResponse:
    """Process a Razorpay webhook event.

    Steps (per webhook-design.md):
    1. Capture raw body BEFORE any JSON parsing.
    2. Reject missing signature immediately.
    3. Verify HMAC-SHA256 signature via WebhookProcessor.
    4. Idempotency check on event ID.
    5. Map provider identifiers to internal Payment/Case.
    6. Amount / currency / binding validation.
    7. Payment-level idempotency.
    8. Reconcile via ReconciliationService (deterministic).
    9. Persist state changes + audit events.
    """
    # --- 1. Capture raw body ---
    raw_body: bytes = await request.body()

    # --- 2. Reject missing signature ---
    if not x_razorpay_signature:
        logger.warning("Webhook received without signature header")
        raise_domain_error("WEBHOOK_SIGNATURE_INVALID", "Missing X-Razorpay-Signature", 400)

    settings = get_settings()
    webhook_secret = settings.razorpay_webhook_secret

    if not webhook_secret:
        # Fail closed if secret is not configured
        logger.error("RAZORPAY_WEBHOOK_SECRET not configured — rejecting webhook")
        raise_domain_error("WEBHOOK_SIGNATURE_INVALID", "Webhook processing unavailable", 500)

    # --- 3. Pre-load idempotency data from DB (async, before sync processing) ---
    # Load all processed external_event_ids from AuditEvent table
    evt_result = await session.execute(
        select(AuditEvent.external_event_id).where(
            AuditEvent.external_event_id.isnot(None)
        )
    )
    processed_event_ids: set[str] = set(
        r for r in evt_result.scalars().all() if r is not None
    )

    # Load all captured razorpay_payment_ids
    pay_result = await session.execute(
        select(Payment.razorpay_payment_id).where(
            Payment.razorpay_payment_id.isnot(None),
            Payment.status == "CAPTURED",
        )
    )
    processed_payment_ids: set[str] = set(
        r for r in pay_result.scalars().all() if r is not None
    )

    # --- 4. Load payment context from DB (async) ---
    # The sync processor needs payment context; load it before entering sync mode.
    # We'll load all relevant payments with link IDs and build a sync lookup map.
    pay_ctx_result = await session.execute(
        select(Payment).where(Payment.razorpay_payment_link_id.isnot(None))
    )
    payments_with_links = pay_ctx_result.scalars().all()

    # Eagerly load related case and invoice for each payment
    payment_context_map: dict = {}
    for p in payments_with_links:
        case_result = await session.execute(
            select(RecoveryCase).where(RecoveryCase.id == p.case_id)
        )
        case = case_result.scalars().first()
        if case is None:
            continue

        from app.domain.invoice import Invoice

        inv_result = await session.execute(
            select(Invoice).where(Invoice.id == p.invoice_id)
        )
        inv = inv_result.scalars().first()
        if inv is None:
            continue

        link_id = str(p.razorpay_payment_link_id)
        payment_context_map[link_id] = {
            "expected_provider_payment_link_id": link_id,
            "expected_provider_reference_id": None,
            "expected_amount_minor": p.amount,
            "expected_currency": p.currency,
            "current_state": case.status,
            "verified_recovered_amount": case.recovered_amount,
            "applicable_recoverable_balance": case.safely_recoverable_amount or 0,
        }

    # Also build ReconciliationContext keyed by link_id for reconciliation step
    recon_context_map: dict[str, ReconciliationContext] = {}
    for p in payments_with_links:
        case_result = await session.execute(
            select(RecoveryCase).where(RecoveryCase.id == p.case_id)
        )
        case = case_result.scalars().first()
        if case is None:
            continue
        from app.domain.enums import RecoveryCaseStatus
        from app.domain.invoice import Invoice

        inv_result = await session.execute(
            select(Invoice).where(Invoice.id == p.invoice_id)
        )
        inv = inv_result.scalars().first()
        if inv is None:
            continue

        link_id = str(p.razorpay_payment_link_id)
        recon_context_map[link_id] = ReconciliationContext(
            case_id=str(case.id),
            action_id=str(p.recovery_action_id),
            payment_id=str(p.id),
            current_case_state=RecoveryCaseStatus(case.status),
            expected_currency=p.currency,
            expected_amount_minor=p.amount,
            gross_invoice_amount_minor=inv.total_amount,
            valid_adjustments_minor=0,
            verified_payments_minor_before=inv.amount_paid,
            verified_recovered_amount_minor_before=case.recovered_amount,
            claimed_disputed_amount_minor=case.claimed_disputed_amount,
            verified_disputed_amount_minor=case.verified_disputed_amount,
            is_already_reconciled=(p.status == "CAPTURED"),
        )

    # --- 5. Run synchronous webhook processing ---
    idempotency_store = _SessionIdempotencyStore(processed_event_ids, processed_payment_ids)
    payment_lookup = _SessionPaymentLookup(payment_context_map)
    audit_repo = _ListAuditRepo()

    processor = WebhookProcessor(
        secret=webhook_secret,
        idempotency_store=idempotency_store,
        payment_lookup=payment_lookup,
        state_machine=None,  # State machine drives via reconciliation service below
    )

    result = processor.process_webhook(raw_body, x_razorpay_signature)

    # --- 6. Handle signature / validation rejection ---
    if not result.success and result.error_message in (
        "Invalid signature",
        "Missing signature",
    ):
        logger.warning("Webhook signature rejected")
        raise_domain_error("WEBHOOK_SIGNATURE_INVALID", "Webhook signature invalid", 400)

    if not result.success:
        # Other failures (malformed payload, incomplete data): log and return 200
        # to prevent Razorpay from retrying non-recoverable errors indefinitely.
        logger.warning("Webhook processing failed safely: %s", result.error_message)
        return WebhookAckResponse(status="ok")

    if result.is_duplicate:
        logger.info("Duplicate webhook event %s — idempotent ack", result.event_id)
        return WebhookAckResponse(status="ok")

    if not result.domain_event_generated or result.verified_event is None:
        # Ignored event type or no domain event — ack OK
        return WebhookAckResponse(status="ok")

    # --- 7. Reconcile payment ---
    verified_event: VerifiedWebhookEvent = result.verified_event
    link_id = verified_event.provider_payment_link_id
    recon_ctx = recon_context_map.get(link_id) if link_id else None

    if recon_ctx is not None:
        recon_audit_repo = _ListAuditRepo()
        recon_audit_svc = AuditService(recon_audit_repo)
        recon_repo = _SessionReconciliationRepo({}, recon_ctx)
        sm_svc = StateMachineService()
        recon_svc = ReconciliationService(recon_repo, sm_svc, recon_audit_svc)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, recon_svc.reconcile_payment, verified_event
            )
        except Exception as exc:
            logger.error("Reconciliation failed for event %s: %s", result.event_id, exc)
            return WebhookAckResponse(status="ok")

        # Persist reconciliation result
        if recon_repo._pending_update:
            upd = recon_repo._pending_update
            case_result = await session.execute(
                select(RecoveryCase).where(RecoveryCase.id == upd["case_id"])
            )
            db_case = case_result.scalars().first()
            if db_case:
                db_case.status = upd["new_state"].value
                db_case.collectible_amount = upd["calc_result"].collectible_amount_minor
                db_case.safely_recoverable_amount = (
                    upd["calc_result"].safely_recoverable_amount_minor
                )
                db_case.recovered_amount = upd["calc_result"].verified_recovered_amount_minor
                db_case.remaining_amount = upd["calc_result"].remaining_amount_minor

            pay_result = await session.execute(
                select(Payment).where(Payment.id == upd["payment_id"])
            )
            db_payment = pay_result.scalars().first()
            if db_payment:
                db_payment.status = "CAPTURED"
                db_payment.razorpay_payment_id = verified_event.provider_payment_id

        # Persist all audit events (from both processor audit_svc and recon_audit_svc)
        all_audit_events = audit_repo.events + recon_audit_repo.events
        for evt in all_audit_events:
            # Only persist if we have a real case_id (not "UNKNOWN")
            if evt.get("case_id") and evt["case_id"] != "UNKNOWN":
                db_audit = AuditEvent(
                    case_id=evt["case_id"],
                    event_type=evt["event_type"],
                    actor_type=evt["actor_type"],
                    actor_id=evt.get("actor_id"),
                    state_before=evt.get("state_before"),
                    state_after=evt.get("state_after"),
                    payload_json=evt.get("payload_json"),
                    policy_version=evt.get("policy_version"),
                    external_event_id=evt.get("external_event_id"),
                )
                session.add(db_audit)

        await session.commit()

    return WebhookAckResponse(status="ok")
