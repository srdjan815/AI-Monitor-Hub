from __future__ import annotations

import uuid
from datetime import datetime

from app.modules.suppliers.article_review_models import SupplierArticleReviewEvent
from app.modules.suppliers.article_review_repository import (
    SupplierArticleReviewRepository,
)
from app.modules.suppliers.delta_models import SupplierDeltaItem


async def release_resolved_shared_ean_groups(
    repository: SupplierArticleReviewRepository,
    *,
    source_id: uuid.UUID,
    delta_run_id: uuid.UUID,
    delta_items: list[SupplierDeltaItem],
    decided_at: datetime,
) -> list[SupplierArticleReviewEvent]:
    oversized_eans = {
        str(delta.change_summary.get("ean") or "").strip()
        for delta in delta_items
        if "SHARED_EAN_GROUP_LIMIT_EXCEEDED" in delta.anomaly_flags
    }
    events: list[SupplierArticleReviewEvent] = []
    for blocked in await repository.pending_shared_ean_group_reviews(source_id):
        if not blocked.ean or blocked.ean in oversized_eans:
            continue
        previous_status = blocked.status
        blocked.status = "AUTO_RELEASED"
        blocked.decision_comment = "Broj šifara za EAN je vraćen u dozvoljeni okvir."
        blocked.decided_by = "system"
        blocked.decided_at = decided_at
        blocked.version += 1
        events.append(
            SupplierArticleReviewEvent(
                id=uuid.uuid4(),
                review_id=blocked.id,
                action="AUTO_RELEASED",
                previous_status=previous_status,
                current_status=blocked.status,
                actor_id="system",
                comment=blocked.decision_comment,
                event_metadata={"corrected_delta_id": str(delta_run_id)},
            )
        )
    return events


__all__ = ["release_resolved_shared_ean_groups"]
