from __future__ import annotations

from pathlib import Path

from app.core.security import ROLE_PERMISSIONS
from app.main import app
from app.modules.suppliers.article_review_models import (
    SupplierArticleReview,
    SupplierArticleReviewEvent,
)

ROOT = Path(__file__).parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "c9d0e1f2a3b4_article_review_center.py"


def test_article_review_schema_is_additive_and_registered() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: Union[str, Sequence[str], None] = "b8c4bdfd5754"' in text
    assert "drop_column" not in text and "alter_column" not in text
    assert SupplierArticleReview.__tablename__ == "supplier_article_reviews"
    assert SupplierArticleReviewEvent.__tablename__ == "supplier_article_review_events"


def test_article_review_openapi_and_permissions() -> None:
    paths = {
        path: operations
        for path, operations in app.openapi()["paths"].items()
        if "/article-reviews" in path
    }
    assert len(paths) == 5
    assert {"article_reviews.read", "article_reviews.decide"} <= ROLE_PERMISSIONS[
        "supplier_admin"
    ]
    assert "article_reviews.read" in ROLE_PERMISSIONS["read_only"]
    assert "article_reviews.decide" not in ROLE_PERMISSIONS["read_only"]
