from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import stat as stat_module
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.system.schemas import (
    CapacityRead,
    Health,
    RuntimeRead,
    StorageCategoryRead,
    SystemInventoryRead,
)


@dataclass(frozen=True, slots=True)
class CleanupCandidate:
    path: Path
    size: int
    modified_ns: int


@dataclass(frozen=True, slots=True)
class StoragePolicy:
    code: str
    label: str
    root: Path
    cleanup_allowed: bool
    protection_reason: str | None


def storage_policies() -> tuple[StoragePolicy, ...]:
    return (
        StoragePolicy(
            "LOGOVI",
            "Logovi aplikacije",
            Path(settings.system_log_root),
            True,
            None,
        ),
        StoragePolicy(
            "PRIVREMENI_FAJLOVI",
            "Privremeni fajlovi",
            Path(settings.system_temporary_root),
            True,
            None,
        ),
        StoragePolicy(
            "CENOVNICI",
            "Sačuvani cenovnici",
            Path(settings.supplier_artifact_root),
            False,
            "Poslovni artefakti povezani su sa zapisima u bazi.",
        ),
        StoragePolicy(
            "SNAPSHOT_ARHIVE",
            "Snapshot arhive",
            Path(settings.snapshot_archive_root),
            False,
            "Arhive se uklanjaju samo kroz njihov životni ciklus.",
        ),
    )


def _capacity(
    total: int | None, used: int | None, warning: int, critical: int
) -> CapacityRead:
    if total is None or used is None or total <= 0:
        return CapacityRead(
            total_bytes=total,
            used_bytes=used,
            free_bytes=None,
            used_percent=None,
            status="NEPOZNATO",
        )
    percent = used * 100.0 / total
    status: Health = (
        "KRITIČNO"
        if percent >= critical
        else "UPOZORENJE" if percent >= warning else "OK"
    )
    return CapacityRead(
        total_bytes=total,
        used_bytes=used,
        free_bytes=max(total - used, 0),
        used_percent=round(percent, 2),
        status=status,
    )


def _read_integer(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="ascii").strip()
        return None if raw == "max" else int(raw)
    except (OSError, ValueError):
        return None


def _memory_usage() -> tuple[int | None, int | None]:
    limit = _read_integer(Path("/sys/fs/cgroup/memory.max"))
    used = _read_integer(Path("/sys/fs/cgroup/memory.current"))
    if limit is not None and used is not None and limit < 1 << 60:
        return limit, used
    try:
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, value = line.split(":", 1)
            values[key] = int(value.strip().split()[0]) * 1024
        total = values["MemTotal"]
        return total, total - values["MemAvailable"]
    except (OSError, KeyError, ValueError):
        return None, None


def _processor_load() -> float | None:
    try:
        one_minute, _, _ = os.getloadavg()
        return round(min(one_minute / max(os.cpu_count() or 1, 1) * 100, 100), 2)
    except (AttributeError, OSError):
        return None


def _safe_root(path: Path) -> Path:
    root = path.resolve()
    if root == root.parent or len(root.parts) < 3:
        raise RuntimeError("System putanja nije dovoljno uska za bezbednu obradu")
    return root


def _walk_files(root: Path, limit: int) -> tuple[list[CleanupCandidate], bool]:
    resolved = _safe_root(root)
    if not resolved.is_dir():
        return [], False
    files: list[CleanupCandidate] = []
    truncated = False
    for current, directories, names in os.walk(resolved, followlinks=False):
        directories[:] = [
            name for name in directories if not (Path(current) / name).is_symlink()
        ]
        for name in names:
            path = Path(current) / name
            try:
                if path.is_symlink():
                    continue
                stat = path.stat()
                if not stat_module.S_ISREG(stat.st_mode):
                    continue
                path.resolve().relative_to(resolved)
            except (OSError, ValueError):
                continue
            files.append(CleanupCandidate(path, stat.st_size, stat.st_mtime_ns))
            if len(files) >= limit:
                truncated = True
                return files, truncated
    return files, truncated


def cleanup_candidates(category: str, older_than_days: int) -> list[CleanupCandidate]:
    policy = next((item for item in storage_policies() if item.code == category), None)
    if policy is None or not policy.cleanup_allowed:
        raise ValueError("Kategorija nije dozvoljena za generičko čišćenje")
    cutoff_ns = int((time.time() - older_than_days * 86_400) * 1_000_000_000)
    files, truncated = _walk_files(policy.root, settings.system_cleanup_max_files + 1)
    candidates = [item for item in files if item.modified_ns < cutoff_ns]
    if truncated or len(candidates) > settings.system_cleanup_max_files:
        raise RuntimeError("Broj kandidata prelazi bezbedni limit jednog čišćenja")
    return sorted(candidates, key=lambda item: str(item.path))


def candidate_digest(candidates: list[CleanupCandidate]) -> str:
    digest = hashlib.sha256()
    for item in candidates:
        digest.update(
            f"{item.path.resolve()}\0{item.size}\0{item.modified_ns}\n".encode()
        )
    return digest.hexdigest()


def create_confirmation_token(
    category: str, days: int, digest: str
) -> tuple[str, datetime]:
    expires = datetime.now(UTC) + timedelta(minutes=10)
    payload = {
        "category": category,
        "days": days,
        "digest": digest,
        "exp": int(expires.timestamp()),
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = hmac.new(
        settings.auth_secret.encode(), encoded.encode(), hashlib.sha256
    ).hexdigest()
    return f"{encoded}.{signature}", expires


def verify_confirmation_token(
    token: str, category: str, days: int, digest: str
) -> bool:
    try:
        encoded, supplied = token.rsplit(".", 1)
        expected = hmac.new(
            settings.auth_secret.encode(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        payload = json.loads(encoded)
        return (
            hmac.compare_digest(supplied, expected)
            and payload
            == {
                "category": category,
                "days": days,
                "digest": digest,
                "exp": payload["exp"],
            }
            and int(payload["exp"]) >= int(time.time())
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


class SystemResourceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def inventory(self) -> SystemInventoryRead:
        disk_root = Path(settings.supplier_artifact_root)
        existing_root = next(
            (parent for parent in (disk_root, *disk_root.parents) if parent.exists()),
            Path.cwd(),
        )
        disk = shutil.disk_usage(existing_root)
        memory_total, memory_used = _memory_usage()
        categories: list[StorageCategoryRead] = []
        for policy in storage_policies():
            files, truncated = _walk_files(
                policy.root, settings.system_inventory_max_files
            )
            categories.append(
                StorageCategoryRead(
                    code=policy.code,
                    label=policy.label,
                    size_bytes=sum(item.size for item in files),
                    file_count=len(files),
                    status="UPOZORENJE" if truncated else "OK",
                    cleanup_allowed=policy.cleanup_allowed,
                    protection_reason=policy.protection_reason,
                    scan_truncated=truncated,
                )
            )
        database_size = await self.session.scalar(
            text("SELECT pg_database_size(current_database())")
        )
        return SystemInventoryRead(
            runtime=RuntimeRead(
                processor_count=os.cpu_count() or 1,
                processor_load_percent=_processor_load(),
                memory=_capacity(
                    memory_total,
                    memory_used,
                    settings.system_memory_warning_percent,
                    settings.system_memory_critical_percent,
                ),
                disk=_capacity(
                    disk.total,
                    disk.used,
                    settings.system_disk_warning_percent,
                    settings.system_disk_critical_percent,
                ),
                measured_at=datetime.now(UTC),
            ),
            database_size_bytes=int(database_size or 0),
            categories=categories,
        )


__all__ = [
    "SystemResourceService",
    "candidate_digest",
    "cleanup_candidates",
    "create_confirmation_token",
    "verify_confirmation_token",
]
