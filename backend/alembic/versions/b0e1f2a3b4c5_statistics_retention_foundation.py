"""Durable price observations and configurable retention foundation.

Revision ID: b0e1f2a3b4c5
Revises: a9d0e1f2a3b4
"""

from alembic import op
import sqlalchemy as sa

revision = "b0e1f2a3b4c5"
down_revision = "a9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_data_retention_policies",
        sa.Column("source_connection_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("staging_retention_days", sa.Integer(), nullable=False),
        sa.Column("snapshot_online_days", sa.Integer(), nullable=False),
        sa.Column("minimum_online_snapshots", sa.Integer(), nullable=False),
        sa.Column("cleanup_batch_size", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "cleanup_batch_size BETWEEN 1 AND 10000",
            name=op.f("ck_supplier_data_retention_policies_cleanup_batch_size_valid"),
        ),
        sa.CheckConstraint(
            "minimum_online_snapshots BETWEEN 2 AND 100",
            name=op.f(
                "ck_supplier_data_retention_policies_minimum_online_snapshots_valid"
            ),
        ),
        sa.CheckConstraint(
            "snapshot_online_days BETWEEN 1 AND 3650",
            name=op.f("ck_supplier_data_retention_policies_snapshot_online_days_valid"),
        ),
        sa.CheckConstraint(
            "staging_retention_days BETWEEN 1 AND 3650",
            name=op.f(
                "ck_supplier_data_retention_policies_staging_retention_days_valid"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["source_connection_id"],
            ["supplier_sources.id"],
            name=op.f(
                "fk_supplier_data_retention_policies_source_connection_id_supplier_sources"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_data_retention_policies")),
        sa.UniqueConstraint(
            "source_connection_id", name="uq_supplier_retention_policy_source"
        ),
    )
    op.create_table(
        "supplier_price_observations",
        sa.Column("snapshot_id", sa.Uuid()),
        sa.Column("snapshot_item_id", sa.Uuid()),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("source_connection_id", sa.Uuid(), nullable=False),
        sa.Column("product_code", sa.Text(), nullable=False),
        sa.Column("product_code_normalized", sa.Text(), nullable=False),
        sa.Column("identity_key", sa.Text(), nullable=False),
        sa.Column("ean", sa.Text()),
        sa.Column("product_name", sa.Text()),
        sa.Column("category_name", sa.Text()),
        sa.Column("source_currency", sa.String(3), nullable=False),
        sa.Column("source_price", sa.Numeric(20, 6)),
        sa.Column("exchange_rate_to_rsd", sa.Numeric(20, 8)),
        sa.Column("price_rsd", sa.Numeric(20, 2), nullable=False),
        sa.Column("stock", sa.Numeric(20, 4)),
        sa.Column("item_fingerprint", sa.String(64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "exchange_rate_to_rsd IS NULL OR exchange_rate_to_rsd > 0",
            name=op.f("ck_supplier_price_observations_exchange_rate_positive"),
        ),
        sa.CheckConstraint(
            "price_rsd >= 0",
            name=op.f("ck_supplier_price_observations_price_rsd_nonnegative"),
        ),
        sa.CheckConstraint(
            "source_price IS NULL OR source_price >= 0",
            name=op.f("ck_supplier_price_observations_source_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "stock IS NULL OR stock >= 0",
            name=op.f("ck_supplier_price_observations_stock_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["supplier_snapshots.id"],
            name=op.f("fk_supplier_price_observations_snapshot_id_supplier_snapshots"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_item_id"],
            ["supplier_snapshot_items.id"],
            name=op.f(
                "fk_supplier_price_observations_snapshot_item_id_supplier_snapshot_items"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_connection_id"],
            ["supplier_sources.id"],
            name=op.f(
                "fk_supplier_price_observations_source_connection_id_supplier_sources"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_supplier_price_observations_supplier_id_suppliers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_price_observations")),
        sa.UniqueConstraint(
            "snapshot_item_id", name="uq_supplier_price_observations_snapshot_item"
        ),
    )
    op.create_index(
        "ix_supplier_price_observations_supplier_observed",
        "supplier_price_observations",
        ["supplier_id", "observed_at", "id"],
    )
    op.create_index(
        "ix_supplier_price_observations_source_product_observed",
        "supplier_price_observations",
        ["source_connection_id", "product_code_normalized", "observed_at"],
    )
    op.create_index(
        "ix_supplier_price_observations_ean_observed",
        "supplier_price_observations",
        ["ean", "observed_at"],
    )
    op.create_index(
        "ix_supplier_price_observations_category_observed",
        "supplier_price_observations",
        ["category_name", "observed_at"],
    )
    op.create_table(
        "supplier_retention_runs",
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("staging_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "candidate_staging_rows",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "candidate_snapshots", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "preserved_observations",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "deleted_staging_rows", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column(
            "offloaded_snapshot_items",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("failure_message", sa.String(1000)),
        sa.Column("notes", sa.Text()),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "candidate_staging_rows >= 0 AND candidate_snapshots >= 0 AND preserved_observations >= 0 AND deleted_staging_rows >= 0 AND offloaded_snapshot_items >= 0",
            name=op.f("ck_supplier_retention_runs_counts_nonnegative"),
        ),
        sa.CheckConstraint(
            "status IN ('PREVIEWED','RUNNING','SUCCEEDED','FAILED')",
            name=op.f("ck_supplier_retention_runs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["supplier_data_retention_policies.id"],
            name=op.f(
                "fk_supplier_retention_runs_policy_id_supplier_data_retention_policies"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_retention_runs")),
    )
    op.create_index(
        "ix_supplier_retention_runs_policy_created",
        "supplier_retention_runs",
        ["policy_id", "created_at", "id"],
    )

    # Existing snapshots are projected without changing or deleting source rows.
    op.execute("""
        INSERT INTO supplier_price_observations (
            id, snapshot_id, snapshot_item_id, supplier_id, source_connection_id,
            product_code, product_code_normalized, identity_key, ean,
            product_name, category_name, source_currency, source_price,
            exchange_rate_to_rsd, price_rsd, stock, item_fingerprint,
            observed_at, created_at
        )
        SELECT gen_random_uuid(), snap.id, item.id, snap.supplier_id,
               snap.source_connection_id, value.product_code,
               lower(value.product_code),
               CASE WHEN value.ean IS NOT NULL THEN 'ean:' || value.ean
                    ELSE 'supplier:' || snap.supplier_id::text || ':code:' || lower(value.product_code) END,
               value.ean, NULLIF(btrim(item.mapped_data->>'name'), ''),
               NULLIF(btrim(item.mapped_data->>'category'), ''),
               left(upper(COALESCE(NULLIF(btrim(item.mapped_data->>'source_currency'), ''), NULLIF(btrim(item.mapped_data->>'currency'), ''), snap.source_currency, 'RSD')), 3),
               CASE WHEN value.source_price_text ~ '^[0-9]+([.,][0-9]+)?$' THEN replace(value.source_price_text, ',', '.')::numeric END,
               CASE WHEN value.rate_text ~ '^[0-9]+([.,][0-9]+)?$' THEN replace(value.rate_text, ',', '.')::numeric END,
               replace(value.price_rsd_text, ',', '.')::numeric,
               CASE WHEN value.stock_text ~ '^[0-9]+([.,][0-9]+)?$' THEN replace(value.stock_text, ',', '.')::numeric END,
               item.item_fingerprint, COALESCE(snap.finalized_at, snap.created_at), now()
        FROM supplier_snapshot_items item
        JOIN supplier_snapshots snap ON snap.id=item.snapshot_id
        CROSS JOIN LATERAL (
            SELECT COALESCE(NULLIF(btrim(item.mapped_data->>'product_code'), ''), NULLIF(btrim(item.source_identifier), '')) AS product_code,
                   NULLIF(btrim(item.mapped_data->>'ean'), '') AS ean,
                   COALESCE(NULLIF(btrim(item.mapped_data->>'source_price'), ''), NULLIF(btrim(item.mapped_data->>'price'), '')) AS source_price_text,
                   COALESCE(NULLIF(btrim(item.mapped_data->>'exchange_rate'), ''), snap.exchange_rate_to_rsd::text) AS rate_text,
                   COALESCE(NULLIF(btrim(item.mapped_data->>'price_rsd'), ''), NULLIF(btrim(item.mapped_data->>'price'), '')) AS price_rsd_text,
                   NULLIF(btrim(item.mapped_data->>'stock'), '') AS stock_text
        ) value
        WHERE value.product_code IS NOT NULL
          AND value.price_rsd_text ~ '^[0-9]+([.,][0-9]+)?$'
          AND replace(value.price_rsd_text, ',', '.')::numeric >= 0
          AND (value.source_price_text IS NULL OR value.source_price_text !~ '^[0-9]+([.,][0-9]+)?$' OR replace(value.source_price_text, ',', '.')::numeric >= 0)
          AND (value.rate_text IS NULL OR value.rate_text !~ '^[0-9]+([.,][0-9]+)?$' OR replace(value.rate_text, ',', '.')::numeric > 0)
          AND (value.stock_text IS NULL OR value.stock_text !~ '^[0-9]+([.,][0-9]+)?$' OR replace(value.stock_text, ',', '.')::numeric >= 0)
        ON CONFLICT (snapshot_item_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_retention_runs_policy_created",
        table_name="supplier_retention_runs",
    )
    op.drop_table("supplier_retention_runs")
    op.drop_index(
        "ix_supplier_price_observations_category_observed",
        table_name="supplier_price_observations",
    )
    op.drop_index(
        "ix_supplier_price_observations_ean_observed",
        table_name="supplier_price_observations",
    )
    op.drop_index(
        "ix_supplier_price_observations_source_product_observed",
        table_name="supplier_price_observations",
    )
    op.drop_index(
        "ix_supplier_price_observations_supplier_observed",
        table_name="supplier_price_observations",
    )
    op.drop_table("supplier_price_observations")
    op.drop_table("supplier_data_retention_policies")
