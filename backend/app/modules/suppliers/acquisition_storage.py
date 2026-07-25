from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from pathlib import Path

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
    StoredArtifact,
)


class LocalArtifactStorage:
    def __init__(self, root: Path, maximum_bytes: int) -> None:
        self.root = root.resolve()
        self.maximum_bytes = maximum_bytes

    def store(self, payload: AcquiredPayload) -> StoredArtifact:
        if not payload.content:
            raise AcquisitionFailure(
                "acquisition_empty_artifact", "Ulazni fajl je prazan"
            )
        if len(payload.content) > self.maximum_bytes:
            raise AcquisitionFailure(
                "acquisition_artifact_too_large",
                "Ulazni fajl prelazi dozvoljenu veličinu",
            )
        filename = self._safe_display_name(payload.original_filename)
        suffix = Path(filename).suffix.lower() if filename else ""
        self.root.mkdir(parents=True, exist_ok=True)
        generated = f"{uuid.uuid4().hex}{suffix}"
        destination = (self.root / generated).resolve()
        if destination.parent != self.root:
            raise AcquisitionFailure(
                "acquisition_unsafe_filename",
                "Naziv fajla nije bezbedan",
            )
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.root,
                prefix=".upload-",
                delete=False,
            ) as handle:
                temporary = handle.name
                handle.write(payload.content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except Exception:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise
        return StoredArtifact(
            reference=generated,
            checksum=hashlib.sha256(payload.content).hexdigest(),
            size_bytes=len(payload.content),
            content_type=payload.content_type,
            original_filename=filename,
        )

    def delete(self, reference: str) -> None:
        if not reference or Path(reference).name != reference:
            return
        target = (self.root / reference).resolve()
        if target.parent == self.root:
            target.unlink(missing_ok=True)

    def load(self, reference: str) -> bytes:
        if not reference or Path(reference).name != reference:
            raise AcquisitionFailure(
                "acquisition_artifact_missing",
                "Sačuvani artefakt nije dostupan",
            )
        target = (self.root / reference).resolve()
        if target.parent != self.root or not target.is_file():
            raise AcquisitionFailure(
                "acquisition_artifact_missing",
                "Sačuvani artefakt nije dostupan",
            )
        return target.read_bytes()

    @staticmethod
    def _safe_display_name(filename: str | None) -> str | None:
        if filename is None:
            return None
        normalized = filename.strip()
        if (
            not normalized
            or len(normalized) > 500
            or Path(normalized).name != normalized
            or "/" in normalized
            or "\\" in normalized
            or "\x00" in normalized
        ):
            raise AcquisitionFailure(
                "acquisition_unsafe_filename",
                "Naziv fajla nije bezbedan",
            )
        return normalized


__all__ = ["LocalArtifactStorage"]
