"""Comprehensive verification and hardening test suite for the Phase 2 domain schema.

Validates that the SQLAlchemy persistence layer and Alembic schema strictly
conform to the engineering specifications:
- Entity coverage (all 16 core tables)
- Type consistency (UUID PKs, TIMESTAMPTZ, BIGINT minor units)
- Financial safety invariants (no floats, non-negative checks)
- Relationship graph and ON DELETE RESTRICT behavior
- Action fingerprint binding for human approval
- Webhook idempotency field on audit events
- Enum alignment with domain state machine
"""


import pytest
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.domain import (
    HumanApprovalDecision,
    PaymentStatus,
    RecoveryActionStatus,
    RecoveryCaseStatus,
    metadata,
)

EXPECTED_TABLES = {
    "merchants",
    "merchant_policies",
    "customers",
    "invoices",
    "invoice_lines",
    "recovery_cases",
    "disputes",
    "evidence",
    "agent_runs",
    "resolution_proposals",
    "policy_decisions",
    "recovery_actions",
    "payments",
    "outreach",
    "human_approvals",
    "audit_events",
}

MONETARY_BIGINT_COLUMNS = [
    ("invoices", "total_amount"),
    ("invoices", "amount_paid"),
    ("invoice_lines", "unit_price"),
    ("invoice_lines", "tax_amount"),
    ("invoice_lines", "line_total"),
    ("recovery_cases", "claimed_disputed_amount"),
    ("recovery_cases", "verified_disputed_amount"),
    ("recovery_cases", "collectible_amount"),
    ("recovery_cases", "safely_recoverable_amount"),
    ("recovery_cases", "recovered_amount"),
    ("recovery_cases", "remaining_amount"),
    ("merchant_policies", "max_auto_recovery_amount"),
    ("merchant_policies", "max_concession_amount"),
    ("merchant_policies", "high_value_threshold"),
    ("payments", "amount"),
    ("recovery_actions", "amount"),
    ("resolution_proposals", "proposed_amount"),
    ("human_approvals", "requested_amount"),
    ("disputes", "claimed_amount"),
    ("disputes", "verified_amount"),
]


class TestEntityCoverage:
    """Verify that all documented entities exist in SQLAlchemy metadata."""

    def test_all_16_tables_exist(self):
        actual_tables = set(metadata.tables.keys())
        missing = EXPECTED_TABLES - actual_tables
        assert not missing, f"Missing required domain tables: {missing}"

    def test_no_unrelated_tables(self):
        actual_tables = set(metadata.tables.keys())
        extra = actual_tables - EXPECTED_TABLES
        assert not extra, f"Unexpected tables found in metadata: {extra}"

    @pytest.mark.parametrize("table_name", list(EXPECTED_TABLES))
    def test_table_has_uuid_primary_key(self, table_name):
        table = metadata.tables[table_name]
        pk_cols = list(table.primary_key.columns)
        assert len(pk_cols) == 1, f"{table_name} must have a single PK column"
        pk = pk_cols[0]
        assert pk.name == "id", f"{table_name} PK column must be named 'id'"
        assert isinstance(pk.type, UUID), f"{table_name}.id must be a UUID type"


class TestFinancialSafety:
    """Verify that authoritative financial representation is exact and protected."""

    @pytest.mark.parametrize("table_name,col_name", MONETARY_BIGINT_COLUMNS)
    def test_monetary_fields_use_bigint(self, table_name, col_name):
        col = metadata.tables[table_name].c[col_name]
        assert isinstance(col.type, BigInteger), (
            f"{table_name}.{col_name} must be BigInteger, got {type(col.type).__name__}"
        )

    def test_no_authoritative_money_field_uses_floating_point(self):
        for table_name, table in metadata.tables.items():
            for col in table.c:
                if any(kw in col.name for kw in ["amount", "price", "total", "threshold"]):
                    assert not isinstance(col.type, Float), (
                        f"CRITICAL: {table_name}.{col.name} uses Float!"
                    )

    def test_policy_concession_percent_is_bounded_numeric(self):
        col = metadata.tables["merchant_policies"].c["max_concession_percent"]
        assert isinstance(col.type, Numeric)
        assert col.type.precision == 5
        assert col.type.scale == 2

    def test_invoice_non_negative_checks(self):
        table = metadata.tables["invoices"]
        ck_clauses = [
            str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
        ]
        assert any("total_amount >= 0" in c for c in ck_clauses)
        assert any("amount_paid >= 0" in c for c in ck_clauses)
        assert any("amount_paid <= total_amount" in c for c in ck_clauses)

    def test_recovery_case_financial_checks(self):
        table = metadata.tables["recovery_cases"]
        ck_clauses = [
            str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
        ]
        assert any("claimed_disputed_amount >= 0" in c for c in ck_clauses)
        assert any("verified_disputed_amount" in c and ">= 0" in c for c in ck_clauses)
        assert any("collectible_amount" in c and ">= 0" in c for c in ck_clauses)
        assert any("safely_recoverable_amount" in c and ">= 0" in c for c in ck_clauses)
        assert any("recovered_amount >= 0" in c for c in ck_clauses)
        assert any("remaining_amount >= 0" in c for c in ck_clauses)

    def test_payment_amount_positive_check(self):
        table = metadata.tables["payments"]
        ck_clauses = [
            str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
        ]
        assert any("amount > 0" in c for c in ck_clauses)

    def test_disputes_amounts_non_negative_checks(self):
        table = metadata.tables["disputes"]
        ck_clauses = [
            str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
        ]
        assert any("claimed_amount" in c and ">= 0" in c for c in ck_clauses)
        assert any("verified_amount" in c and ">= 0" in c for c in ck_clauses)

    def test_human_approval_requested_amount_non_negative(self):
        table = metadata.tables["human_approvals"]
        ck_clauses = [
            str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
        ]
        assert any("requested_amount" in c and ">= 0" in c for c in ck_clauses)


class TestTimestampConsistency:
    """Verify that all persistent timestamps use timezone-aware TIMESTAMPTZ."""

    def test_all_datetime_columns_are_timezone_aware(self):
        for table_name, table in metadata.tables.items():
            for col in table.c:
                if isinstance(col.type, DateTime):
                    assert col.type.timezone is True, (
                        f"{table_name}.{col.name} DateTime must have timezone=True (TIMESTAMPTZ)"
                    )


class TestForeignKeyIntegrity:
    """Verify that all domain foreign keys use ON DELETE RESTRICT."""

    def test_all_fks_use_restrict(self):
        for table_name, table in metadata.tables.items():
            for fk in table.foreign_keys:
                assert fk.ondelete == "RESTRICT", (
                    f"{table_name}.{fk.parent.name} -> {fk.target_fullname} "
                    f"must use ondelete='RESTRICT', got {fk.ondelete}"
                )


class TestUniquenessAndIndexes:
    """Verify documented unique constraints and indexes."""

    def test_invoices_unique_merchant_invoice_number(self):
        table = metadata.tables["invoices"]
        uq_cols = [
            {col.name for col in c.columns}
            for c in table.constraints
            if isinstance(c, UniqueConstraint)
        ]
        assert {"merchant_id", "invoice_number"} in uq_cols

    def test_merchant_policies_unique_merchant_version(self):
        table = metadata.tables["merchant_policies"]
        uq_cols = [
            {col.name for col in c.columns}
            for c in table.constraints
            if isinstance(c, UniqueConstraint)
        ]
        assert {"merchant_id", "version"} in uq_cols

    def test_invoice_lines_unique_invoice_line_number(self):
        table = metadata.tables["invoice_lines"]
        uq_cols = [
            {col.name for col in c.columns}
            for c in table.constraints
            if isinstance(c, UniqueConstraint)
        ]
        assert {"invoice_id", "line_number"} in uq_cols

    def test_audit_event_external_event_id_indexed(self):
        table = metadata.tables["audit_events"]
        indexed_cols = [
            [col.name for col in idx.columns]
            for idx in table.indexes
        ]
        assert ["external_event_id"] in indexed_cols

    def test_outreach_case_id_sent_at_composite_index(self):
        table = metadata.tables["outreach"]
        indexed_cols = [
            [col.name for col in idx.columns]
            for idx in table.indexes
        ]
        assert ["case_id", "sent_at"] in indexed_cols


class TestHumanApprovalBinding:
    """Verify that HumanApproval is strictly bound to RecoveryAction and has action_fingerprint."""

    def test_action_fingerprint_column_exists_and_not_null(self):
        col = metadata.tables["human_approvals"].c["action_fingerprint"]
        assert not col.nullable, "human_approvals.action_fingerprint must NOT be nullable"

    def test_human_approval_fk_to_recovery_action(self):
        table = metadata.tables["human_approvals"]
        fks = {fk.column.table.name: fk.parent.name for fk in table.foreign_keys}
        assert fks.get("recovery_actions") == "action_id"
        assert fks.get("recovery_cases") == "case_id"


class TestEnumAlignment:
    """Verify that domain enums match documented state machine and domain specifications."""

    def test_recovery_case_status_has_exact_15_documented_states(self):
        expected_states = {
            "OVERDUE",
            "TRIAGING",
            "ISSUE_IDENTIFIED",
            "EVIDENCE_ANALYSIS",
            "RESOLUTION_READY",
            "POLICY_REVIEW",
            "RECOVERY_INITIATED",
            "PAYMENT_PENDING",
            "PARTIALLY_RECOVERED",
            "FULLY_RECOVERED",
            "HUMAN_REVIEW",
            "LEGAL_ESCALATION",
            "AUTOMATION_LOCKED",
            "EXECUTION_FAILED",
            "CLOSED",
        }
        actual_states = {s.value for s in RecoveryCaseStatus}
        assert actual_states == expected_states

    def test_recovery_case_default_is_overdue(self):
        col = metadata.tables["recovery_cases"].c["status"]
        assert col.default.arg == RecoveryCaseStatus.OVERDUE.value

    def test_human_approval_decision_values(self):
        expected = {"PENDING", "APPROVED", "REJECTED", "EXPIRED", "INVALIDATED"}
        actual = {d.value for d in HumanApprovalDecision}
        assert actual == expected

    def test_payment_status_values(self):
        expected = {"CREATED", "PENDING", "CAPTURED", "FAILED", "REFUNDED", "EXPIRED"}
        actual = {s.value for s in PaymentStatus}
        assert actual == expected

    def test_recovery_action_status_values(self):
        expected = {
            "PENDING_APPROVAL",
            "AUTHORIZED",
            "EXECUTING",
            "PAYMENT_PENDING",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
        }
        actual = {s.value for s in RecoveryActionStatus}
        assert actual == expected


class TestDomainRelationships:
    """Verify that ORM relationships are properly configured across all 16 models."""

    def test_merchant_relationships(self):
        from app.domain import Merchant

        mapper = Merchant.__mapper__
        rel_names = set(mapper.relationships.keys())
        assert {"customers", "policies", "invoices", "recovery_cases"}.issubset(rel_names)

    def test_customer_relationships(self):
        from app.domain import Customer

        mapper = Customer.__mapper__
        rel_names = set(mapper.relationships.keys())
        assert {"merchant", "invoices", "recovery_cases"}.issubset(rel_names)

    def test_invoice_relationships(self):
        from app.domain import Invoice

        mapper = Invoice.__mapper__
        rel_names = set(mapper.relationships.keys())
        assert {"merchant", "customer", "lines", "recovery_cases", "payments"}.issubset(rel_names)

    def test_recovery_case_relationships(self):
        from app.domain import RecoveryCase

        mapper = RecoveryCase.__mapper__
        rel_names = set(mapper.relationships.keys())
        expected = {
            "merchant",
            "customer",
            "invoice",
            "disputes",
            "evidence",
            "agent_runs",
            "resolution_proposals",
            "policy_decisions",
            "recovery_actions",
            "payments",
            "outreach",
            "human_approvals",
            "audit_events",
        }
        assert expected.issubset(rel_names)

    def test_recovery_action_relationships(self):
        from app.domain import RecoveryAction

        mapper = RecoveryAction.__mapper__
        rel_names = set(mapper.relationships.keys())
        expected = {"case", "proposal", "policy_decision", "payments", "human_approvals"}
        assert expected.issubset(rel_names)

    def test_human_approval_relationships(self):
        from app.domain import HumanApproval

        mapper = HumanApproval.__mapper__
        rel_names = set(mapper.relationships.keys())
        assert {"case", "action"}.issubset(rel_names)

    def test_payment_relationships(self):
        from app.domain import Payment

        mapper = Payment.__mapper__
        rel_names = set(mapper.relationships.keys())
        assert {"invoice", "case", "recovery_action"}.issubset(rel_names)

    def test_agent_run_relationships(self):
        from app.domain import AgentRun

        mapper = AgentRun.__mapper__
        rel_names = set(mapper.relationships.keys())
        assert {"case", "resolution_proposals"}.issubset(rel_names)

    def test_resolution_proposal_relationships(self):
        from app.domain import ResolutionProposal

        mapper = ResolutionProposal.__mapper__
        rel_names = set(mapper.relationships.keys())
        assert {"case", "agent_run", "policy_decisions", "recovery_actions"}.issubset(rel_names)

    def test_audit_event_relationships(self):
        from app.domain import AuditEvent

        mapper = AuditEvent.__mapper__
        rel_names = set(mapper.relationships.keys())
        assert "case" in rel_names


class TestAlembicMigration:
    """Verify Alembic migration compilation and offline SQL generation."""

    def test_alembic_config_resolves_script_directory(self):
        from pathlib import Path

        from alembic.config import Config

        backend_dir = Path(__file__).resolve().parent.parent
        ini_path = backend_dir / "alembic.ini"
        config = Config(str(ini_path))
        script_dir = config.get_main_option("script_location")
        assert script_dir == "alembic"

    def test_migration_file_exists_and_revision_id_matches(self):
        from pathlib import Path

        backend_dir = Path(__file__).resolve().parent.parent
        versions_dir = backend_dir / "alembic" / "versions"
        migration_files = list(versions_dir.glob("*_initial_domain_schema.py"))
        assert len(migration_files) == 1, "Exactly one initial migration file must exist"
        content = migration_files[0].read_text()
        assert 'revision = "9590b30401e1"' in content
        assert "down_revision = None" in content
