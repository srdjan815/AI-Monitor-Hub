"""Supplier Incident Center.

Revision ID: a6b7c8d9e0f1
Revises: a5b6c7d8e9f1
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a6b7c8d9e0f1"
down_revision = "a5b6c7d8e9f1"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]


def upgrade() -> None:
    op.execute("CREATE SEQUENCE supplier_incident_code_seq START WITH 1 INCREMENT BY 1")
    op.create_table(
        "supplier_incidents",
        sa.Column("incident_code", sa.String(50), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("source_connection_id", sa.Uuid()),
        sa.Column("incident_type", sa.String(64), nullable=False),
        sa.Column("source_domain", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(4), nullable=False),
        sa.Column("status", sa.String(20), server_default="OPEN", nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("correlation_key", sa.String(255)),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False),
        *[sa.Column(name, sa.DateTime(timezone=True)) for name in ("acknowledged_at", "resolved_at", "dismissed_at", "suppressed_at", "suppression_until", "reopened_at", "due_at")],
        sa.Column("assigned_user_id", sa.String(255)),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("resolved_by", sa.String(255)),
        sa.Column("resolution_code", sa.String(100)),
        sa.Column("resolution_summary", sa.String(1000)),
        sa.Column("source_acquisition_run_id", sa.Uuid()),
        sa.Column("source_snapshot_id", sa.Uuid()),
        sa.Column("source_snapshot_archive_operation_id", sa.Uuid()),
        sa.Column("source_delta_run_id", sa.Uuid()),
        sa.Column("source_delta_item_id", sa.Uuid()),
        sa.Column("source_row_error_id", sa.Uuid()),
        sa.Column("sanitized_context", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')", name=op.f("ck_supplier_incidents_severity_valid")),
        sa.CheckConstraint("priority IN ('P4','P3','P2','P1')", name=op.f("ck_supplier_incidents_priority_valid")),
        sa.CheckConstraint("status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','RESOLVED','DISMISSED','SUPPRESSED')", name=op.f("ck_supplier_incidents_status_valid")),
        sa.CheckConstraint("occurrence_count >= 1", name=op.f("ck_supplier_incidents_occurrence_count_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_incidents")),
        sa.UniqueConstraint("incident_code", name=op.f("uq_supplier_incidents_incident_code")),
        *[sa.ForeignKeyConstraint([column], [target], name=op.f(f"fk_supplier_incidents_{column}_{target.split('.')[0]}"), ondelete=delete) for column, target, delete in (
            ("supplier_id", "suppliers.id", "RESTRICT"), ("source_connection_id", "supplier_sources.id", "RESTRICT"),
            ("source_acquisition_run_id", "supplier_acquisition_runs.id", "RESTRICT"), ("source_snapshot_id", "supplier_snapshots.id", "RESTRICT"),
            ("source_snapshot_archive_operation_id", "supplier_snapshot_archive_operations.id", "RESTRICT"), ("source_delta_run_id", "supplier_delta_runs.id", "RESTRICT"),
            ("source_delta_item_id", "supplier_delta_items.id", "SET NULL"), ("source_row_error_id", "supplier_acquisition_issues.id", "SET NULL"),
        )],
    )
    op.alter_column("supplier_incidents", "incident_code", server_default=sa.text("'INC-' || lpad(nextval('supplier_incident_code_seq'::regclass)::text, 6, '0')"))
    for name, columns in (
        ("ix_supplier_incidents_supplier_status", ["supplier_id", "status"]), ("ix_supplier_incidents_source_status", ["source_connection_id", "status"]),
        ("ix_supplier_incidents_classification", ["source_domain", "incident_type", "severity", "priority"]), ("ix_supplier_incidents_assignment_due", ["assigned_user_id", "due_at"]),
        ("ix_supplier_incidents_detected", ["last_detected_at", "created_at"]), ("ix_supplier_incidents_correlation", ["correlation_key"]),
        ("ix_supplier_incidents_acquisition", ["source_acquisition_run_id"]), ("ix_supplier_incidents_snapshot", ["source_snapshot_id"]), ("ix_supplier_incidents_delta", ["source_delta_run_id"]),
    ):
        op.create_index(name, "supplier_incidents", columns)
    op.create_index("uq_supplier_incidents_active_fingerprint", "supplier_incidents", ["fingerprint"], unique=True, postgresql_where=sa.text("status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','SUPPRESSED')"))
    op.create_table(
        "supplier_incident_events",
        sa.Column("incident_id", sa.Uuid(), nullable=False), sa.Column("event_type", sa.String(50), nullable=False), sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("previous_status", sa.String(20)), sa.Column("current_status", sa.String(20)), sa.Column("event_data", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_incident_events")), sa.ForeignKeyConstraint(["incident_id"], ["supplier_incidents.id"], name=op.f("fk_supplier_incident_events_incident_id_supplier_incidents"), ondelete="RESTRICT"),
    )
    op.create_index("ix_supplier_incident_events_incident_created", "supplier_incident_events", ["incident_id", "created_at", "id"])
    op.create_table(
        "supplier_incident_comments",
        sa.Column("incident_id", sa.Uuid(), nullable=False), sa.Column("body", sa.String(4000), nullable=False), sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_incident_comments")), sa.ForeignKeyConstraint(["incident_id"], ["supplier_incidents.id"], name=op.f("fk_supplier_incident_comments_incident_id_supplier_incidents"), ondelete="RESTRICT"),
    )
    op.create_index("ix_supplier_incident_comments_incident_created", "supplier_incident_comments", ["incident_id", "created_at", "id"])
    op.create_table(
        "supplier_incident_links",
        sa.Column("incident_id", sa.Uuid(), nullable=False), sa.Column("related_incident_id", sa.Uuid(), nullable=False), sa.Column("relationship_type", sa.String(16), nullable=False), sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("incident_id <> related_incident_id", name=op.f("ck_supplier_incident_links_not_self")), sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_incident_links")),
        sa.UniqueConstraint("incident_id", "related_incident_id", "relationship_type", name=op.f("uq_supplier_incident_links_relation")),
        sa.ForeignKeyConstraint(["incident_id"], ["supplier_incidents.id"], name=op.f("fk_supplier_incident_links_incident_id_supplier_incidents"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["related_incident_id"], ["supplier_incidents.id"], name=op.f("fk_supplier_incident_links_related_incident_id_supplier_incidents"), ondelete="RESTRICT"),
    )
    op.create_index("ix_supplier_incident_links_related", "supplier_incident_links", ["related_incident_id"])
    op.create_table(
        "supplier_incident_rules",
        sa.Column("rule_code", sa.String(100), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("source_domain", sa.String(32), nullable=False),
        sa.Column("incident_type", sa.String(64), nullable=False), sa.Column("signal_code", sa.String(100)), sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("minimum_severity", sa.String(16), server_default="INFO", nullable=False), sa.Column("resulting_severity", sa.String(16), nullable=False), sa.Column("default_priority", sa.String(4), nullable=False),
        sa.Column("threshold_configuration", postgresql.JSONB(), server_default="{}", nullable=False), sa.Column("deduplication_window_hours", sa.Integer()),
        sa.Column("auto_reopen", sa.Boolean(), server_default=sa.true(), nullable=False), sa.Column("suppression_compatible", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("supplier_id", sa.Uuid()), sa.Column("source_connection_id", sa.Uuid()), sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False), *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_incident_rules")), sa.UniqueConstraint("rule_code", name=op.f("uq_supplier_incident_rules_rule_code")),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], name=op.f("fk_supplier_incident_rules_supplier_id_suppliers"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_connection_id"], ["supplier_sources.id"], name=op.f("fk_supplier_incident_rules_source_connection_id_supplier_sources"), ondelete="CASCADE"),
    )
    op.create_index("ix_supplier_incident_rules_scope", "supplier_incident_rules", ["source_connection_id", "supplier_id", "source_domain", "signal_code", "enabled"])


def downgrade() -> None:
    for table in ("supplier_incident_links", "supplier_incident_comments", "supplier_incident_events", "supplier_incident_rules", "supplier_incidents"):
        op.drop_table(table)
    op.execute("DROP SEQUENCE supplier_incident_code_seq")
