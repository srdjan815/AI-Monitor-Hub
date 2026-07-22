"""product core foundation

Revision ID: d4a9c8e7f621
Revises: 8b2f4d1c6a10
Create Date: 2026-07-22 23:30:00
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4a9c8e7f621"
down_revision: Union[str, Sequence[str], None] = "8b2f4d1c6a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GLOBAL_ATTRIBUTES = [
    ("Naziv proizvoda", "naziv_proizvoda", "TEXT"),
    ("Proizvođač", "proizvodjac", "TEXT"),
    ("Part number / SKU", "part_number_sku", "TEXT"),
    ("Kategorija proizvoda", "kategorija_proizvoda", "TEXT"),
    ("Podkategorija proizvoda 1", "podkategorija_proizvoda_1", "TEXT"),
    ("Podkategorija proizvoda 2", "podkategorija_proizvoda_2", "TEXT"),
    ("Garantni rok", "garantni_rok", "TEXT"),
    ("Dimenzije uređaja", "dimenzije_uredjaja", "TEXT"),
    ("Težina uređaja", "tezina_uredjaja", "DECIMAL"),
    ("Namena", "namena", "TEXT"),
    ("Potrošnja uređaja", "potrosnja_uredjaja", "TEXT"),
    ("Preporučeno za", "preporuceno_za", "TEXT"),
    ("Boja", "boja", "TEXT"),
    ("Težina upakovanog uređaja", "tezina_upakovanog_uredjaja", "DECIMAL"),
    ("Dimenzije upakovanog uređaja", "dimenzije_upakovanog_uredjaja", "TEXT"),
    ("Serija", "serija", "TEXT"),
    ("EAN", "ean", "TEXT"),
    ("ID proizvoda / Šifra proizvoda", "id_proizvoda_sifra_proizvoda", "TEXT"),
    ("Sadržaj pakovanja", "sadrzaj_pakovanja", "LONG_TEXT"),
    ("Materijal od kog je napravljen uređaj", "materijal_uredjaja", "TEXT"),
    ("Mini tekst", "mini_tekst", "LONG_TEXT"),
    ("Landing page", "landing_page", "URL"),
    ("YouTube video", "youtube_video", "URL"),
]


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"], name=op.f("fk_categories_parent_id_categories"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("code", name="uq_categories_code"),
        sa.UniqueConstraint("parent_id", "name", name="uq_categories_parent_name"),
    )
    op.create_index("ix_categories_active", "categories", ["is_active"], unique=False)
    op.create_index("ix_categories_parent_position", "categories", ["parent_id", "position"], unique=False)

    op.create_table(
        "attribute_definitions",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("data_type", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ai_prompt", sa.Text(), nullable=True),
        sa.Column("example_value", sa.Text(), nullable=True),
        sa.Column("validation_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("api_name", sa.String(length=255), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column("is_filterable", sa.Boolean(), nullable=False),
        sa.Column("is_searchable", sa.Boolean(), nullable=False),
        sa.Column("allows_multiple", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_definitions")),
        sa.UniqueConstraint("code", name="uq_attribute_definitions_code"),
    )
    op.create_index("ix_attribute_definitions_scope_active", "attribute_definitions", ["scope", "is_active"], unique=False)

    op.create_table(
        "category_attributes",
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("attribute_id", sa.Uuid(), nullable=False),
        sa.Column("group_name", sa.String(length=255), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_required_override", sa.Boolean(), nullable=True),
        sa.Column("is_visible_override", sa.Boolean(), nullable=True),
        sa.Column("ai_prompt_override", sa.Text(), nullable=True),
        sa.Column("validation_rules_override", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attribute_id"], ["attribute_definitions.id"], name=op.f("fk_category_attributes_attribute_id_attribute_definitions"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name=op.f("fk_category_attributes_category_id_categories"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_attributes")),
        sa.UniqueConstraint("category_id", "attribute_id", name="uq_category_attributes_pair"),
    )
    op.create_index("ix_category_attributes_order", "category_attributes", ["category_id", "position"], unique=False)

    attribute_table = sa.table(
        "attribute_definitions",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("code", sa.String()),
        sa.column("scope", sa.String()),
        sa.column("data_type", sa.String()),
        sa.column("validation_rules", postgresql.JSONB()),
        sa.column("api_name", sa.String()),
        sa.column("is_required", sa.Boolean()),
        sa.column("is_visible", sa.Boolean()),
        sa.column("is_filterable", sa.Boolean()),
        sa.column("is_searchable", sa.Boolean()),
        sa.column("allows_multiple", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
        sa.column("version", sa.Integer()),
    )
    namespace = uuid.UUID("b864c390-d293-4ccf-b574-5a78c7a79f85")
    op.bulk_insert(
        attribute_table,
        [
            {
                "id": uuid.uuid5(namespace, code),
                "name": name,
                "code": code,
                "scope": "GLOBAL",
                "data_type": data_type,
                "validation_rules": {},
                "api_name": code,
                "is_required": False,
                "is_visible": True,
                "is_filterable": False,
                "is_searchable": False,
                "allows_multiple": False,
                "is_active": True,
                "version": 1,
            }
            for name, code, data_type in GLOBAL_ATTRIBUTES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_category_attributes_order", table_name="category_attributes")
    op.drop_table("category_attributes")
    op.drop_index("ix_attribute_definitions_scope_active", table_name="attribute_definitions")
    op.drop_table("attribute_definitions")
    op.drop_index("ix_categories_parent_position", table_name="categories")
    op.drop_index("ix_categories_active", table_name="categories")
    op.drop_table("categories")
