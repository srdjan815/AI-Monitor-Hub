from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_principal
from app.modules.system.models import SystemCleanupAudit
from app.modules.system.resource_service import (
    candidate_digest,
    cleanup_candidates,
    create_confirmation_token,
    verify_confirmation_token,
)
from app.modules.system.schemas import (
    CleanupAuditRead,
    CleanupExecuteRequest,
    CleanupPreviewRead,
    CleanupPreviewRequest,
    CleanupResultRead,
)


class CleanupConflict(RuntimeError):
    pass


class SystemMaintenanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def preview(self, payload: CleanupPreviewRequest) -> CleanupPreviewRead:
        candidates = cleanup_candidates(payload.category, payload.older_than_days)
        digest = candidate_digest(candidates)
        token, expires = create_confirmation_token(
            payload.category, payload.older_than_days, digest
        )
        return CleanupPreviewRead(
            category=payload.category,
            older_than_days=payload.older_than_days,
            candidate_files=len(candidates),
            candidate_bytes=sum(item.size for item in candidates),
            expires_at=expires,
            confirmation_token=token,
        )

    async def execute(self, payload: CleanupExecuteRequest) -> CleanupResultRead:
        candidates = cleanup_candidates(payload.category, payload.older_than_days)
        digest = candidate_digest(candidates)
        if not verify_confirmation_token(
            payload.confirmation_token,
            payload.category,
            payload.older_than_days,
            digest,
        ):
            raise CleanupConflict(
                "Pregled je istekao ili se skup fajlova promenio; ponovite pregled."
            )
        principal = current_principal()
        actor_id = principal.subject if principal else "unknown"
        deleted_files = 0
        deleted_bytes = 0
        failure: str | None = None
        try:
            for candidate in candidates:
                candidate.path.unlink()
                deleted_files += 1
                deleted_bytes += candidate.size
        except OSError as exc:
            failure = f"Čišćenje prekinuto nakon {deleted_files} fajlova: {exc.__class__.__name__}"
        status = (
            "FAILED" if failure else "NO_CHANGES" if deleted_files == 0 else "SUCCEEDED"
        )
        audit = SystemCleanupAudit(
            category=payload.category,
            older_than_days=payload.older_than_days,
            status=status,
            deleted_files=deleted_files,
            deleted_bytes=deleted_bytes,
            actor_id=actor_id,
            candidate_digest=digest,
            error_message=failure,
        )
        self.session.add(audit)
        await self.session.commit()
        await self.session.refresh(audit)
        return CleanupResultRead(
            audit_id=audit.id,
            status=status,
            deleted_files=deleted_files,
            deleted_bytes=deleted_bytes,
        )

    async def audit(self, limit: int) -> list[CleanupAuditRead]:
        rows = (
            await self.session.scalars(
                select(SystemCleanupAudit)
                .order_by(SystemCleanupAudit.created_at.desc())
                .limit(limit)
            )
        ).all()
        return [
            CleanupAuditRead(
                id=row.id,
                category=row.category,
                older_than_days=row.older_than_days,
                status=row.status,
                deleted_files=row.deleted_files,
                deleted_bytes=row.deleted_bytes,
                actor_id=row.actor_id,
                error_message=row.error_message,
                created_at=row.created_at,
            )
            for row in rows
        ]


__all__ = ["CleanupConflict", "SystemMaintenanceService"]
