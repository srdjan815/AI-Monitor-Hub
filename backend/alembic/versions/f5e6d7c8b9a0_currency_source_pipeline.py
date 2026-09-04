"""bind currency to source and add pre-fetch phase

Revision ID: f5e6d7c8b9a0
Revises: e3f4a5b6c7d8
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f5e6d7c8b9a0"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("supplier_sources", sa.Column("portal_supplier_code", sa.String(128)))
    op.add_column("supplier_currency_settings", sa.Column("source_connection_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        op.f("fk_supplier_currency_settings_source_connection_id_supplier_sources"),
        "supplier_currency_settings", "supplier_sources",
        ["source_connection_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(
        "ix_supplier_currency_settings_source_connection",
        "supplier_currency_settings", ["source_connection_id"],
    )
    op.drop_constraint(
        op.f("ck_supplier_source_pipeline_runs_phase_valid"),
        "supplier_source_pipeline_runs", type_="check",
    )
    op.create_check_constraint(
        op.f("ck_supplier_source_pipeline_runs_phase_valid"),
        "supplier_source_pipeline_runs",
        "current_phase IN ('CURRENCY_RATE','FETCH','ARTIFACT_SAVE','TECHNICAL_VALIDATE','SCHEMA_ANALYZE','SCHEMA_COMPARE','MAPPING','BUSINESS_VALIDATE','STAGING','COMMIT','SNAPSHOT','DELTA','INCIDENT')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_supplier_source_pipeline_runs_phase_valid"),
        "supplier_source_pipeline_runs", type_="check",
    )
    op.create_check_constraint(
        op.f("ck_supplier_source_pipeline_runs_phase_valid"),
        "supplier_source_pipeline_runs",
        "current_phase IN ('FETCH','ARTIFACT_SAVE','TECHNICAL_VALIDATE','SCHEMA_ANALYZE','SCHEMA_COMPARE','MAPPING','BUSINESS_VALIDATE','STAGING','COMMIT','SNAPSHOT','DELTA','INCIDENT')",
    )
    op.drop_index("ix_supplier_currency_settings_source_connection", table_name="supplier_currency_settings")
    op.drop_constraint(
        op.f("fk_supplier_currency_settings_source_connection_id_supplier_sources"),
        "supplier_currency_settings", type_="foreignkey",
    )
    op.drop_column("supplier_currency_settings", "source_connection_id")
    op.drop_column("supplier_sources", "portal_supplier_code")
