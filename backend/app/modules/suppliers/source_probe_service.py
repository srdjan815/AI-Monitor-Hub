from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.suppliers.acquisition_adapters import (
    SourceAdapterRegistry,
    UrllibHttpClient,
)
from app.modules.suppliers.acquisition_parsers import XlsxParser
from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
)
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.source_probe_schemas import (
    SourceProbeResult,
    SourceProbeStep,
)
from app.modules.suppliers.source_repository import SupplierSourceRepository
from app.modules.suppliers.source_secrets import source_secret_provider
from app.modules.suppliers.source_validation_service import (
    SupplierSourceValidationService,
)


class SupplierSourceProbeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sources = SupplierSourceRepository(session)
        self.suppliers = SupplierRepository(session)
        self.validator = SupplierSourceValidationService()
        self.adapters = SourceAdapterRegistry(
            UrllibHttpClient(),
            source_secret_provider,
            settings.acquisition_max_artifact_bytes,
        )

    async def probe(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        supplied: AcquiredPayload | None = None,
    ) -> SourceProbeResult:
        supplier = await self.suppliers.get_supplier(supplier_id)
        if supplier is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        source = await self.sources.get_source(supplier_id, source_id, for_update=True)
        if source is None:
            supplier_error(404, "supplier_source_not_found", "Konekcija nije pronađena")
        if not source.is_active:
            supplier_error(409, "supplier_source_inactive", "Arhivirana konekcija se ne može testirati")
        if supplied is not None and source.source_type not in {
            "MANUAL_UPLOAD",
            "CSV",
            "EXCEL",
            "XML",
        }:
            supplier_error(
                409,
                "supplier_source_probe_upload_not_allowed",
                "Probni fajl je dozvoljen samo za ručno učitavanje",
            )

        started = time.monotonic()
        tested_at = datetime.now(UTC)
        try:
            self.validator.normalize_configuration(
                source.source_type, source.configuration
            )
            payload = await self.adapters.resolve(source.source_type).acquire(
                source, supplied
            )
            if not payload.content:
                raise AcquisitionFailure(
                    "acquisition_empty_artifact",
                    "Dobavljač je vratio prazan cenovnik",
                )
            detected, preview, count = self._analyse(
                payload.content,
                payload.content_type,
                payload.original_filename,
            )
            checksum = hashlib.sha256(payload.content).hexdigest()
            message = "PROBE_OK: Konekcija radi i cenovnik je uspešno preuzet"
            await self._save_result(source, tested_at, "VALID", message)
            return SourceProbeResult(
                successful=True,
                tested_at=tested_at,
                duration_ms=int((time.monotonic() - started) * 1000),
                detected_format=detected,
                size_bytes=len(payload.content),
                approximate_record_count=count,
                message=message.removeprefix("PROBE_OK: "),
                steps=self._steps(True),
                preview=preview[:10],
                http_status=self._int_metadata(payload, "http_status"),
                content_type=payload.content_type,
                checksum=checksum,
            )
        except AcquisitionFailure as exc:
            message = self._safe_message(exc)
            await self._save_result(
                source,
                tested_at,
                "INVALID",
                f"PROBE_FAILED: {message}",
            )
            return SourceProbeResult(
                successful=False,
                tested_at=tested_at,
                duration_ms=int((time.monotonic() - started) * 1000),
                detected_format=None,
                size_bytes=0,
                approximate_record_count=None,
                message=message,
                steps=self._steps(False),
                preview=[],
            )

    async def _save_result(
        self, source: SupplierSource, tested_at: datetime, status: str, message: str
    ) -> None:
        await self.sources.update_source(
            source,
            {
                "last_validation_at": tested_at,
                "last_validation_status": status,
                "last_validation_message": message[:1000],
                "version": source.version + 1,
            },
        )
        await self.session.commit()

    @staticmethod
    def _steps(successful: bool) -> list[SourceProbeStep]:
        labels = [
            "Podešavanja su ispravna",
            "Adresa je dostupna",
            "Prijava je uspešna",
            "Cenovnik je pronađen",
            "Fajl je preuzet",
            "Format je prepoznat",
            "Sadržaj može da se otvori",
            "Pronađeni su zapisi",
        ]
        return [
            SourceProbeStep(label=label, successful=successful) for label in labels
        ]

    @staticmethod
    def _safe_message(exc: AcquisitionFailure) -> str:
        if exc.code == "acquisition_source_type_unsupported":
            return (
                "Automatsko preuzimanje za ovaj tip izvora biće dostupno "
                "u narednoj fazi razvoja."
            )
        return exc.safe_message

    @staticmethod
    def _int_metadata(payload: AcquiredPayload, key: str) -> int | None:
        value = payload.source_metadata.get(key)
        return value if isinstance(value, int) else None

    @classmethod
    def _analyse(
        cls,
        content: bytes,
        content_type: str | None,
        filename: str | None,
    ) -> tuple[str, list[dict[str, object]], int]:
        stripped = content.lstrip()
        name = (filename or "").lower()
        media = (content_type or "").lower()
        if "html" in media or stripped[:100].lower().startswith(
            (b"<!doctype html", b"<html")
        ):
            raise AcquisitionFailure(
                "acquisition_unexpected_html",
                "Dobavljač je vratio HTML stranicu umesto cenovnika",
            )
        if content.startswith(b"PK") or name.endswith(".xlsx"):
            return cls._xlsx(content)
        if stripped.startswith(b"<") or "xml" in media or name.endswith(".xml"):
            return cls._xml(content)
        if stripped.startswith((b"{", b"[")) or "json" in media:
            return cls._json(content)
        return cls._csv(content)

    @classmethod
    def _xml(
        cls, content: bytes
    ) -> tuple[str, list[dict[str, object]], int]:
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise AcquisitionFailure(
                "acquisition_parse_failed",
                "Preuzeti fajl nije ispravan XML cenovnik",
            ) from exc
        groups: dict[str, list[ET.Element]] = {}
        for child in root.iter():
            groups.setdefault(child.tag, []).append(child)
        candidates = [rows for rows in groups.values() if len(rows) > 1]
        rows = max(candidates, key=len) if candidates else list(root)
        if not rows:
            raise AcquisitionFailure(
                "acquisition_no_records",
                "U preuzetom cenovniku nisu pronađeni zapisi",
            )
        preview: list[dict[str, object]] = [
            {
                item.tag.rsplit("}", 1)[-1]: (item.text or "").strip()
                for item in row
            }
            for row in rows[:10]
        ]
        return "XML", cls._sanitize_preview(preview), len(rows)

    @classmethod
    def _json(
        cls, content: bytes
    ) -> tuple[str, list[dict[str, object]], int]:
        try:
            value = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcquisitionFailure(
                "acquisition_parse_failed",
                "Preuzeti JSON cenovnik nije ispravan",
            ) from exc
        rows = value if isinstance(value, list) else [value]
        preview = [row for row in rows[:10] if isinstance(row, dict)]
        if not preview:
            raise AcquisitionFailure(
                "acquisition_no_records",
                "U preuzetom cenovniku nisu pronađeni zapisi",
            )
        return "JSON", cls._sanitize_preview(preview), len(rows)

    @classmethod
    def _xlsx(cls, content: bytes) -> tuple[str, list[dict[str, object]], int]:
        rows = XlsxParser().parse(content, {})
        if not rows:
            raise AcquisitionFailure(
                "acquisition_no_records",
                "U preuzetom cenovniku nisu pronađeni zapisi",
            )
        return "EXCEL", cls._sanitize_preview(rows[:10]), len(rows)

    @classmethod
    def _csv(
        cls, content: bytes
    ) -> tuple[str, list[dict[str, object]], int]:
        try:
            text = content.decode("utf-8-sig")
            rows = list(csv.DictReader(io.StringIO(text)))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise AcquisitionFailure(
                "acquisition_parse_failed",
                "Preuzeti fajl nije u prepoznatom formatu",
            ) from exc
        if not rows:
            raise AcquisitionFailure(
                "acquisition_no_records",
                "U preuzetom cenovniku nisu pronađeni zapisi",
            )
        preview: list[dict[str, object]] = [
            {key: value for key, value in row.items()} for row in rows[:10]
        ]
        return "CSV", cls._sanitize_preview(preview), len(rows)

    @staticmethod
    def _sanitize_preview(
        rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        sensitive = {
            "password",
            "lozinka",
            "secret",
            "token",
            "api_key",
            "apikey",
            "authorization",
            "username",
            "korisnickoime",
        }
        sanitized: list[dict[str, object]] = []
        for row in rows:
            clean: dict[str, object] = {}
            for key, value in row.items():
                normalized = str(key).lower().replace("-", "_")
                if any(marker in normalized for marker in sensitive):
                    clean[str(key)] = "[REDACTED]"
                elif isinstance(value, (str, int, float, bool)) or value is None:
                    clean[str(key)] = (
                        value[:500] if isinstance(value, str) else value
                    )
                else:
                    clean[str(key)] = str(value)[:500]
            sanitized.append(clean)
        return sanitized


__all__ = ["SupplierSourceProbeService"]
