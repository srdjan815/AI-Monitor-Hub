"""supplier currency automation

Revision ID: e3f4a5b6c7d8
Revises: d0e1f2a3b4c5
"""
from alembic import op
import sqlalchemy as sa

revision = "e3f4a5b6c7d8"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = "supplier_currency_settings"
    op.add_column(table, sa.Column("extraction_method", sa.String(24), server_default="JSON_PATH", nullable=False))
    op.add_column(table, sa.Column("extraction_expression", sa.String(1000)))
    op.add_column(table, sa.Column("decimal_separator", sa.String(1), server_default=".", nullable=False))
    op.add_column(table, sa.Column("daily_check_time", sa.Time(), server_default="06:00:00", nullable=False))
    op.add_column(table, sa.Column("next_check_at", sa.DateTime(timezone=True)))
    op.add_column(table, sa.Column("last_check_at", sa.DateTime(timezone=True)))
    op.add_column(table, sa.Column("last_check_status", sa.String(24)))
    op.add_column(table, sa.Column("last_check_message", sa.String(500)))
    op.create_check_constraint("ck_supplier_currency_settings_foreign_rate_not_fixed", table, "currency_code = 'RSD' OR rate_mode IN ('MANUAL','AUTOMATIC')")
    op.create_check_constraint("ck_supplier_currency_settings_extraction_method_valid", table, "extraction_method IN ('JSON_PATH','CSS_SELECTOR','XPATH','REGEX')")
    op.create_check_constraint("ck_supplier_currency_settings_decimal_separator_valid", table, "decimal_separator IN ('.', ',')")
    op.create_index("ix_supplier_currency_settings_automatic_due", table, ["next_check_at"], postgresql_where=sa.text("is_active AND rate_mode = 'AUTOMATIC'"))
    op.add_column("supplier_exchange_rates", sa.Column("source_excerpt", sa.String(1000)))
    op.add_column("supplier_exchange_rates", sa.Column("source_content_type", sa.String(120)))


def downgrade() -> None:
    op.drop_column("supplier_exchange_rates", "source_content_type")
    op.drop_column("supplier_exchange_rates", "source_excerpt")
    table = "supplier_currency_settings"
    op.drop_index("ix_supplier_currency_settings_automatic_due", table_name=table)
    op.drop_constraint("ck_supplier_currency_settings_decimal_separator_valid", table, type_="check")
    op.drop_constraint("ck_supplier_currency_settings_extraction_method_valid", table, type_="check")
    op.drop_constraint("ck_supplier_currency_settings_foreign_rate_not_fixed", table, type_="check")
    for column in ("last_check_message", "last_check_status", "last_check_at", "next_check_at", "daily_check_time", "decimal_separator", "extraction_expression", "extraction_method"):
        op.drop_column(table, column)
