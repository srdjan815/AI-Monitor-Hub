"""article review center

Revision ID: c9d0e1f2a3b4
Revises: b8c4bdfd5754
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c4bdfd5754"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "supplier_article_reviews",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("source_connection_id", sa.Uuid(), nullable=False),
        sa.Column("delta_run_id", sa.Uuid(), nullable=False),
        sa.Column("delta_item_id", sa.Uuid(), nullable=False),
        sa.Column("product_code", sa.String(length=500), nullable=False),
        sa.Column("ean", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="PENDING_REVIEW", nullable=False),
        sa.Column("severity", sa.String(length=8), server_default="HIGH", nullable=False),
        sa.Column("issue_codes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("reviewed_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('PENDING_REVIEW','MANUALLY_APPROVED','REJECTED','AUTO_RELEASED','SUPERSEDED')", name="supplier_article_reviews_status_valid"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_connection_id"], ["supplier_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["delta_run_id"], ["supplier_delta_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["delta_item_id"], ["supplier_delta_items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delta_item_id", name="uq_supplier_article_reviews_delta_item"),
    )
    op.create_index("ix_article_reviews_queue", "supplier_article_reviews", ["status", "opened_at", "id"])
    op.create_index("ix_article_reviews_supplier_status", "supplier_article_reviews", ["supplier_id", "status", "opened_at"])
    op.create_index("ix_article_reviews_source_product", "supplier_article_reviews", ["source_connection_id", "product_code", "status"])
    op.create_index("ix_article_reviews_issue_codes", "supplier_article_reviews", ["issue_codes"], postgresql_using="gin")
    op.create_table(
        "supplier_article_review_events",
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("current_status", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["supplier_article_reviews.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_article_review_events_review_created", "supplier_article_review_events", ["review_id", "created_at", "id"])
    op.execute(
        """
        INSERT INTO supplier_article_reviews (
            id, supplier_id, source_connection_id, delta_run_id, delta_item_id,
            product_code, ean, status, severity, issue_codes,
            reviewed_fingerprint, opened_at, version, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), run.supplier_id, run.source_connection_id,
            item.delta_run_id, item.id,
            COALESCE(
                NULLIF(current_item.mapped_data ->> 'product_code', ''),
                NULLIF(previous_item.mapped_data ->> 'product_code', ''),
                NULLIF(item.change_summary ->> 'first_product_code', ''),
                item.matching_key_value
            ),
            COALESCE(
                NULLIF(current_item.mapped_data ->> 'ean', ''),
                NULLIF(previous_item.mapped_data ->> 'ean', ''),
                NULLIF(item.change_summary ->> 'ean', '')
            ),
            'PENDING_REVIEW',
            CASE WHEN item.anomaly_flags ? 'CURRENT_RECORD_INVALID'
                THEN 'CRITICAL' ELSE 'HIGH' END,
            CASE WHEN jsonb_array_length(item.anomaly_flags) > 0
                THEN item.anomaly_flags - 'DOWNSTREAM_ITEM_BLOCKED'
                ELSE jsonb_build_array(
                    COALESCE(item.change_summary ->> 'classification',
                             'MANUAL_REVIEW_REQUIRED')
                )
            END,
            item.current_item_fingerprint, item.created_at, 1, now(), now()
        FROM supplier_delta_items AS item
        JOIN supplier_delta_runs AS run ON run.id = item.delta_run_id
        LEFT JOIN supplier_snapshot_items AS current_item
            ON current_item.id = item.current_snapshot_item_id
        LEFT JOIN supplier_snapshot_items AS previous_item
            ON previous_item.id = item.previous_snapshot_item_id
        WHERE item.change_summary ->> 'downstream_blocked' = 'true'
           OR item.change_summary ->> 'requires_manual_approval' = 'true'
        ON CONFLICT (delta_item_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO supplier_article_review_events (
            id, review_id, action, previous_status, current_status,
            actor_id, comment, event_metadata, created_at
        )
        SELECT gen_random_uuid(), review.id, 'OPENED', NULL, review.status,
               'migration', 'Preneto iz postojeće Delta blokade.',
               jsonb_build_object('backfilled', true), review.opened_at
        FROM supplier_article_reviews AS review
        WHERE NOT EXISTS (
            SELECT 1 FROM supplier_article_review_events AS event
            WHERE event.review_id = review.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_article_review_events_review_created", table_name="supplier_article_review_events")
    op.drop_table("supplier_article_review_events")
    op.drop_index("ix_article_reviews_issue_codes", table_name="supplier_article_reviews", postgresql_using="gin")
    op.drop_index("ix_article_reviews_source_product", table_name="supplier_article_reviews")
    op.drop_index("ix_article_reviews_supplier_status", table_name="supplier_article_reviews")
    op.drop_index("ix_article_reviews_queue", table_name="supplier_article_reviews")
    op.drop_table("supplier_article_reviews")
