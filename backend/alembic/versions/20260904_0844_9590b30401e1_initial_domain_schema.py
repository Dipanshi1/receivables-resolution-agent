"""Initial domain schema — all 16 core domain tables.

Revision ID: 9590b30401e1
Revises: (initial)
Create Date: 2026-09-04

Creates the full MVP database schema for the Receivables Resolution Agent:
  merchants, merchant_policies, customers, invoices, invoice_lines,
  recovery_cases, disputes, evidence, agent_runs, resolution_proposals,
  policy_decisions, recovery_actions, payments, outreach, human_approvals,
  audit_events.

All authoritative monetary amounts use BIGINT (integer minor units, paise).
No floating-point types are used for authoritative financial amounts.
All timestamps use TIMESTAMPTZ (timezone-aware).
All primary keys use UUID.
Foreign keys use ON DELETE RESTRICT to preserve financial/audit history.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9590b30401e1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # merchants — root ownership entity
    # ------------------------------------------------------------------
    op.create_table(
        "merchants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_merchants"),
    )

    # ------------------------------------------------------------------
    # merchant_policies — versioned, immutable recovery rules
    # ------------------------------------------------------------------
    op.create_table(
        "merchant_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("max_auto_recovery_amount", sa.BigInteger(), nullable=False),
        sa.Column("max_concession_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_concession_amount", sa.BigInteger(), nullable=False),
        sa.Column("max_touchpoints", sa.Integer(), nullable=False),
        sa.Column("touchpoint_window_days", sa.Integer(), nullable=False),
        sa.Column("quiet_hours_start", sa.Time(), nullable=False),
        sa.Column("quiet_hours_end", sa.Time(), nullable=False),
        sa.Column("high_value_threshold", sa.BigInteger(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("max_auto_recovery_amount >= 0", name="ck_policy_max_auto_recovery"),
        sa.CheckConstraint(
            "max_concession_percent >= 0 AND max_concession_percent <= 100",
            name="ck_policy_concession_percent",
        ),
        sa.CheckConstraint("max_concession_amount >= 0", name="ck_policy_concession_amount"),
        sa.CheckConstraint("max_touchpoints >= 0", name="ck_policy_max_touchpoints"),
        sa.CheckConstraint("touchpoint_window_days > 0", name="ck_policy_touchpoint_window"),
        sa.CheckConstraint("high_value_threshold >= 0", name="ck_policy_high_value_threshold"),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"], ondelete="RESTRICT",
            name="fk_merchant_policies_merchant_id_merchants",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_merchant_policies"),
        sa.UniqueConstraint("merchant_id", "version", name="uq_merchant_policies_version"),
    )

    # ------------------------------------------------------------------
    # customers — merchant-scoped B2B customers
    # ------------------------------------------------------------------
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("gstin", sa.String(32), nullable=True),
        sa.Column("external_customer_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"], ondelete="RESTRICT",
            name="fk_customers_merchant_id_merchants",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
    )
    op.create_index("ix_customers_merchant_id", "customers", ["merchant_id"])
    op.create_index(
        "ix_customers_merchant_external_id", "customers",
        ["merchant_id", "external_customer_id"],
    )

    # ------------------------------------------------------------------
    # invoices — customer financial obligations
    # ------------------------------------------------------------------
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        # BIGINT paise — no float
        sa.Column("total_amount", sa.BigInteger(), nullable=False),
        sa.Column("amount_paid", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("external_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("total_amount >= 0", name="ck_invoices_total_amount"),
        sa.CheckConstraint("amount_paid >= 0", name="ck_invoices_amount_paid_nonneg"),
        sa.CheckConstraint(
            "amount_paid <= total_amount", name="ck_invoices_amount_paid_limit"
        ),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"], ondelete="RESTRICT",
            name="fk_invoices_merchant_id_merchants",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="RESTRICT",
            name="fk_invoices_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_invoices"),
        sa.UniqueConstraint(
            "merchant_id", "invoice_number", name="uq_invoices_merchant_invoice_number"
        ),
    )
    op.create_index("ix_invoices_merchant_id", "invoices", ["merchant_id"])
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("ix_invoices_due_date", "invoices", ["due_date"])
    op.create_index("ix_invoices_status", "invoices", ["status"])

    # ------------------------------------------------------------------
    # invoice_lines — decomposed line items
    # ------------------------------------------------------------------
    op.create_table(
        "invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("product_code", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        # BIGINT paise — no float
        sa.Column("unit_price", sa.BigInteger(), nullable=False),
        sa.Column("tax_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("line_total", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_invoice_lines_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_invoice_lines_unit_price"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_invoice_lines_tax_amount"),
        sa.CheckConstraint("line_total >= 0", name="ck_invoice_lines_line_total"),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["invoices.id"], ondelete="RESTRICT",
            name="fk_invoice_lines_invoice_id_invoices",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_invoice_lines"),
        sa.UniqueConstraint(
            "invoice_id", "line_number", name="uq_invoice_lines_invoice_line_number"
        ),
    )

    # ------------------------------------------------------------------
    # recovery_cases — core workflow state per invoice
    # ------------------------------------------------------------------
    op.create_table(
        "recovery_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("issue_type", sa.String(64), nullable=True),
        sa.Column("risk_level", sa.String(32), nullable=True),
        # All BIGINT paise — no float
        sa.Column(
            "claimed_disputed_amount", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("verified_disputed_amount", sa.BigInteger(), nullable=True),
        sa.Column("collectible_amount", sa.BigInteger(), nullable=True),
        sa.Column("safely_recoverable_amount", sa.BigInteger(), nullable=True),
        sa.Column("recovered_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("remaining_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("resolution_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("touchpoint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("lock_reason", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "claimed_disputed_amount >= 0", name="ck_rc_claimed_disputed_nonneg"
        ),
        sa.CheckConstraint(
            "verified_disputed_amount IS NULL OR verified_disputed_amount >= 0",
            name="ck_rc_verified_disputed_nonneg",
        ),
        sa.CheckConstraint(
            "collectible_amount IS NULL OR collectible_amount >= 0",
            name="ck_rc_collectible_nonneg",
        ),
        sa.CheckConstraint(
            "safely_recoverable_amount IS NULL OR safely_recoverable_amount >= 0",
            name="ck_rc_safely_recoverable_nonneg",
        ),
        sa.CheckConstraint("recovered_amount >= 0", name="ck_rc_recovered_nonneg"),
        sa.CheckConstraint("remaining_amount >= 0", name="ck_rc_remaining_nonneg"),
        sa.CheckConstraint("touchpoint_count >= 0", name="ck_rc_touchpoint_count_nonneg"),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"], ondelete="RESTRICT",
            name="fk_recovery_cases_merchant_id_merchants",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="RESTRICT",
            name="fk_recovery_cases_customer_id_customers",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["invoices.id"], ondelete="RESTRICT",
            name="fk_recovery_cases_invoice_id_invoices",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recovery_cases"),
    )
    op.create_index("ix_recovery_cases_merchant_id", "recovery_cases", ["merchant_id"])
    op.create_index(
        "ix_recovery_cases_merchant_status", "recovery_cases", ["merchant_id", "status"]
    )
    op.create_index("ix_recovery_cases_invoice_id", "recovery_cases", ["invoice_id"])
    op.create_index("ix_recovery_cases_status", "recovery_cases", ["status"])

    # ------------------------------------------------------------------
    # disputes — commercial invoice disputes
    # ------------------------------------------------------------------
    op.create_table(
        "disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("customer_claim", sa.Text(), nullable=False),
        sa.Column("claimed_amount", sa.BigInteger(), nullable=True),
        sa.Column("verified_amount", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"], ["recovery_cases.id"], ondelete="RESTRICT",
            name="fk_disputes_case_id_recovery_cases",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_disputes"),
    )
    op.create_index("ix_disputes_case_id", "disputes", ["case_id"])

    # ------------------------------------------------------------------
    # evidence — business evidence artifacts
    # ------------------------------------------------------------------
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("external_reference", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("structured_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["recovery_cases.id"], ondelete="RESTRICT",
            name="fk_evidence_case_id_recovery_cases",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence"),
    )
    op.create_index("ix_evidence_case_id", "evidence", ["case_id"])
    op.create_index("ix_evidence_type", "evidence", ["type"])

    # ------------------------------------------------------------------
    # agent_runs — AI reasoning execution metadata
    # ------------------------------------------------------------------
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(128), nullable=False),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["recovery_cases.id"], ondelete="RESTRICT",
            name="fk_agent_runs_case_id_recovery_cases",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
    )
    op.create_index("ix_agent_runs_case_id", "agent_runs", ["case_id"])

    # ------------------------------------------------------------------
    # resolution_proposals — AI-generated recovery recommendations
    # ------------------------------------------------------------------
    op.create_table(
        "resolution_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("proposed_amount", sa.BigInteger(), nullable=True),
        sa.Column("reason_code", sa.String(128), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "proposed_amount IS NULL OR proposed_amount >= 0",
            name="ck_proposals_proposed_amount_nonneg",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_proposals_confidence_range"
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["recovery_cases.id"], ondelete="RESTRICT",
            name="fk_resolution_proposals_case_id_recovery_cases",
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"], ["agent_runs.id"], ondelete="RESTRICT",
            name="fk_resolution_proposals_agent_run_id_agent_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_resolution_proposals"),
    )
    op.create_index(
        "ix_resolution_proposals_case_id", "resolution_proposals", ["case_id"]
    )

    # ------------------------------------------------------------------
    # policy_decisions — deterministic policy engine results
    # ------------------------------------------------------------------
    op.create_table(
        "policy_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("checks_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("blocking_reason", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["recovery_cases.id"], ondelete="RESTRICT",
            name="fk_policy_decisions_case_id_recovery_cases",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["resolution_proposals.id"], ondelete="RESTRICT",
            name="fk_policy_decisions_proposal_id_resolution_proposals",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_decisions"),
    )
    op.create_index("ix_policy_decisions_case_id", "policy_decisions", ["case_id"])

    # ------------------------------------------------------------------
    # recovery_actions — controlled execution records
    # ------------------------------------------------------------------
    op.create_table(
        "recovery_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("external_provider", sa.String(64), nullable=True),
        sa.Column("external_reference", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "amount IS NULL OR amount >= 0", name="ck_recovery_actions_amount_nonneg"
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["recovery_cases.id"], ondelete="RESTRICT",
            name="fk_recovery_actions_case_id_recovery_cases",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["resolution_proposals.id"], ondelete="RESTRICT",
            name="fk_recovery_actions_proposal_id_resolution_proposals",
        ),
        sa.ForeignKeyConstraint(
            ["policy_decision_id"], ["policy_decisions.id"], ondelete="RESTRICT",
            name="fk_recovery_actions_policy_decision_id_policy_decisions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recovery_actions"),
    )
    op.create_index("ix_recovery_actions_case_id", "recovery_actions", ["case_id"])

    # ------------------------------------------------------------------
    # payments — provider-confirmed payment records
    # ------------------------------------------------------------------
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recovery_action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("razorpay_payment_id", sa.String(128), nullable=True),
        sa.Column("razorpay_payment_link_id", sa.String(128), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["invoices.id"], ondelete="RESTRICT",
            name="fk_payments_invoice_id_invoices",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["recovery_cases.id"], ondelete="RESTRICT",
            name="fk_payments_case_id_recovery_cases",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_action_id"], ["recovery_actions.id"], ondelete="RESTRICT",
            name="fk_payments_recovery_action_id_recovery_actions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
    )
    op.create_index("ix_payments_case_id", "payments", ["case_id"])
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])
    op.create_index("ix_payments_razorpay_payment_id", "payments", ["razorpay_payment_id"])
    op.create_index(
        "ix_payments_razorpay_link_id", "payments", ["razorpay_payment_link_id"]
    )

    # ------------------------------------------------------------------
    # outreach — contact attempts for touchpoint enforcement
    # ------------------------------------------------------------------
    op.create_table(
        "outreach",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("message_reference", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"], ["recovery_cases.id"], ondelete="RESTRICT",
            name="fk_outreach_case_id_recovery_cases",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outreach"),
    )
    op.create_index("ix_outreach_case_id_sent_at", "outreach", ["case_id", "sent_at"])

    # ------------------------------------------------------------------
    # human_approvals — explicit human authorization records
    # action_fingerprint binds approval to exact action/amount/type.
    # ------------------------------------------------------------------
    op.create_table(
        "human_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_amount", sa.BigInteger(), nullable=True),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("action_fingerprint", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"], ["recovery_cases.id"], ondelete="RESTRICT",
            name="fk_human_approvals_case_id_recovery_cases",
        ),
        sa.ForeignKeyConstraint(
            ["action_id"], ["recovery_actions.id"], ondelete="RESTRICT",
            name="fk_human_approvals_action_id_recovery_actions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_human_approvals"),
    )

    # ------------------------------------------------------------------
    # audit_events — append-only operational history
    # external_event_id enables idempotent webhook processing.
    # ------------------------------------------------------------------
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_type", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=True),
        sa.Column("state_before", sa.String(40), nullable=True),
        sa.Column("state_after", sa.String(40), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("policy_version", sa.String(64), nullable=True),
        sa.Column("external_event_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["recovery_cases.id"], ondelete="RESTRICT",
            name="fk_audit_events_case_id_recovery_cases",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_events_case_id_created_at", "audit_events", ["case_id", "created_at"]
    )
    op.create_index(
        "ix_audit_events_external_event_id", "audit_events", ["external_event_id"]
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("ix_audit_events_external_event_id", table_name="audit_events")
    op.drop_index("ix_audit_events_case_id_created_at", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_table("human_approvals")

    op.drop_index("ix_outreach_case_id_sent_at", table_name="outreach")
    op.drop_table("outreach")

    op.drop_index("ix_payments_razorpay_link_id", table_name="payments")
    op.drop_index("ix_payments_razorpay_payment_id", table_name="payments")
    op.drop_index("ix_payments_invoice_id", table_name="payments")
    op.drop_index("ix_payments_case_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index("ix_recovery_actions_case_id", table_name="recovery_actions")
    op.drop_table("recovery_actions")

    op.drop_index("ix_policy_decisions_case_id", table_name="policy_decisions")
    op.drop_table("policy_decisions")

    op.drop_index("ix_resolution_proposals_case_id", table_name="resolution_proposals")
    op.drop_table("resolution_proposals")

    op.drop_index("ix_agent_runs_case_id", table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_index("ix_evidence_type", table_name="evidence")
    op.drop_index("ix_evidence_case_id", table_name="evidence")
    op.drop_table("evidence")

    op.drop_index("ix_disputes_case_id", table_name="disputes")
    op.drop_table("disputes")

    op.drop_index("ix_recovery_cases_status", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_invoice_id", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_merchant_status", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_merchant_id", table_name="recovery_cases")
    op.drop_table("recovery_cases")

    op.drop_table("invoice_lines")

    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_due_date", table_name="invoices")
    op.drop_index("ix_invoices_customer_id", table_name="invoices")
    op.drop_index("ix_invoices_merchant_id", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_customers_merchant_external_id", table_name="customers")
    op.drop_index("ix_customers_merchant_id", table_name="customers")
    op.drop_table("customers")

    op.drop_table("merchant_policies")
    op.drop_table("merchants")
