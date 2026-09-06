from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.suppliers.pipeline_models import SupplierSourceArtifact
from app.modules.system.models import ArtifactArchiveSetting, ArtifactArchiveTransfer
from app.modules.system.schemas import (
    ArchiveProcessRead,
    ArchiveSettingRead,
    ArchiveSettingWrite,
    ArchiveStatusRead,
    ArchiveTestRead,
)


class ArchiveConfigurationError(RuntimeError):
    pass


def _setting_read(item: ArtifactArchiveSetting) -> ArchiveSettingRead:
    return ArchiveSettingRead.model_validate(item, from_attributes=True)


def _target_root(relative_path: str) -> Path:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ArchiveConfigurationError("Putanja arhive mora biti relativna i bez '..'")
    base = Path(settings.system_archive_mount_root).resolve()
    target = (base / Path(*relative.parts)).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ArchiveConfigurationError(
            "Putanja arhive izlazi iz dozvoljenog korena"
        ) from exc
    if base == base.parent or len(base.parts) < 3:
        raise ArchiveConfigurationError("Koren arhive nije dovoljno usko podešen")
    return target


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_verified_artifact(
    source: Path, target_root: Path, checksum: str, size: int
) -> str:
    reference = f"blobs/sha256/{checksum[:2]}/{checksum}"
    destination = (target_root / reference).resolve()
    destination.relative_to(target_root.resolve())
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)
        if destination.stat().st_size != size or _checksum(destination) != checksum:
            raise OSError("Checksum udaljene kopije nije ispravan")
        return reference
    finally:
        temporary.unlink(missing_ok=True)


class ArtifactArchiveService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def setting(self) -> ArtifactArchiveSetting | None:
        return cast(
            ArtifactArchiveSetting | None,
            await self.session.scalar(
                select(ArtifactArchiveSetting).where(
                    ArtifactArchiveSetting.setting_key == "PRIMARY"
                )
            ),
        )

    async def status(self) -> ArchiveStatusRead:
        setting = await self.setting()
        artifact_count = int(
            await self.session.scalar(select(func.count(SupplierSourceArtifact.id)))
            or 0
        )
        counts = (
            await self.session.execute(
                select(
                    func.count().filter(ArtifactArchiveTransfer.status == "PENDING"),
                    func.count().filter(ArtifactArchiveTransfer.status == "VERIFIED"),
                    func.count().filter(ArtifactArchiveTransfer.status == "FAILED"),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    ArtifactArchiveTransfer.status == "VERIFIED",
                                    ArtifactArchiveTransfer.verified_size_bytes,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                )
            )
        ).one()
        groups = (
            select(
                (func.count(SupplierSourceArtifact.id) - 1).label("copies"),
                (
                    SupplierSourceArtifact.size_bytes
                    * (func.count(SupplierSourceArtifact.id) - 1)
                ).label("bytes"),
            )
            .group_by(
                SupplierSourceArtifact.checksum_sha256,
                SupplierSourceArtifact.size_bytes,
            )
            .subquery()
        )
        duplicate = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(groups.c.copies), 0),
                    func.coalesce(func.sum(groups.c.bytes), 0),
                )
            )
        ).one()
        return ArchiveStatusRead(
            setting=_setting_read(setting) if setting else None,
            pending_transfers=int(counts[0])
            + max(artifact_count - int(counts[0]) - int(counts[1]) - int(counts[2]), 0),
            verified_transfers=int(counts[1]),
            failed_transfers=int(counts[2]),
            verified_bytes=int(counts[3]),
            duplicate_artifacts=int(duplicate[0]),
            duplicate_bytes=int(duplicate[1]),
        )

    async def save_setting(self, payload: ArchiveSettingWrite) -> ArchiveSettingRead:
        _target_root(payload.relative_path)
        item = await self.setting()
        if item is None:
            item = ArtifactArchiveSetting(
                setting_key="PRIMARY",
                backend_type="MOUNT",
                **payload.model_dump(exclude={"expected_version"}),
            )
            self.session.add(item)
        else:
            if payload.expected_version != item.version:
                raise ArchiveConfigurationError(
                    "Podešavanje je u međuvremenu promenjeno"
                )
            for key, value in payload.model_dump(exclude={"expected_version"}).items():
                setattr(item, key, value)
            item.version += 1
        await self.session.commit()
        await self.session.refresh(item)
        return _setting_read(item)

    async def test(self) -> ArchiveTestRead:
        item = await self.setting()
        if item is None:
            raise ArchiveConfigurationError("Odredište arhive nije podešeno")
        target = _target_root(item.relative_path)
        now = datetime.now(UTC)
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / f".ai-monitor-probe-{uuid.uuid4().hex}"
            payload = os.urandom(64)
            probe.write_bytes(payload)
            with probe.open("rb") as handle:
                os.fsync(handle.fileno())
            if probe.read_bytes() != payload:
                raise OSError("Sadržaj probnog fajla nije isti")
            probe.unlink()
            status: Literal["SUCCEEDED", "FAILED"] = "SUCCEEDED"
            message = "Upis, čitanje i uklanjanje probnog fajla su uspešni."
        except OSError as exc:
            status, message = (
                "FAILED",
                f"Odredište nije dostupno za pouzdan upis: {exc.__class__.__name__}",
            )
        item.last_tested_at, item.last_test_status, item.last_test_message = (
            now,
            status,
            message,
        )
        item.version += 1
        await self.session.commit()
        return ArchiveTestRead(status=status, message=message)

    async def archive_artifact(self, artifact_id: uuid.UUID) -> bool:
        setting = await self.setting()
        if (
            setting is None
            or not setting.enabled
            or setting.last_test_status != "SUCCEEDED"
        ):
            return False
        artifact = await self.session.get(SupplierSourceArtifact, artifact_id)
        if artifact is None:
            return False
        transfer = await self.session.scalar(
            select(ArtifactArchiveTransfer)
            .where(ArtifactArchiveTransfer.artifact_id == artifact.id)
            .with_for_update()
        )
        if transfer is None:
            transfer = ArtifactArchiveTransfer(
                artifact_id=artifact.id, setting_id=setting.id, status="PENDING"
            )
            self.session.add(transfer)
            await self.session.flush()
        if transfer.status == "VERIFIED":
            return True
        transfer.attempt_count += 1
        transfer.last_attempt_at = datetime.now(UTC)
        source = (
            Path(settings.supplier_artifact_root) / artifact.storage_reference
        ).resolve()
        target_root = _target_root(setting.relative_path)
        try:
            source.relative_to(Path(settings.supplier_artifact_root).resolve())
            if not source.is_file() or source.stat().st_size != artifact.size_bytes:
                raise OSError("Lokalni artefakt nedostaje ili veličina nije ispravna")
            reference = copy_verified_artifact(
                source, target_root, artifact.checksum_sha256, artifact.size_bytes
            )
            transfer.status, transfer.archive_reference = "VERIFIED", reference
            transfer.verified_checksum, transfer.verified_size_bytes = (
                artifact.checksum_sha256,
                artifact.size_bytes,
            )
            transfer.verified_at, transfer.failure_code, transfer.failure_message = (
                datetime.now(UTC),
                None,
                None,
            )
            result = True
        except OSError as exc:
            transfer.status, transfer.failure_code = "FAILED", "artifact_archive_failed"
            transfer.failure_message, result = str(exc)[:500], False
        await self.session.commit()
        return result

    async def archive_if_configured(self, artifact_id: uuid.UUID) -> bool | None:
        setting = await self.setting()
        if (
            setting is None
            or not setting.enabled
            or setting.last_test_status != "SUCCEEDED"
        ):
            return None
        return await self.archive_artifact(artifact_id)

    async def process_pending(self, limit: int) -> ArchiveProcessRead:
        ids = list(
            (
                await self.session.scalars(
                    select(SupplierSourceArtifact.id)
                    .outerjoin(
                        ArtifactArchiveTransfer,
                        ArtifactArchiveTransfer.artifact_id
                        == SupplierSourceArtifact.id,
                    )
                    .where(
                        (ArtifactArchiveTransfer.id.is_(None))
                        | (ArtifactArchiveTransfer.status == "FAILED")
                    )
                    .order_by(SupplierSourceArtifact.created_at)
                    .limit(limit)
                )
            ).all()
        )
        verified = 0
        for artifact_id in ids:
            if await self.archive_artifact(artifact_id):
                verified += 1
        return ArchiveProcessRead(
            attempted=len(ids), verified=verified, failed=len(ids) - verified
        )


async def artifact_archive_warnings(
    session: AsyncSession, artifact_id: uuid.UUID
) -> list[str]:
    try:
        result = await ArtifactArchiveService(session).archive_if_configured(
            artifact_id
        )
    except (ArchiveConfigurationError, OSError, SQLAlchemyError):
        # Arhiva je sekundarna kopija: njen kvar nikada ne sme ponistiti uspesan
        # uvoz niti obrisati jedinu lokalnu kopiju poslovnog artefakta.
        await session.rollback()
        result = False
    if result is False:
        return ["Arhiviranje nije uspelo; lokalna kopija čeka novi pokušaj."]
    return []


__all__ = [
    "ArchiveConfigurationError",
    "ArtifactArchiveService",
    "artifact_archive_warnings",
    "copy_verified_artifact",
]
