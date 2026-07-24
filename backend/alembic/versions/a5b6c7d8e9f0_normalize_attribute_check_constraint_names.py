"""Normalize Attribute check-constraint names.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
"""

from alembic import op

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Replace naming-convention-expanded identifiers with canonical names."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname =
                    'ck_category_attributes_ck_category_attributes_position__5a1f'
                  AND conrelid = 'category_attributes'::regclass
            )
            AND NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_category_attributes_position_nonnegative'
                  AND conrelid = 'category_attributes'::regclass
            )
            THEN
                ALTER TABLE category_attributes
                RENAME CONSTRAINT
                    ck_category_attributes_ck_category_attributes_position__5a1f
                TO ck_category_attributes_position_nonnegative;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname =
                    'ck_attribute_definitions_ck_attribute_definitions_confi_b15e'
                  AND conrelid = 'attribute_definitions'::regclass
            )
            AND NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname =
                    'ck_attribute_definitions_confidence_threshold_range'
                  AND conrelid = 'attribute_definitions'::regclass
            )
            THEN
                ALTER TABLE attribute_definitions
                RENAME CONSTRAINT
                    ck_attribute_definitions_ck_attribute_definitions_confi_b15e
                TO ck_attribute_definitions_confidence_threshold_range;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname =
                    'ck_attribute_definitions_ck_attribute_definitions_defau_95cd'
                  AND conrelid = 'attribute_definitions'::regclass
            )
            AND NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname =
                    'ck_attribute_definitions_default_sort_order_nonnegative'
                  AND conrelid = 'attribute_definitions'::regclass
            )
            THEN
                ALTER TABLE attribute_definitions
                RENAME CONSTRAINT
                    ck_attribute_definitions_ck_attribute_definitions_defau_95cd
                TO ck_attribute_definitions_default_sort_order_nonnegative;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Keep canonical names so the parent migration can downgrade safely."""
