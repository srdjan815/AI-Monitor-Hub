"""Supplier Acquisition Engine.

Revision ID: a3b4c5d6e7f8
Revises: a2b3c4d5e6f7
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a3b4c5d6e7f8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.execute(
        "CREATE SEQUENCE supplier_acquisition_code_seq START WITH 1 INCREMENT BY 1"
    )
    op.create_table(
        "supplier_acquisition_runs",
        sa.Column("acquisition_code", sa.String(length=50), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("source_connection_id", sa.Uuid(), nullable=False),
        sa.Column("schema_profile_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_profile_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version_reference", sa.Integer(), nullable=False),
        sa.Column("mapping_version_reference", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=True),
        sa.Column("artifact_reference", sa.String(length=1000), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("total_record_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "accepted_record_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "rejected_record_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("warning_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.String(length=1000), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "trigger_type IN ('MANUAL','API_REQUEST','MANUAL_UPLOAD')",
            name=op.f("ck_supplier_acquisition_runs_trigger_type_valid"),
        ),
        sa.CheckConstraint(
            "status IN "
            "('PENDING','RUNNING','SUCCEEDED','PARTIALLY_SUCCEEDED','FAILED','CANCELLED')",
            name=op.f("ck_supplier_acquisition_runs_status_valid"),
        ),
        sa.CheckConstraint(
            "total_record_count >= 0 AND accepted_record_count >= 0 "
            "AND rejected_record_count >= 0 AND warning_count >= 0 "
            "AND error_count >= 0",
            name=op.f("ck_supplier_acquisition_runs_counts_nonnegative"),
        ),
        sa.CheckConstraint(
            "artifact_size_bytes IS NULL OR artifact_size_bytes >= 0",
            name=op.f("ck_supplier_acquisition_runs_artifact_size_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_supplier_acquisition_runs_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_connection_id"],
            ["supplier_sources.id"],
            name=op.f(
                "fk_supplier_acquisition_runs_source_connection_id_supplier_sources"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["schema_profile_id"],
            ["supplier_schema_profiles.id"],
            name=op.f(
                "fk_supplier_acquisition_runs_schema_profile_id_supplier_schema_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["mapping_profile_id"],
            ["supplier_mapping_profiles.id"],
            name=op.f(
                "fk_supplier_acquisition_runs_mapping_profile_id_supplier_mapping_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_acquisition_runs")),
        sa.UniqueConstraint(
            "acquisition_code",
            name=op.f("uq_supplier_acquisition_runs_acquisition_code"),
        ),
    )
    op.alter_column(
        "supplier_acquisition_runs",
        "acquisition_code",
        server_default=sa.text(
            "'ACQ-' || lpad(nextval('supplier_acquisition_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    op.create_index(
        "uq_supplier_acquisition_runs_source_idempotency",
        "supplier_acquisition_runs",
        ["source_connection_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "ix_supplier_acquisition_runs_supplier_created",
        "supplier_acquisition_runs",
        ["supplier_id", "created_at", "id"],
    )
    op.create_index(
        "ix_supplier_acquisition_runs_source_status",
        "supplier_acquisition_runs",
        ["source_connection_id", "status"],
    )
    op.create_table(
        "supplier_staged_acquisition_records",
        sa.Column("acquisition_run_id", sa.Uuid(), nullable=False),
        sa.Column("record_number", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=True),
        sa.Column("source_identifier", sa.Text(), nullable=True),
        sa.Column(
            "raw_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "mapped_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("warning_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "record_number >= 1",
            name=op.f("ck_supplier_staged_acquisition_records_record_number_positive"),
        ),
        sa.CheckConstraint(
            "validation_status IN ('ACCEPTED','REJECTED')",
            name=op.f(
                "ck_supplier_staged_acquisition_records_validation_status_valid"
            ),
        ),
        sa.CheckConstraint(
            "warning_count >= 0 AND error_count >= 0",
            name=op.f("ck_supplier_staged_acquisition_records_counts_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_run_id"],
            ["supplier_acquisition_runs.id"],
            name=op.f(
                "fk_supplier_staged_acquisition_records_acquisition_run_id_supplier_acquisition_runs"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_supplier_staged_acquisition_records"),
        ),
        sa.UniqueConstraint(
            "acquisition_run_id",
            "record_number",
            name=op.f("uq_supplier_staged_records_run_number"),
        ),
    )
    op.create_index(
        "ix_supplier_staged_records_run_status_number",
        "supplier_staged_acquisition_records",
        ["acquisition_run_id", "validation_status", "record_number"],
    )
    op.create_table(
        "supplier_acquisition_issues",
        sa.Column("acquisition_run_id", sa.Uuid(), nullable=False),
        sa.Column("staged_record_id", sa.Uuid(), nullable=True),
        sa.Column("record_number", sa.Integer(), nullable=False),
        sa.Column("schema_field_id", sa.Uuid(), nullable=True),
        sa.Column("mapping_rule_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column(
            "technical_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('WARNING','ERROR')",
            name=op.f("ck_supplier_acquisition_issues_severity_valid"),
        ),
        sa.CheckConstraint(
            "record_number >= 1",
            name=op.f("ck_supplier_acquisition_issues_record_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_run_id"],
            ["supplier_acquisition_runs.id"],
            name=op.f(
                "fk_supplier_acquisition_issues_acquisition_run_id_supplier_acquisition_runs"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["staged_record_id"],
            ["supplier_staged_acquisition_records.id"],
            name=op.f(
                "fk_supplier_acquisition_issues_staged_record_id_supplier_staged_acquisition_records"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["schema_field_id"],
            ["supplier_schema_fields.id"],
            name=op.f(
                "fk_supplier_acquisition_issues_schema_field_id_supplier_schema_fields"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["mapping_rule_id"],
            ["supplier_mapping_rules.id"],
            name=op.f(
                "fk_supplier_acquisition_issues_mapping_rule_id_supplier_mapping_rules"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_acquisition_issues")),
    )
    op.create_index(
        "ix_supplier_acquisition_issues_run_record",
        "supplier_acquisition_issues",
        ["acquisition_run_id", "record_number", "id"],
    )
    op.create_index(
        "ix_supplier_acquisition_issues_run_severity",
        "supplier_acquisition_issues",
        ["acquisition_run_id", "severity"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_acquisition_issues_run_severity",
        table_name="supplier_acquisition_issues",
    )
    op.drop_index(
        "ix_supplier_acquisition_issues_run_record",
        table_name="supplier_acquisition_issues",
    )
    op.drop_table("supplier_acquisition_issues")
    op.drop_index(
        "ix_supplier_staged_records_run_status_number",
        table_name="supplier_staged_acquisition_records",
    )
    op.drop_table("supplier_staged_acquisition_records")
    for name in (
        "ix_supplier_acquisition_runs_source_status",
        "ix_supplier_acquisition_runs_supplier_created",
        "uq_supplier_acquisition_runs_source_idempotency",
    ):
        op.drop_index(name, table_name="supplier_acquisition_runs")
    op.drop_table("supplier_acquisition_runs")
    op.execute("DROP SEQUENCE supplier_acquisition_code_seq")
