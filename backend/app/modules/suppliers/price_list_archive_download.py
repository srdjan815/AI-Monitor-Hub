from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.suppliers.acquisition_models import SupplierAcquisitionRun
from app.modules.suppliers.pipeline_models import (
    SupplierSourceArtifact,
    SupplierSourcePipelineRun,
)
from app.modules.suppliers.price_list_archive_service import VISIBLE_RUN_STATUSES
from app.modules.system.artifact_archive_service import archive_target_root
from app.modules.system.models import ArtifactArchiveSetting, ArtifactArchiveTransfer


class ArchiveDownloadUnavailable(RuntimeError):
    pass


class ArchiveIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedArchiveDownload:
    path: Path
    filename: str
    content_type: str
    checksum_sha256: str


def _verified(path: Path, checksum: str, size: int | None) -> bool:
    if not path.is_file() or (size is not None and path.stat().st_size != size):
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest() == checksum


def _local_path(reference: str | None, root_setting: str) -> Path | None:
    if not reference or Path(reference).name != reference:
        return None
    root = Path(root_setting).resolve()
    candidate = (root / reference).resolve()
    return candidate if candidate.parent == root else None


def _archive_path(relative_path: str, reference: str | None) -> Path | None:
    if not reference:
        return None
    relative = PurePosixPath(reference)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    root = archive_target_root(relative_path).resolve()
    candidate = (root / Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _download_name(original: str | None, code: str, detected_format: str | None) -> str:
    if original:
        clean = original.strip()
        if clean and Path(clean).name == clean and "\x00" not in clean:
            return clean
    suffix = f".{detected_format.lower()}" if detected_format else ""
    return f"{code}{suffix}"


async def prepare_archive_download(
    session: AsyncSession, run_id: uuid.UUID
) -> PreparedArchiveDownload:
    row = (
        await session.execute(
            select(
                SupplierAcquisitionRun,
                SupplierSourceArtifact,
                ArtifactArchiveTransfer,
                ArtifactArchiveSetting,
            )
            .outerjoin(
                SupplierSourcePipelineRun,
                SupplierSourcePipelineRun.acquisition_run_id
                == SupplierAcquisitionRun.id,
            )
            .outerjoin(
                SupplierSourceArtifact,
                SupplierSourceArtifact.id == SupplierSourcePipelineRun.artifact_id,
            )
            .outerjoin(
                ArtifactArchiveTransfer,
                ArtifactArchiveTransfer.artifact_id == SupplierSourceArtifact.id,
            )
            .outerjoin(
                ArtifactArchiveSetting,
                ArtifactArchiveSetting.id == ArtifactArchiveTransfer.setting_id,
            )
            .where(
                SupplierAcquisitionRun.id == run_id,
                SupplierAcquisitionRun.status.in_(VISIBLE_RUN_STATUSES),
            )
        )
    ).first()
    if row is None:
        raise ArchiveDownloadUnavailable("Originalni cenovnik nije pronađen")
    run, artifact, transfer, archive_setting = row
    checksum = artifact.checksum_sha256 if artifact else run.checksum
    size = artifact.size_bytes if artifact else run.artifact_size_bytes
    if not checksum:
        raise ArchiveIntegrityError("Original nema sačuvan SHA-256 dokaz")

    candidates: list[Path] = []
    if (
        transfer
        and transfer.status == "VERIFIED"
        and archive_setting
        and (
            path := _archive_path(
                archive_setting.relative_path, transfer.archive_reference
            )
        )
    ):
        candidates.append(path)
    local = _local_path(
        artifact.storage_reference if artifact else run.artifact_reference,
        (
            settings.supplier_artifact_root
            if artifact
            else settings.acquisition_artifact_root
        ),
    )
    if local is not None:
        candidates.append(local)
    for candidate in candidates:
        if await asyncio.to_thread(_verified, candidate, checksum, size):
            return PreparedArchiveDownload(
                path=candidate,
                filename=_download_name(
                    artifact.original_filename if artifact else run.original_filename,
                    run.acquisition_code,
                    artifact.detected_format if artifact else None,
                ),
                content_type=(artifact.content_type if artifact else run.content_type)
                or "application/octet-stream",
                checksum_sha256=checksum,
            )
    if any(candidate.is_file() for candidate in candidates):
        raise ArchiveIntegrityError(
            "Preuzimanje je odbijeno jer SHA-256 ili veličina fajla nisu ispravni"
        )
    raise ArchiveDownloadUnavailable("Originalni fajl trenutno nije dostupan")


__all__ = [
    "ArchiveDownloadUnavailable",
    "ArchiveIntegrityError",
    "PreparedArchiveDownload",
    "prepare_archive_download",
]
