from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class SnapshotFailure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code[:100]
        self.safe_message = message[:1000]


@dataclass(frozen=True, slots=True)
class StoredSnapshotArchive:
    reference: str
    checksum: str
    size_bytes: int
    path: Path


class SnapshotArchiveStorage(Protocol):
    def allocate(self, snapshot_code: str) -> tuple[Path, Path]: ...

    def finalize(self, temporary: Path, destination: Path) -> StoredSnapshotArchive: ...

    def resolve(self, reference: str) -> Path: ...

    def remove_temporary(self, temporary: Path) -> None: ...

    def delete(self, reference: str) -> None: ...


@dataclass(frozen=True, slots=True)
class SnapshotItemPayload:
    id: str
    source_staged_record_id: str
    record_number: int
    source_key: str | None
    source_identifier: str | None
    item_fingerprint: str
    mapped_data: dict[str, object]
    source_image_links: list[dict[str, object]]


@dataclass(frozen=True, slots=True)
class VerifiedArchive:
    snapshot: dict[str, object]
    manifest: dict[str, object]


__all__ = [
    "SnapshotArchiveStorage",
    "SnapshotFailure",
    "SnapshotItemPayload",
    "StoredSnapshotArchive",
    "VerifiedArchive",
]
