from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path

from app.modules.suppliers.snapshot_contracts import (
    SnapshotFailure,
    StoredSnapshotArchive,
)


class LocalSnapshotArchiveStorage:
    def __init__(self, root: Path, maximum_bytes: int) -> None:
        self.root = root.resolve()
        self.maximum_bytes = maximum_bytes

    def allocate(self, snapshot_code: str) -> tuple[Path, Path]:
        self.root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(self.root).free < self.maximum_bytes:
            raise SnapshotFailure(
                "snapshot_archive_space_insufficient",
                "Nema dovoljno slobodnog prostora za bezbedan izvoz arhive",
            )
        token = uuid.uuid4().hex
        temporary = (self.root / f".{token}.tmp").resolve()
        destination = (self.root / f"{snapshot_code}-{token}.zip").resolve()
        self._under_root(temporary)
        self._under_root(destination)
        return temporary, destination

    def finalize(
        self,
        temporary: Path,
        destination: Path,
    ) -> StoredSnapshotArchive:
        self._under_root(temporary)
        self._under_root(destination)
        size = temporary.stat().st_size
        if size > self.maximum_bytes:
            temporary.unlink(missing_ok=True)
            raise SnapshotFailure(
                "snapshot_archive_too_large",
                "Snapshot arhiva prelazi dozvoljenu veličinu",
            )
        if destination.exists():
            temporary.unlink(missing_ok=True)
            raise SnapshotFailure(
                "snapshot_archive_exists",
                "Snapshot arhiva već postoji",
            )
        os.replace(temporary, destination)
        return StoredSnapshotArchive(
            reference=destination.name,
            checksum=self._checksum(destination),
            size_bytes=size,
            path=destination,
        )

    def resolve(self, reference: str) -> Path:
        if not reference or Path(reference).name != reference:
            raise SnapshotFailure(
                "snapshot_archive_reference_invalid",
                "Referenca Snapshot arhive nije bezbedna",
            )
        target = (self.root / reference).resolve()
        self._under_root(target)
        if not target.is_file():
            raise SnapshotFailure(
                "snapshot_archive_missing",
                "Snapshot arhiva nije dostupna",
            )
        return target

    def remove_temporary(self, temporary: Path) -> None:
        try:
            self._under_root(temporary)
        except SnapshotFailure:
            return
        temporary.unlink(missing_ok=True)

    def delete(self, reference: str) -> None:
        try:
            self.resolve(reference).unlink(missing_ok=True)
        except SnapshotFailure:
            return

    def _under_root(self, path: Path) -> None:
        if path.parent != self.root:
            raise SnapshotFailure(
                "snapshot_archive_path_invalid",
                "Putanja Snapshot arhive nije dozvoljena",
            )

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


__all__ = ["LocalSnapshotArchiveStorage"]
