from __future__ import annotations

import uuid
from typing import Any

from app.modules.product_content.query_services import ScoringService
from app.modules.product_content.services import (
    ConfigurationService,
    ReferenceService,
    RevisionService,
)


class ProductContentService(
    ConfigurationService,
    RevisionService,
    ReferenceService,
):
    """Backward-compatible façade over responsibility-specific services."""

    async def score(self, product_id: uuid.UUID) -> dict[str, Any]:
        return await ScoringService(self.session).content_score(product_id)


__all__ = ["ProductContentService"]
