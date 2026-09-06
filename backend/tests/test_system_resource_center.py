from __future__ import annotations

import os
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import httpx
from sqlalchemy import delete

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.db.session import AsyncSessionLocal
from app.modules.system.models import (
    ArtifactArchiveSetting,
    ArtifactArchiveTransfer,
    SystemCleanupAudit,
)
from app.modules.system.artifact_archive_service import (
    ArchiveConfigurationError,
    ArtifactArchiveService,
    _target_root,
    artifact_archive_warnings,
    copy_verified_artifact,
)
from app.modules.suppliers.acquisition_contracts import AcquiredPayload
from app.modules.suppliers.acquisition_storage import LocalArtifactStorage
from app.modules.suppliers.source_artifact_service import SupplierSourceArtifactService
from app.modules.system.resource_service import (
    candidate_digest,
    cleanup_candidates,
    create_confirmation_token,
    verify_confirmation_token,
)


def _old(path: Path, days: int = 40) -> None:
    moment = (datetime.now(UTC) - timedelta(days=days)).timestamp()
    os.utime(path, (moment, moment))


def test_cleanup_audit_model_declares_migrated_created_at_index() -> None:
    index = next(
        item
        for item in SystemCleanupAudit.__table__.indexes
        if item.name == "ix_system_cleanup_audit_created_at"
    )

    assert [column.name for column in index.columns] == ["created_at"]
    assert not index.unique


def test_cleanup_is_restricted_to_explicit_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_root = tmp_path / "application" / "logs"
    log_root.mkdir(parents=True)
    old_log = log_root / "application.log.1"
    current_log = log_root / "application.log"
    old_log.write_text("old", encoding="utf-8")
    current_log.write_text("current", encoding="utf-8")
    _old(old_log)
    monkeypatch.setattr(settings, "system_log_root", str(log_root))

    candidates = cleanup_candidates("LOGOVI", 30)

    assert [candidate.path for candidate in candidates] == [old_log]
    with pytest.raises(ValueError, match="nije dozvoljena"):
        cleanup_candidates("CENOVNICI", 30)


def test_cleanup_ignores_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_root = tmp_path / "application" / "logs"
    protected_root = tmp_path / "protected"
    log_root.mkdir(parents=True)
    protected_root.mkdir()
    protected = protected_root / "business.txt"
    protected.write_text("never delete", encoding="utf-8")
    link = log_root / "linked.log"
    try:
        link.symlink_to(protected)
    except OSError:
        pytest.skip("Platforma ne dozvoljava kreiranje simboličkog linka")
    _old(protected)
    monkeypatch.setattr(settings, "system_log_root", str(log_root))

    assert cleanup_candidates("LOGOVI", 30) == []
    assert protected.read_text(encoding="utf-8") == "never delete"


def test_confirmation_token_binds_category_age_and_exact_file_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_root = tmp_path / "application" / "logs"
    log_root.mkdir(parents=True)
    log = log_root / "old.log"
    log.write_text("first", encoding="utf-8")
    _old(log)
    monkeypatch.setattr(settings, "system_log_root", str(log_root))
    original = cleanup_candidates("LOGOVI", 30)
    digest = candidate_digest(original)
    token, _ = create_confirmation_token("LOGOVI", 30, digest)

    assert verify_confirmation_token(token, "LOGOVI", 30, digest)
    assert not verify_confirmation_token(token, "LOGOVI", 31, digest)
    assert not verify_confirmation_token(token + "x", "LOGOVI", 30, digest)

    log.write_text("changed", encoding="utf-8")
    _old(log)
    changed_digest = candidate_digest(cleanup_candidates("LOGOVI", 30))
    assert changed_digest != digest
    assert not verify_confirmation_token(token, "LOGOVI", 30, changed_digest)


def test_unsafe_broad_root_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "system_log_root", str(Path("/").resolve()))

    with pytest.raises(RuntimeError, match="nije dovoljno uska"):
        cleanup_candidates("LOGOVI", 30)


def test_archive_copy_is_content_addressed_verified_and_idempotent(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source" / "price-list.json"
    target = tmp_path / "mounted" / "archive"
    source.parent.mkdir()
    source.write_bytes(b'{"products": [1, 2, 3]}')
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    first = copy_verified_artifact(source, target, checksum, source.stat().st_size)
    second = copy_verified_artifact(source, target, checksum, source.stat().st_size)

    assert first == second
    assert (target / first).read_bytes() == source.read_bytes()
    assert source.exists()
    assert len([path for path in target.rglob("*") if path.is_file()]) == 1


def test_archive_target_is_confined_to_configured_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mount = tmp_path / "application" / "archive-targets"
    monkeypatch.setattr(settings, "system_archive_mount_root", str(mount))

    assert _target_root("cenovnici/2026") == mount / "cenovnici" / "2026"
    with pytest.raises(ArchiveConfigurationError, match="relativna"):
        _target_root("../izvan")
    with pytest.raises(ArchiveConfigurationError, match="relativna"):
        _target_root("/apsolutna")

    monkeypatch.setattr(settings, "system_archive_mount_root", str(Path("/").resolve()))
    with pytest.raises(ArchiveConfigurationError, match="dovoljno usko"):
        _target_root("cenovnici")


def test_archive_copy_rejects_corrupt_existing_blob(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"ispravan cenovnik")
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    target = tmp_path / "mounted" / "archive"
    destination = target / "blobs" / "sha256" / checksum[:2] / checksum
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"ostecen sadrzaj")

    with pytest.raises(OSError, match="Checksum"):
        copy_verified_artifact(source, target, checksum, destination.stat().st_size)


@pytest.mark.asyncio
async def test_archive_failure_is_warning_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    monkeypatch.setattr(
        ArtifactArchiveService,
        "archive_if_configured",
        AsyncMock(side_effect=OSError("NAS nije dostupan")),
    )

    warnings = await artifact_archive_warnings(session, uuid.uuid4())

    assert warnings == ["Arhiviranje nije uspelo; lokalna kopija čeka novi pokušaj."]
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_identical_imports_share_one_local_blob(tmp_path: Path) -> None:
    artifacts: list[object] = []

    class Repository:
        async def lock_artifact_checksum(self, checksum: str) -> None:
            assert len(checksum) == 64

        async def artifact_by_checksum(self, checksum: str, size: int):
            return artifacts[0] if artifacts else None

        async def add(self, artifact: object) -> None:
            artifacts.append(artifact)

    session = AsyncMock()
    service = SupplierSourceArtifactService(session)
    service.repository = Repository()  # type: ignore[assignment]
    service.storage = LocalArtifactStorage(tmp_path / "artifacts", 1_000_000)
    payload = AcquiredPayload(
        content=b'[{"product_code":"A-1","price":10}]',
        content_type="application/json",
        original_filename="cenovnik.json",
        source_metadata={},
    )
    source_id = uuid.uuid4()

    first = await service.store(source_id, payload)
    second = await service.store(source_id, payload)

    # Svaki zapis zadrzava jedinstvenu referencu radi sledljivosti i rollback-a,
    # dok hard-link obezbedjuje da identican sadrzaj fizicki zauzima prostor jednom.
    assert first.storage_reference != second.storage_reference
    stored = list((tmp_path / "artifacts").iterdir())
    assert len(stored) == 2
    assert stored[0].stat().st_ino == stored[1].stat().st_ino


def _bearer(subject: str, role: str) -> dict[str, str]:
    token = create_access_token(subject, (role,))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_system_endpoints_are_admin_only_and_inventory_is_operational() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.get(
            "/api/v1/system/resources", headers=_bearer("reader", "read_only")
        )
        inventory = await client.get(
            "/api/v1/system/resources", headers=_bearer("admin", "system_admin")
        )
        preview = await client.post(
            "/api/v1/system/resources/cleanup/preview",
            headers=_bearer("admin", "system_admin"),
            json={"category": "LOGOVI", "older_than_days": 30},
        )

    assert denied.status_code == 403
    assert inventory.status_code == 200, inventory.text
    body = inventory.json()
    assert body["database_size_bytes"] > 0
    assert {item["code"] for item in body["categories"]} == {
        "LOGOVI",
        "PRIVREMENI_FAJLOVI",
        "CENOVNICI",
        "SNAPSHOT_ARHIVE",
    }
    assert preview.status_code == 200, preview.text
    assert preview.json()["confirmation_token"]


@pytest.mark.asyncio
async def test_confirmed_cleanup_deletes_only_previewed_files_and_writes_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_root = tmp_path / "application" / "logs"
    log_root.mkdir(parents=True)
    old_log = log_root / "application.log.1"
    current_log = log_root / "application.log"
    old_log.write_text("old", encoding="utf-8")
    current_log.write_text("current", encoding="utf-8")
    _old(old_log)
    monkeypatch.setattr(settings, "system_log_root", str(log_root))
    headers = _bearer("cleanup-admin", "system_admin")
    request = {"category": "LOGOVI", "older_than_days": 30}
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        preview = await client.post(
            "/api/v1/system/resources/cleanup/preview",
            headers=headers,
            json=request,
        )
        assert preview.status_code == 200, preview.text
        result = await client.post(
            "/api/v1/system/resources/cleanup/execute",
            headers=headers,
            json={
                **request,
                "confirmation_token": preview.json()["confirmation_token"],
            },
        )
        replay = await client.post(
            "/api/v1/system/resources/cleanup/execute",
            headers=headers,
            json={
                **request,
                "confirmation_token": preview.json()["confirmation_token"],
            },
        )
        audit = await client.get(
            "/api/v1/system/resources/cleanup/audit", headers=headers
        )

    assert result.status_code == 200, result.text
    assert result.json()["status"] == "SUCCEEDED"
    assert result.json()["deleted_files"] == 1
    assert replay.status_code == 409
    assert not old_log.exists()
    assert current_log.read_text(encoding="utf-8") == "current"
    assert audit.status_code == 200, audit.text
    record = next(
        item for item in audit.json() if item["id"] == result.json()["audit_id"]
    )
    assert record["actor_id"] == "cleanup-admin"
    assert record["deleted_files"] == 1


@pytest.mark.asyncio
async def test_archive_setting_is_mount_bounded_and_connection_is_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mount_root = tmp_path / "application" / "archive-targets"
    monkeypatch.setattr(settings, "system_archive_mount_root", str(mount_root))
    headers = _bearer("archive-admin", "system_admin")
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncSessionLocal() as session:
        await session.execute(delete(ArtifactArchiveTransfer))
        await session.execute(delete(ArtifactArchiveSetting))
        await session.commit()
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            saved = await client.put(
                "/api/v1/system/resources/artifact-archive/setting",
                headers=headers,
                json={
                    "display_name": "Test NAS",
                    "relative_path": "cenovnici/test",
                    "enabled": True,
                    "local_retention_days": 30,
                    "expected_version": None,
                },
            )
            tested = await client.post(
                "/api/v1/system/resources/artifact-archive/test", headers=headers
            )
            rejected = await client.put(
                "/api/v1/system/resources/artifact-archive/setting",
                headers=headers,
                json={
                    "display_name": "Unsafe",
                    "relative_path": "../outside",
                    "enabled": True,
                    "local_retention_days": 30,
                    "expected_version": saved.json().get("version"),
                },
            )
        assert saved.status_code == 200, saved.text
        assert tested.status_code == 200, tested.text
        assert tested.json()["status"] == "SUCCEEDED"
        assert rejected.status_code == 409
        assert (mount_root / "cenovnici" / "test").is_dir()
        assert list((mount_root / "cenovnici" / "test").iterdir()) == []
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(ArtifactArchiveTransfer))
            await session.execute(delete(ArtifactArchiveSetting))
            await session.commit()
