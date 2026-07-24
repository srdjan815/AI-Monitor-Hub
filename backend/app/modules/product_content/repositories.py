from __future__ import annotations

from app.modules.product_content.configuration_repository import (
    ConfigurationRepository,
)
from app.modules.product_content.library_repository import LibraryRepository
from app.modules.product_content.revision_repository import RevisionRepository
from app.modules.product_content.scoring_repository import ScoringRepository


class ContentRepository(
    ConfigurationRepository,
    RevisionRepository,
    LibraryRepository,
    ScoringRepository,
):
    """Backward-compatible façade over cohesive content repositories."""


__all__ = ["ContentRepository"]
