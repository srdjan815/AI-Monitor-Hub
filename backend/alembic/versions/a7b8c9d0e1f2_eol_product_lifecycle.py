"""EOL product lifecycle and deactivation outbox.

Revision ID: a7b8c9d0e1f2
Revises: f6e7d8c9b0a1, a5b6c7d8e9f0
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a7b8c9d0e1f2"
down_revision = ("f6e7d8c9b0a1", "a5b6c7d8e9f0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE eol_export_batch_code_seq START WITH 1")
    op.create_table(
        "supplier_product_presence",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("source_connection_id", sa.Uuid(), nullable=False),
        sa.Column("product_code", sa.String(500), nullable=False),
        sa.Column("product_code_normalized", sa.String(500), nullable=False),
        sa.Column("identity_key", sa.String(600), nullable=False),
        sa.Column("ean", sa.String(32)),
        sa.Column("product_name", sa.String(2000)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("is_currently_offered", sa.Boolean(), nullable=False),
        sa.Column("last_data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_connection_id"], ["supplier_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_snapshot_id"], ["supplier_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_connection_id", "product_code_normalized", "identity_key", name="uq_supplier_product_presence_source_product_identity"),
    )
    op.create_index("ix_supplier_product_presence_identity_seen", "supplier_product_presence", ["identity_key", "last_seen_at"])
    op.create_index("ix_supplier_product_presence_supplier_seen", "supplier_product_presence", ["supplier_id", "last_seen_at"])
    op.create_index("ix_supplier_product_presence_current", "supplier_product_presence", ["is_currently_offered", "last_seen_at"])
    op.create_table(
        "eol_export_batches",
        sa.Column("batch_code", sa.String(50), server_default=sa.text("'EOL-' || lpad(nextval('eol_export_batch_code_seq'::regclass)::text, 6, '0')"), nullable=False),
        sa.Column("status", sa.String(32), server_default="PREPARED", nullable=False),
        sa.Column("inactivity_months", sa.Integer(), nullable=False),
        sa.Column("target_systems", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failure_message", sa.Text()),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("inactivity_months BETWEEN 1 AND 12", name="inactivity_months_valid"),
        sa.CheckConstraint("status IN ('PREPARED','PROCESSING','PARTIALLY_SUCCEEDED','SUCCEEDED','FAILED','CANCELLED')", name="status_valid"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_code", name="uq_eol_export_batches_batch_code"),
        sa.UniqueConstraint("idempotency_key", name="uq_eol_export_batches_idempotency_key"),
    )
    op.create_index("ix_eol_export_batches_status_created", "eol_export_batches", ["status", "created_at"])
    op.create_table(
        "eol_export_items",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("identity_key", sa.String(600), nullable=False),
        sa.Column("ean", sa.String(32)),
        sa.Column("product_name", sa.String(2000)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), server_default="PENDING", nullable=False),
        sa.Column("target_results", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("failure_message", sa.Text()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('PENDING','SUCCEEDED','FAILED','SKIPPED')", name="status_valid"),
        sa.ForeignKeyConstraint(["batch_id"], ["eol_export_batches.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "identity_key", name="uq_eol_export_items_batch_identity"),
    )
    op.create_index("ix_eol_export_items_batch_status", "eol_export_items", ["batch_id", "status"])
    op.create_index(
        "uq_eol_export_items_pending_identity",
        "eol_export_items",
        ["identity_key"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    # Build the compact projection from historical READY snapshots. The latest
    # snapshot per source determines current offer membership; MAX preserves history.
    op.execute("""
        INSERT INTO supplier_product_presence (
            id, supplier_id, source_connection_id, product_code,
            product_code_normalized, identity_key, ean, product_name,
            last_seen_at, last_snapshot_id, is_currently_offered, last_data,
            created_at, updated_at
        )
        SELECT gen_random_uuid(), ranked.supplier_id, ranked.source_connection_id,
               ranked.product_code, lower(ranked.product_code),
               CASE WHEN ranked.ean IS NOT NULL THEN 'ean:' || ranked.ean
                    ELSE 'supplier:' || ranked.supplier_id::text || ':code:' || lower(ranked.product_code) END,
               ranked.ean, ranked.product_name, ranked.last_seen_at,
               ranked.last_snapshot_id,
               EXISTS (
                   SELECT 1 FROM supplier_snapshot_items current_item
                   WHERE current_item.snapshot_id=ranked.latest_source_snapshot_id
                     AND lower(current_item.mapped_data->>'product_code')=lower(ranked.product_code)
                     AND COALESCE(NULLIF(current_item.mapped_data->>'ean',''), '')=
                         COALESCE(ranked.ean, '')
               ),
               ranked.last_data, now(), now()
        FROM (
            SELECT DISTINCT ON (
                       snap.source_connection_id,
                       lower(item.mapped_data->>'product_code'),
                       COALESCE(NULLIF(item.mapped_data->>'ean',''), '')
                   )
                   snap.supplier_id, snap.source_connection_id,
                   item.mapped_data->>'product_code' AS product_code,
                   NULLIF(item.mapped_data->>'ean','') AS ean,
                   NULLIF(item.mapped_data->>'name','') AS product_name,
                   COALESCE(snap.finalized_at, snap.created_at) AS last_seen_at,
                   snap.id AS last_snapshot_id, item.mapped_data AS last_data,
                   (SELECT newest.id FROM supplier_snapshots newest
                    WHERE newest.source_connection_id=snap.source_connection_id
                      AND newest.status='READY'
                    ORDER BY COALESCE(newest.finalized_at, newest.created_at) DESC,
                             newest.id DESC LIMIT 1) AS latest_source_snapshot_id
            FROM supplier_snapshots snap
            JOIN supplier_snapshot_items item ON item.snapshot_id=snap.id
            WHERE snap.status='READY' AND NULLIF(item.mapped_data->>'product_code','') IS NOT NULL
            ORDER BY snap.source_connection_id, lower(item.mapped_data->>'product_code'),
                     COALESCE(NULLIF(item.mapped_data->>'ean',''), ''),
                     COALESCE(snap.finalized_at, snap.created_at) DESC, snap.id DESC
        ) ranked
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        UPDATE supplier_delta_items
        SET change_summary=(change_summary - 'classification' - 'downstream_blocked' - 'requires_manual_approval') ||
             jsonb_build_object(
                 'classification', 'REMOVED_FROM_SUPPLIER_OFFER',
                 'downstream_blocked', false,
                 'requires_manual_approval', false,
                 'eol_policy_migrated', true
             ),
            anomaly_flags=(anomaly_flags - 'REMOVAL_REQUIRES_REVIEW') - 'DOWNSTREAM_ITEM_BLOCKED'
        WHERE change_type='REMOVED'
          AND anomaly_flags ? 'REMOVAL_REQUIRES_REVIEW'
    """)
    op.execute("""
        INSERT INTO supplier_article_review_events (
            id, review_id, action, previous_status, current_status,
            actor_id, comment, event_metadata, created_at
        )
        SELECT gen_random_uuid(), id, 'SUPERSEDED', status, 'SUPERSEDED',
               'migration', 'Povlačenje iz ponude više nije kontrolna greška.',
               jsonb_build_object('policy', 'REMOVED_FROM_SUPPLIER_OFFER'), now()
        FROM supplier_article_reviews
        WHERE status='PENDING_REVIEW' AND issue_codes ? 'ARTICLE_REMOVED'
    """)
    op.execute("""
        UPDATE supplier_article_reviews
        SET status='SUPERSEDED', decided_by='migration', decided_at=now(),
            decision_comment='Povlačenje iz ponude više nije kontrolna greška.',
            version=version+1, updated_at=now()
        WHERE status='PENDING_REVIEW' AND issue_codes ? 'ARTICLE_REMOVED'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE supplier_delta_items
        SET change_summary=(change_summary - 'classification' - 'downstream_blocked' -
                            'requires_manual_approval' - 'eol_policy_migrated') ||
             jsonb_build_object(
                 'classification', 'REMOVED_BLOCKED',
                 'downstream_blocked', true,
                 'requires_manual_approval', true
             ),
            anomaly_flags=(anomaly_flags || '["REMOVAL_REQUIRES_REVIEW", "DOWNSTREAM_ITEM_BLOCKED"]'::jsonb)
        WHERE change_summary ->> 'eol_policy_migrated' = 'true'
    """)
    op.execute("""
        UPDATE supplier_article_reviews
        SET status='PENDING_REVIEW', decided_by=NULL, decided_at=NULL,
            decision_comment=NULL, version=version+1, updated_at=now()
        WHERE status='SUPERSEDED' AND decided_by='migration'
          AND decision_comment='Povlačenje iz ponude više nije kontrolna greška.'
    """)
    op.execute("""
        DELETE FROM supplier_article_review_events
        WHERE action='SUPERSEDED' AND actor_id='migration'
          AND event_metadata ->> 'policy' = 'REMOVED_FROM_SUPPLIER_OFFER'
    """)
    op.drop_index("uq_eol_export_items_pending_identity", table_name="eol_export_items")
    op.drop_index("ix_eol_export_items_batch_status", table_name="eol_export_items")
    op.drop_table("eol_export_items")
    op.drop_index("ix_eol_export_batches_status_created", table_name="eol_export_batches")
    op.drop_table("eol_export_batches")
    op.drop_index("ix_supplier_product_presence_current", table_name="supplier_product_presence")
    op.drop_index("ix_supplier_product_presence_supplier_seen", table_name="supplier_product_presence")
    op.drop_index("ix_supplier_product_presence_identity_seen", table_name="supplier_product_presence")
    op.drop_table("supplier_product_presence")
    op.execute("DROP SEQUENCE eol_export_batch_code_seq")
