from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Iterable

from app.core.config import settings
from app.modules.suppliers.snapshot_contracts import (
    SnapshotFailure,
    SnapshotItemPayload,
    VerifiedArchive,
)
from app.modules.suppliers.snapshot_fingerprints import canonical_json

FORMAT_VERSION = 1
MANIFEST_VERSION = 1
_ALLOWED_FILES = {
    "manifest.json",
    "snapshot.json",
    "snapshot_items.jsonl",
    "checksums.json",
    "acquisition_artifact.bin",
}
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class SnapshotArchiveFormat:
    def write(
        self,
        path: Path,
        *,
        snapshot: dict[str, object],
        items: Iterable[SnapshotItemPayload],
        item_count: int,
        acquisition_artifact: bytes | None = None,
        acquisition_artifact_metadata: dict[str, object] | None = None,
    ) -> None:
        checksums: dict[str, str] = {}
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            snapshot_bytes = canonical_json(snapshot)
            self._write_bytes(archive, "snapshot.json", snapshot_bytes)
            checksums["snapshot.json"] = hashlib.sha256(snapshot_bytes).hexdigest()
            item_digest = hashlib.sha256()
            with archive.open(self._info("snapshot_items.jsonl"), "w") as handle:
                for item in items:
                    line = (
                        canonical_json(
                            {
                                "id": item.id,
                                "source_staged_record_id": item.source_staged_record_id,
                                "record_number": item.record_number,
                                "source_key": item.source_key,
                                "source_identifier": item.source_identifier,
                                "item_fingerprint": item.item_fingerprint,
                                "mapped_data": item.mapped_data,
                                "source_image_links": item.source_image_links,
                            }
                        )
                        + b"\n"
                    )
                    item_digest.update(line)
                    handle.write(line)
            checksums["snapshot_items.jsonl"] = item_digest.hexdigest()
            if acquisition_artifact is not None:
                self._write_bytes(
                    archive,
                    "acquisition_artifact.bin",
                    acquisition_artifact,
                )
                checksums["acquisition_artifact.bin"] = hashlib.sha256(
                    acquisition_artifact
                ).hexdigest()
            checksum_bytes = canonical_json(checksums)
            self._write_bytes(archive, "checksums.json", checksum_bytes)
            manifest = {
                "archive_format_version": FORMAT_VERSION,
                "archive_manifest_version": MANIFEST_VERSION,
                "application": "AI Monitor Hub",
                "compatibility": {"minimum_snapshot_format_version": 1},
                "created_at": datetime.now(UTC).isoformat(),
                "snapshot_id": snapshot["id"],
                "snapshot_code": snapshot["snapshot_code"],
                "supplier_id": snapshot["supplier_id"],
                "source_connection_id": snapshot["source_connection_id"],
                "schema_version_reference": snapshot["schema_version_reference"],
                "mapping_version_reference": snapshot["mapping_version_reference"],
                "snapshot_fingerprint": snapshot["snapshot_fingerprint"],
                "item_count": item_count,
                "checksums": checksums,
                "acquisition_artifact": acquisition_artifact_metadata,
            }
            self._write_bytes(archive, "manifest.json", canonical_json(manifest))

    def verify(
        self,
        path: Path,
        *,
        expected_snapshot_id: str,
        expected_fingerprint: str,
        expected_item_count: int,
    ) -> VerifiedArchive:
        try:
            with zipfile.ZipFile(path) as archive:
                self._validate_members(archive)
                manifest = self._json_object(archive.read("manifest.json"))
                if manifest.get("archive_format_version") != FORMAT_VERSION:
                    raise SnapshotFailure(
                        "snapshot_archive_version_unsupported",
                        "Verzija Snapshot arhive nije podržana",
                    )
                if manifest.get("archive_manifest_version") != MANIFEST_VERSION:
                    raise SnapshotFailure(
                        "snapshot_manifest_version_unsupported",
                        "Verzija manifesta nije podržana",
                    )
                if manifest.get("snapshot_id") != expected_snapshot_id:
                    raise SnapshotFailure(
                        "snapshot_archive_identity_mismatch",
                        "Arhiva ne pripada traženom Snapshot-u",
                    )
                if manifest.get("snapshot_fingerprint") != expected_fingerprint:
                    raise SnapshotFailure(
                        "snapshot_archive_fingerprint_mismatch",
                        "Fingerprint Snapshot arhive nije ispravan",
                    )
                checksums = self._json_object(archive.read("checksums.json"))
                if manifest.get("checksums") != checksums:
                    raise SnapshotFailure(
                        "snapshot_archive_manifest_checksum_mismatch",
                        "Manifest checksum zapisi nisu usklađeni",
                    )
                for name, expected in checksums.items():
                    if not isinstance(expected, str):
                        raise ValueError("checksum")
                    digest = self._member_checksum(archive, name)
                    if digest != expected:
                        raise SnapshotFailure(
                            "snapshot_archive_file_corrupt",
                            "Sadržaj Snapshot arhive nije ispravan",
                        )
                snapshot = self._json_object(archive.read("snapshot.json"))
                if (
                    snapshot.get("id") != expected_snapshot_id
                    or snapshot.get("snapshot_fingerprint") != expected_fingerprint
                    or snapshot.get("total_items") != expected_item_count
                    or manifest.get("item_count") != expected_item_count
                ):
                    raise SnapshotFailure(
                        "snapshot_archive_metadata_mismatch",
                        "Snapshot metapodaci u arhivi nisu usklađeni",
                    )
                with archive.open("snapshot_items.jsonl") as handle:
                    item_count = sum(1 for _ in self._read_items(handle))
                if item_count != expected_item_count:
                    raise SnapshotFailure(
                        "snapshot_archive_count_mismatch",
                        "Broj stavki u Snapshot arhivi nije ispravan",
                    )
                return VerifiedArchive(snapshot, manifest)
        except SnapshotFailure:
            raise
        except (
            KeyError,
            OSError,
            ValueError,
            zipfile.BadZipFile,
            json.JSONDecodeError,
        ) as exc:
            raise SnapshotFailure(
                "snapshot_archive_invalid",
                "Snapshot arhiva nije ispravna ili čitljiva",
            ) from exc

    @staticmethod
    def _write_bytes(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
        archive.writestr(SnapshotArchiveFormat._info(name), content)

    @staticmethod
    def _info(name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, _ZIP_TIMESTAMP)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o600 << 16
        return info

    @staticmethod
    def _json_object(content: bytes) -> dict[str, object]:
        value = json.loads(content.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("object")
        return value

    @staticmethod
    def _read_items(handle: IO[bytes]) -> Iterable[SnapshotItemPayload]:
        count = 0
        for line in handle:
            value = json.loads(line.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("item")
            mapped = value.get("mapped_data")
            links = value.get("source_image_links")
            if not isinstance(mapped, dict) or not isinstance(links, list):
                raise ValueError("payload")
            count += 1
            if count > settings.snapshot_archive_candidate_limit * 100_000:
                raise ValueError("item limit")
            yield SnapshotItemPayload(
                id=str(value["id"]),
                source_staged_record_id=str(value["source_staged_record_id"]),
                record_number=int(value["record_number"]),
                source_key=(
                    str(value["source_key"])
                    if value.get("source_key") is not None
                    else None
                ),
                source_identifier=(
                    str(value["source_identifier"])
                    if value.get("source_identifier") is not None
                    else None
                ),
                item_fingerprint=str(value["item_fingerprint"]),
                mapped_data=mapped,
                source_image_links=[item for item in links if isinstance(item, dict)],
            )

    def iter_items(self, path: Path) -> Iterable[SnapshotItemPayload]:
        with zipfile.ZipFile(path) as archive:
            self._validate_members(archive)
            with archive.open("snapshot_items.jsonl") as handle:
                yield from self._read_items(handle)

    @staticmethod
    def _member_checksum(archive: zipfile.ZipFile, name: str) -> str:
        digest = hashlib.sha256()
        with archive.open(name) as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _validate_members(archive: zipfile.ZipFile) -> None:
        entries = archive.infolist()
        if not entries or len(entries) > len(_ALLOWED_FILES):
            raise ValueError("entry count")
        total = 0
        for entry in entries:
            if (
                entry.filename not in _ALLOWED_FILES
                or Path(entry.filename).name != entry.filename
                or entry.is_dir()
            ):
                raise SnapshotFailure(
                    "snapshot_archive_path_unsafe",
                    "Snapshot arhiva sadrži nedozvoljenu putanju",
                )
            total += entry.file_size
            if total > settings.snapshot_archive_max_bytes:
                raise ValueError("expanded size")
        required = {
            "manifest.json",
            "snapshot.json",
            "snapshot_items.jsonl",
            "checksums.json",
        }
        if not required.issubset({entry.filename for entry in entries}):
            raise ValueError("required files")


__all__ = ["FORMAT_VERSION", "MANIFEST_VERSION", "SnapshotArchiveFormat"]
