"""supplier currency center

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monitor_currency_settings",
        sa.Column("singleton_key", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default="RSD", nullable=False),
        sa.Column("rate_to_rsd", sa.Numeric(20, 8), server_default="1", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("singleton_key", name=op.f("ck_monitor_currency_settings_singleton_true")),
        sa.CheckConstraint("currency_code = 'RSD'", name=op.f("ck_monitor_currency_settings_currency_rsd")),
        sa.CheckConstraint("rate_to_rsd = 1", name=op.f("ck_monitor_currency_settings_rate_one")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monitor_currency_settings")),
        sa.UniqueConstraint("singleton_key", name="uq_monitor_currency_settings_singleton"),
    )
    op.execute("INSERT INTO monitor_currency_settings (id) VALUES (gen_random_uuid())")
    op.create_table(
        "supplier_currency_settings",
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("currency_source", sa.String(16), nullable=False),
        sa.Column("rate_mode", sa.String(16), nullable=False),
        sa.Column("automatic_source_url", sa.String(2000)),
        sa.Column("max_rate_age_hours", sa.Integer(), server_default="48", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name=op.f("ck_supplier_currency_settings_currency_iso_format")),
        sa.CheckConstraint("currency_source IN ('CONFIGURED','PRICE_LIST')", name=op.f("ck_supplier_currency_settings_currency_source_valid")),
        sa.CheckConstraint("rate_mode IN ('FIXED','MANUAL','AUTOMATIC')", name=op.f("ck_supplier_currency_settings_rate_mode_valid")),
        sa.CheckConstraint("max_rate_age_hours BETWEEN 1 AND 8760", name=op.f("ck_supplier_currency_settings_max_age_valid")),
        sa.CheckConstraint("currency_code <> 'RSD' OR rate_mode = 'FIXED'", name=op.f("ck_supplier_currency_settings_rsd_rate_fixed")),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT", name=op.f("fk_supplier_currency_settings_supplier_id_suppliers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_currency_settings")),
    )
    op.create_index("uq_supplier_currency_settings_active", "supplier_currency_settings", ["supplier_id"], unique=True, postgresql_where=sa.text("is_active"))
    op.create_index("ix_supplier_currency_settings_currency_active", "supplier_currency_settings", ["currency_code", "is_active"])
    op.create_table(
        "supplier_exchange_rates",
        sa.Column("currency_setting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rate_to_rsd", sa.Numeric(20, 8), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("evidence_checksum", sa.String(64)),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("rate_to_rsd > 0", name=op.f("ck_supplier_exchange_rates_rate_positive")),
        sa.CheckConstraint("status IN ('VERIFIED','REJECTED')", name=op.f("ck_supplier_exchange_rates_status_valid")),
        sa.CheckConstraint("source_type IN ('FIXED','MANUAL','AUTOMATIC')", name=op.f("ck_supplier_exchange_rates_source_type_valid")),
        sa.ForeignKeyConstraint(["currency_setting_id"], ["supplier_currency_settings.id"], ondelete="RESTRICT", name=op.f("fk_supplier_exchange_rates_currency_setting_id_supplier_currency_settings")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_exchange_rates")),
        sa.UniqueConstraint("currency_setting_id", "effective_at", name="uq_supplier_exchange_rates_setting_effective"),
    )
    op.create_index("ix_supplier_exchange_rates_lookup", "supplier_exchange_rates", ["currency_setting_id", "status", "effective_at"])
    op.create_table(
        "supplier_currency_events",
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency_setting_id", postgresql.UUID(as_uuid=True)),
        sa.Column("exchange_rate_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT", name=op.f("fk_supplier_currency_events_supplier_id_suppliers")),
        sa.ForeignKeyConstraint(["currency_setting_id"], ["supplier_currency_settings.id"], ondelete="RESTRICT", name=op.f("fk_supplier_currency_events_currency_setting_id_supplier_currency_settings")),
        sa.ForeignKeyConstraint(["exchange_rate_id"], ["supplier_exchange_rates.id"], ondelete="RESTRICT", name=op.f("fk_supplier_currency_events_exchange_rate_id_supplier_exchange_rates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_currency_events")),
    )
    op.create_index("ix_supplier_currency_events_supplier_created", "supplier_currency_events", ["supplier_id", "created_at", "id"])
    op.add_column("supplier_snapshots", sa.Column("currency_setting_id", postgresql.UUID(as_uuid=True)))
    op.add_column("supplier_snapshots", sa.Column("exchange_rate_id", postgresql.UUID(as_uuid=True)))
    op.add_column("supplier_snapshots", sa.Column("source_currency", sa.String(3)))
    op.add_column("supplier_snapshots", sa.Column("exchange_rate_to_rsd", sa.Numeric(20, 8)))
    op.create_foreign_key(op.f("fk_supplier_snapshots_currency_setting_id_supplier_currency_settings"), "supplier_snapshots", "supplier_currency_settings", ["currency_setting_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key(op.f("fk_supplier_snapshots_exchange_rate_id_supplier_exchange_rates"), "supplier_snapshots", "supplier_exchange_rates", ["exchange_rate_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint(op.f("fk_supplier_snapshots_exchange_rate_id_supplier_exchange_rates"), "supplier_snapshots", type_="foreignkey")
    op.drop_constraint(op.f("fk_supplier_snapshots_currency_setting_id_supplier_currency_settings"), "supplier_snapshots", type_="foreignkey")
    for column in ("exchange_rate_to_rsd", "source_currency", "exchange_rate_id", "currency_setting_id"):
        op.drop_column("supplier_snapshots", column)
    op.drop_index("ix_supplier_currency_events_supplier_created", table_name="supplier_currency_events")
    op.drop_table("supplier_currency_events")
    op.drop_index("ix_supplier_exchange_rates_lookup", table_name="supplier_exchange_rates")
    op.drop_table("supplier_exchange_rates")
    op.drop_index("ix_supplier_currency_settings_currency_active", table_name="supplier_currency_settings")
    op.drop_index("uq_supplier_currency_settings_active", table_name="supplier_currency_settings")
    op.drop_table("supplier_currency_settings")
    op.drop_table("monitor_currency_settings")
