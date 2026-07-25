"""Supplier Delta Engine.

Revision ID: a5b6c7d8e9f1
Revises: a4b5c6d7e8f9
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a5b6c7d8e9f1"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE SEQUENCE supplier_delta_code_seq START WITH 1 INCREMENT BY 1")
    op.create_table(
        "supplier_delta_runs",
        sa.Column("delta_code", sa.String(50), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("source_connection_id", sa.Uuid(), nullable=False),
        sa.Column("previous_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("current_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("previous_snapshot_fingerprint", sa.String(64), nullable=False),
        sa.Column("current_snapshot_fingerprint", sa.String(64), nullable=False),
        sa.Column("previous_schema_profile_id", sa.Uuid(), nullable=False),
        sa.Column("current_schema_profile_id", sa.Uuid(), nullable=False),
        sa.Column("previous_mapping_profile_id", sa.Uuid(), nullable=False),
        sa.Column("current_mapping_profile_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("comparison_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("idempotency_key", sa.String(255)),
        *[sa.Column(name, sa.Integer(), server_default="0", nullable=False) for name in (
            "total_previous_items", "total_current_items", "added_items", "removed_items",
            "modified_items", "unchanged_items", "price_increased_items",
            "price_decreased_items", "price_unchanged_items", "stock_increased_items",
            "stock_decreased_items", "became_available_items", "became_unavailable_items",
            "image_changed_items", "identifier_changed_items", "warning_count", "error_count",
        )],
        sa.Column("anomaly_signals", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("failure_message", sa.String(1000)),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')", name=op.f("ck_supplier_delta_runs_status_valid")),
        sa.CheckConstraint("comparison_version >= 1", name=op.f("ck_supplier_delta_runs_comparison_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_delta_runs")),
        sa.UniqueConstraint("delta_code", name=op.f("uq_supplier_delta_runs_delta_code")),
        *[
            sa.ForeignKeyConstraint([column], [target], name=op.f(f"fk_supplier_delta_runs_{column}_{target.split('.')[0]}"), ondelete="RESTRICT")
            for column, target in (
                ("supplier_id", "suppliers.id"), ("source_connection_id", "supplier_sources.id"),
                ("previous_snapshot_id", "supplier_snapshots.id"), ("current_snapshot_id", "supplier_snapshots.id"),
                ("previous_schema_profile_id", "supplier_schema_profiles.id"), ("current_schema_profile_id", "supplier_schema_profiles.id"),
                ("previous_mapping_profile_id", "supplier_mapping_profiles.id"), ("current_mapping_profile_id", "supplier_mapping_profiles.id"),
            )
        ],
    )
    op.alter_column("supplier_delta_runs", "delta_code", server_default=sa.text("'DLT-' || lpad(nextval('supplier_delta_code_seq'::regclass)::text, 6, '0')"))
    for name, columns in (
        ("ix_supplier_delta_runs_supplier_created", ["supplier_id", "created_at"]),
        ("ix_supplier_delta_runs_source_created", ["source_connection_id", "created_at"]),
        ("ix_supplier_delta_runs_previous_snapshot", ["previous_snapshot_id"]),
        ("ix_supplier_delta_runs_current_snapshot", ["current_snapshot_id"]),
        ("ix_supplier_delta_runs_status_created", ["status", "created_at"]),
    ):
        op.create_index(name, "supplier_delta_runs", columns)
    op.create_index("uq_supplier_delta_runs_successful_pair", "supplier_delta_runs", ["previous_snapshot_id", "current_snapshot_id", "comparison_version"], unique=True, postgresql_where=sa.text("status = 'SUCCEEDED'"))
    op.create_table(
        "supplier_delta_items",
        sa.Column("delta_run_id", sa.Uuid(), nullable=False),
        sa.Column("change_type", sa.String(16), nullable=False),
        sa.Column("matching_key_type", sa.String(32), nullable=False),
        sa.Column("matching_key_value", sa.Text(), nullable=False),
        sa.Column("previous_snapshot_item_id", sa.Uuid()),
        sa.Column("current_snapshot_item_id", sa.Uuid()),
        sa.Column("previous_item_fingerprint", sa.String(64)),
        sa.Column("current_item_fingerprint", sa.String(64)),
        sa.Column("changed_field_count", sa.Integer(), server_default="0", nullable=False),
        *[sa.Column(name, sa.Boolean(), server_default=sa.false(), nullable=False) for name in ("has_price_change", "has_stock_change", "has_image_change", "has_identifier_change")],
        sa.Column("change_summary", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("anomaly_flags", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_delta_items")),
        sa.ForeignKeyConstraint(["delta_run_id"], ["supplier_delta_runs.id"], name=op.f("fk_supplier_delta_items_delta_run_id_supplier_delta_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_snapshot_item_id"], ["supplier_snapshot_items.id"], name=op.f("fk_supplier_delta_items_previous_snapshot_item_id_supplier_snapshot_items"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_snapshot_item_id"], ["supplier_snapshot_items.id"], name=op.f("fk_supplier_delta_items_current_snapshot_item_id_supplier_snapshot_items"), ondelete="SET NULL"),
    )
    op.create_index("ix_supplier_delta_items_run_type", "supplier_delta_items", ["delta_run_id", "change_type"])
    op.create_index("ix_supplier_delta_items_matching_key", "supplier_delta_items", ["delta_run_id", "matching_key_type", "matching_key_value"])
    op.create_index("ix_supplier_delta_items_flags", "supplier_delta_items", ["delta_run_id", "has_price_change", "has_stock_change", "has_image_change", "has_identifier_change"])
    op.create_table(
        "supplier_delta_field_changes",
        sa.Column("delta_item_id", sa.Uuid(), nullable=False),
        sa.Column("field_path", sa.String(1000), nullable=False),
        sa.Column("field_role", sa.String(50)),
        sa.Column("change_type", sa.String(24), nullable=False),
        sa.Column("previous_value_type", sa.String(32)),
        sa.Column("current_value_type", sa.String(32)),
        sa.Column("previous_value_hash", sa.String(64)),
        sa.Column("current_value_hash", sa.String(64)),
        sa.Column("previous_value_preview", sa.String(500)),
        sa.Column("current_value_preview", sa.String(500)),
        sa.Column("previous_numeric_value", sa.Numeric(38, 12)),
        sa.Column("current_numeric_value", sa.Numeric(38, 12)),
        sa.Column("absolute_numeric_change", sa.Numeric(38, 12)),
        sa.Column("percentage_numeric_change", sa.Numeric(38, 12)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_delta_field_changes")),
        sa.ForeignKeyConstraint(["delta_item_id"], ["supplier_delta_items.id"], name=op.f("fk_supplier_delta_field_changes_delta_item_id_supplier_delta_items"), ondelete="CASCADE"),
    )
    op.create_index("ix_supplier_delta_field_changes_item_path", "supplier_delta_field_changes", ["delta_item_id", "field_path"])


def downgrade() -> None:
    op.drop_table("supplier_delta_field_changes")
    op.drop_table("supplier_delta_items")
    op.drop_table("supplier_delta_runs")
    op.execute("DROP SEQUENCE supplier_delta_code_seq")
