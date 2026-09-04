"""add resilient currency extraction fallback

Revision ID: f6e7d8c9b0a1
Revises: f5e6d7c8b9a0
"""
from alembic import op
import sqlalchemy as sa

revision = "f6e7d8c9b0a1"
down_revision = "f5e6d7c8b9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "supplier_currency_settings",
        sa.Column("fallback_extraction_method", sa.String(24)),
    )
    op.add_column(
        "supplier_currency_settings",
        sa.Column("fallback_extraction_expression", sa.String(1000)),
    )
    op.drop_constraint(
        op.f("ck_supplier_currency_settings_ck_supplier_currency_sett_e406"),
        "supplier_currency_settings",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_supplier_currency_settings_extraction_method_valid"),
        "supplier_currency_settings",
        "extraction_method IN ('JSON_PATH','CSS_SELECTOR','XPATH','REGEX','TEXT_LABEL')",
    )
    op.create_check_constraint(
        op.f("ck_supplier_currency_settings_fallback_extraction_method_valid"),
        "supplier_currency_settings",
        "fallback_extraction_method IS NULL OR fallback_extraction_method IN ('JSON_PATH','CSS_SELECTOR','XPATH','REGEX','TEXT_LABEL')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE supplier_currency_settings SET extraction_method = 'REGEX' "
        "WHERE extraction_method = 'TEXT_LABEL'"
    )
    op.drop_constraint(
        op.f("ck_supplier_currency_settings_fallback_extraction_method_valid"),
        "supplier_currency_settings",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_supplier_currency_settings_extraction_method_valid"),
        "supplier_currency_settings",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_supplier_currency_settings_ck_supplier_currency_sett_e406"),
        "supplier_currency_settings",
        "extraction_method IN ('JSON_PATH','CSS_SELECTOR','XPATH','REGEX')",
    )
    op.drop_column("supplier_currency_settings", "fallback_extraction_expression")
    op.drop_column("supplier_currency_settings", "fallback_extraction_method")
