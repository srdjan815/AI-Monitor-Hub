from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_actor_id
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.retention_models import (
    SupplierDataRetentionPolicy,
    SupplierRetentionRun,
)
from app.modules.suppliers.retention_schemas import (
    DataRetentionAnalysisRead,
    RetentionPolicyListRead,
    RetentionPolicyRead,
    RetentionPolicyWrite,
    RetentionRunRead,
)

DEFAULT_STAGING_DAYS = 30
DEFAULT_SNAPSHOT_DAYS = 90
DEFAULT_MINIMUM_SNAPSHOTS = 7
DEFAULT_BATCH_SIZE = 1_000


class RetentionConflict(RuntimeError):
    pass


def preview_blockers(
    *,
    policy_enabled: bool,
    protected_snapshots: int,
    snapshots_requiring_archive: int,
    candidate_snapshot_items: int,
    observations_preserved: int,
) -> list[str]:
    blockers: list[str] = []
    if not policy_enabled:
        blockers.append("Politika nije uključena")
    if protected_snapshots:
        blockers.append("Postoje snapshotovi zaštićeni oznakom zadržavanja")
    if snapshots_requiring_archive:
        blockers.append("Snapshotovi prvo moraju imati verifikovanu arhivu")
    if candidate_snapshot_items > observations_preserved:
        blockers.append("Nisu sačuvana sva statistička opažanja")
    blockers.append(
        "Automatsko izvršenje nije aktivirano dok snapshot arhiva nije vezana za trajno odredište"
    )
    return blockers


def _policy_read(
    source: SupplierSource,
    supplier_name: str,
    policy: SupplierDataRetentionPolicy | None,
) -> RetentionPolicyRead:
    return RetentionPolicyRead(
        source_connection_id=source.id,
        supplier_name=supplier_name,
        source_name=source.name,
        enabled=policy.enabled if policy else False,
        configured=policy is not None,
        staging_retention_days=(
            policy.staging_retention_days if policy else DEFAULT_STAGING_DAYS
        ),
        snapshot_online_days=(
            policy.snapshot_online_days if policy else DEFAULT_SNAPSHOT_DAYS
        ),
        minimum_online_snapshots=(
            policy.minimum_online_snapshots if policy else DEFAULT_MINIMUM_SNAPSHOTS
        ),
        cleanup_batch_size=(
            policy.cleanup_batch_size if policy else DEFAULT_BATCH_SIZE
        ),
        version=policy.version if policy else None,
    )


class SupplierRetentionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def policies(self) -> RetentionPolicyListRead:
        rows = (
            await self.session.execute(
                select(
                    SupplierSource, Supplier.company_name, SupplierDataRetentionPolicy
                )
                .join(Supplier, Supplier.id == SupplierSource.supplier_id)
                .outerjoin(
                    SupplierDataRetentionPolicy,
                    SupplierDataRetentionPolicy.source_connection_id
                    == SupplierSource.id,
                )
                .order_by(Supplier.company_name, SupplierSource.name, SupplierSource.id)
            )
        ).all()
        items = [_policy_read(source, name, policy) for source, name, policy in rows]
        return RetentionPolicyListRead(items=items, total=len(items))

    async def save_policy(
        self, source_id: uuid.UUID, payload: RetentionPolicyWrite
    ) -> RetentionPolicyRead:
        row = (
            await self.session.execute(
                select(SupplierSource, Supplier.company_name)
                .join(Supplier, Supplier.id == SupplierSource.supplier_id)
                .where(SupplierSource.id == source_id)
            )
        ).one_or_none()
        if row is None:
            raise RetentionConflict("Izvor dobavljača ne postoji")
        source, supplier_name = row
        policy = await self.session.scalar(
            select(SupplierDataRetentionPolicy)
            .where(SupplierDataRetentionPolicy.source_connection_id == source_id)
            .with_for_update()
        )
        values = payload.model_dump(exclude={"expected_version"})
        if policy is None:
            if payload.expected_version is not None:
                raise RetentionConflict("Politika je u međuvremenu promenjena")
            policy = SupplierDataRetentionPolicy(
                source_connection_id=source_id, **values
            )
            self.session.add(policy)
        else:
            if payload.expected_version != policy.version:
                raise RetentionConflict("Politika je u međuvremenu promenjena")
            for key, value in values.items():
                setattr(policy, key, value)
            policy.version += 1
        await self.session.commit()
        await self.session.refresh(policy)
        return _policy_read(source, supplier_name, policy)

    async def preview(self, source_id: uuid.UUID) -> DataRetentionAnalysisRead:
        policy = await self.session.scalar(
            select(SupplierDataRetentionPolicy).where(
                SupplierDataRetentionPolicy.source_connection_id == source_id
            )
        )
        if policy is None:
            raise RetentionConflict("Prvo sačuvajte politiku za izabrani izvor")
        now = datetime.now(UTC)
        staging_cutoff = now - timedelta(days=policy.staging_retention_days)
        snapshot_cutoff = now - timedelta(days=policy.snapshot_online_days)
        row = (
            await self.session.execute(
                text("""
                WITH ranked AS (
                  SELECT s.id, s.total_items, s.legal_hold, s.preserve_online,
                         row_number() OVER (ORDER BY s.created_at DESC, s.id DESC) AS rn
                  FROM supplier_snapshots s
                  WHERE s.source_connection_id=:source_id AND s.status='READY'
                        AND s.storage_state='ONLINE'
                ), candidates AS (
                  SELECT r.* FROM ranked r
                  JOIN supplier_snapshots s ON s.id=r.id
                  WHERE s.created_at < :snapshot_cutoff AND r.rn > :minimum_online
                ), staged AS (
                  SELECT sr.id, pg_column_size(sr.*) AS bytes,
                         EXISTS(SELECT 1 FROM supplier_snapshot_items si
                                WHERE si.source_staged_record_id=sr.id) AS referenced
                  FROM supplier_staged_acquisition_records sr
                  JOIN supplier_acquisition_runs ar ON ar.id=sr.acquisition_run_id
                  WHERE ar.source_connection_id=:source_id AND sr.created_at < :staging_cutoff
                )
                SELECT
                  count(*) FILTER (WHERE NOT staged.referenced),
                  coalesce(sum(staged.bytes) FILTER (WHERE NOT staged.referenced),0),
                  count(*) FILTER (WHERE staged.referenced),
                  (SELECT count(*) FROM candidates),
                  (SELECT coalesce(sum(total_items),0) FROM candidates),
                  (SELECT coalesce(sum(pg_column_size(si.*)),0)
                     FROM supplier_snapshot_items si JOIN candidates c ON c.id=si.snapshot_id),
                  (SELECT count(*) FROM candidates WHERE legal_hold OR preserve_online),
                  (SELECT count(*) FROM candidates c WHERE NOT legal_hold AND NOT preserve_online
                    AND EXISTS (SELECT 1 FROM supplier_snapshot_archive_operations ao
                                WHERE ao.snapshot_id=c.id AND ao.status='VERIFIED')),
                  (SELECT count(*) FROM candidates c WHERE NOT legal_hold AND NOT preserve_online
                    AND NOT EXISTS (SELECT 1 FROM supplier_snapshot_archive_operations ao
                                    WHERE ao.snapshot_id=c.id AND ao.status='VERIFIED')),
                  (SELECT count(*) FROM supplier_price_observations po
                    JOIN supplier_snapshot_items si ON si.id=po.snapshot_item_id
                    JOIN candidates c ON c.id=si.snapshot_id)
                FROM staged
                """),
                {
                    "source_id": source_id,
                    "staging_cutoff": staging_cutoff,
                    "snapshot_cutoff": snapshot_cutoff,
                    "minimum_online": policy.minimum_online_snapshots,
                },
            )
        ).one()
        values = [int(value or 0) for value in row]
        blockers = preview_blockers(
            policy_enabled=policy.enabled,
            protected_snapshots=values[6],
            snapshots_requiring_archive=values[8],
            candidate_snapshot_items=values[4],
            observations_preserved=values[9],
        )
        run = SupplierRetentionRun(
            policy_id=policy.id,
            status="PREVIEWED",
            staging_cutoff=staging_cutoff,
            snapshot_cutoff=snapshot_cutoff,
            candidate_staging_rows=values[0],
            candidate_snapshots=values[3],
            preserved_observations=values[9],
            created_by=current_actor_id() or "system",
            notes="; ".join(blockers) or None,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return DataRetentionAnalysisRead(
            run_id=run.id,
            source_connection_id=source_id,
            staging_cutoff=staging_cutoff,
            snapshot_cutoff=snapshot_cutoff,
            candidate_staging_rows=values[0],
            candidate_staging_bytes=values[1],
            referenced_staging_rows=values[2],
            candidate_snapshots=values[3],
            candidate_snapshot_items=values[4],
            candidate_snapshot_bytes=values[5],
            protected_snapshots=values[6],
            snapshots_ready_for_offload=values[7],
            snapshots_requiring_archive=values[8],
            observations_preserved=values[9],
            execution_allowed=False,
            blockers=blockers,
            created_at=run.created_at,
        )

    async def runs(self, limit: int) -> list[RetentionRunRead]:
        rows = (
            await self.session.execute(
                select(SupplierRetentionRun, SupplierSource.name, SupplierSource.id)
                .join(
                    SupplierDataRetentionPolicy,
                    SupplierDataRetentionPolicy.id == SupplierRetentionRun.policy_id,
                )
                .join(
                    SupplierSource,
                    SupplierSource.id
                    == SupplierDataRetentionPolicy.source_connection_id,
                )
                .order_by(
                    SupplierRetentionRun.created_at.desc(),
                    SupplierRetentionRun.id.desc(),
                )
                .limit(limit)
            )
        ).all()
        return [
            RetentionRunRead(
                id=run.id,
                source_connection_id=source_id,
                source_name=source_name,
                status=run.status,
                staging_cutoff=run.staging_cutoff,
                snapshot_cutoff=run.snapshot_cutoff,
                candidate_staging_rows=run.candidate_staging_rows,
                candidate_snapshots=run.candidate_snapshots,
                preserved_observations=run.preserved_observations,
                deleted_staging_rows=run.deleted_staging_rows,
                offloaded_snapshot_items=run.offloaded_snapshot_items,
                created_by=run.created_by,
                created_at=run.created_at,
                completed_at=run.completed_at,
                failure_message=run.failure_message,
            )
            for run, source_name, source_id in rows
        ]


__all__ = ["RetentionConflict", "SupplierRetentionService", "preview_blockers"]
