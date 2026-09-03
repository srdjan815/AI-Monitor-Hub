from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.pipeline_repository import SupplierPipelineRepository
from app.modules.suppliers.schema_inference_engine import SchemaStructureDetector
from app.modules.suppliers.schema_record_schemas import SchemaRecordRead
from app.modules.suppliers.schema_service_support import SupplierSchemaServiceSupport
from app.modules.suppliers.source_artifact_service import SupplierSourceArtifactService

FIELD_ALIASES = {
    "manufacturer_code": (
        "sifraproizvodjaca",
        "proizvodjackasifra",
        "manufacturerpartnumber",
        "manufacturer_code",
        "mpn",
        "partnumber",
        "sifraartikla",
        "sifra",
        "code",
        "sku",
    ),
    "ean": ("ean", "barcode", "barkod", "gtin"),
    "name": (
        "nazivartikla",
        "nazivproizvoda",
        "productname",
        "artikal",
        "naziv",
        "name",
        "description",
        "opis",
    ),
    "price": ("veleprodajnacena", "nabavnacena", "prodajnacena", "unitprice", "price", "cena"),
}


class SupplierSchemaRecordService(SupplierSchemaServiceSupport):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.pipeline = SupplierPipelineRepository(session)
        self.artifacts = SupplierSourceArtifactService(session)

    async def list_records(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SchemaRecordRead], int, int]:
        await self._source(supplier_id, source_id)
        profile = await self._profile(source_id, profile_id)
        if profile.baseline_artifact_id is None:
            supplier_error(
                409,
                "schema_profile_artifact_missing",
                "Izabrani cenovnik nema sačuvan originalni Artifact",
            )
        artifact = await self.pipeline.artifact(
            source_id, profile.baseline_artifact_id
        )
        if artifact is None:
            supplier_error(
                404,
                "supplier_source_artifact_not_found",
                "Originalni cenovnik nije pronađen",
            )
        structure = SchemaStructureDetector.detect(
            self.artifacts.load(artifact), row_limit=None
        )
        aliases = self._columns(structure.rows)
        needle = self._text(search).casefold()
        grouped: dict[tuple[str, ...], SchemaRecordRead] = {}
        for record_number, raw in enumerate(structure.rows, 1):
            values = {
                str(key): self._value(value)
                for key, value in raw.items()
            }
            if needle and not any(
                needle in (value or "").casefold() for value in values.values()
            ):
                continue
            summary = {
                field: values.get(column) if column else None
                for field, column in aliases.items()
            }
            ean = (summary["ean"] or "").strip().casefold()
            code = (summary["manufacturer_code"] or "").strip().casefold()
            name = (summary["name"] or "").strip().casefold()
            price = (summary["price"] or "").strip().casefold()
            key: tuple[str, ...]
            if ean:
                key = ("ean", ean)
            elif code:
                key = ("code", code)
            elif name or price:
                key = ("name-price", name, price)
            else:
                key = tuple(
                    f"{name.casefold()}={value or ''}"
                    for name, value in values.items()
                )
            existing = grouped.get(key)
            if existing is not None:
                existing.duplicate_count += 1
                continue
            grouped[key] = SchemaRecordRead(
                record_number=record_number,
                **summary,
                duplicate_count=1,
                values=values,
            )
        records = list(grouped.values())
        return records[offset : offset + limit], len(records), structure.record_count

    @classmethod
    def _columns(
        cls, rows: list[dict[str, object]]
    ) -> dict[str, str | None]:
        columns = list(dict.fromkeys(str(key) for row in rows for key in row))
        normalized = {column: cls._normalize(column) for column in columns}
        result: dict[str, str | None] = {}
        for field, aliases in FIELD_ALIASES.items():
            result[field] = next(
                (
                    column
                    for alias in aliases
                    for column, value in normalized.items()
                    if value == cls._normalize(alias)
                    or cls._normalize(alias) in value
                ),
                None,
            )
        return result

    @staticmethod
    def _normalize(value: str) -> str:
        ascii_value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode()
            .lower()
        )
        return re.sub(r"[^a-z0-9]+", "", ascii_value)

    @staticmethod
    def _value(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text[:4000] if text else None

    @staticmethod
    def _text(value: str | None) -> str:
        return re.sub(r"\s+", " ", (value or "").strip())[:200]


__all__ = ["SupplierSchemaRecordService"]
