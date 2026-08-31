from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.modules.suppliers.schema_profile_models import SupplierSchemaField


@dataclass
class InferredField:
    entity: SupplierSchemaField
    sample_values: list[str]
    confidence: float


class SchemaFieldInferer:
    STRING_LIMITS = {
        "code": 255,
        "productcode": 255,
        "sku": 255,
        "sifra": 255,
        "partnumber": 255,
        "manufacturercode": 255,
        "name": 255,
        "productname": 255,
        "acname": 255,
        "proizvodjac": 25,
        "manufacturer": 25,
        "brand": 25,
        "grupa": 45,
        "itemgroup": 45,
        "category": 45,
        "accategory": 45,
        "acmaincategory": 45,
        "nadgrupa": 45,
        "naziv": 255,
        "artikal": 255,
        "podkategorija": 50,
        "opis": 150_000,
        "attributes": 150_000,
        "imageurl": 150_000,
        "imageurls": 150_000,
        "urlimages": 150_000,
    }
    DECIMAL_FIELDS = {"cena", "mpcena"}
    PRICE_FIELDS = {
        "price",
        "pricewithdiscounts",
        "pricenotax",
        "retailprice",
        "promotionprice",
        "oldprice",
        "anprice",
        "anoldprice",
        "anretailprice",
        "anrecommendedretailprice",
        "anpromoprice",
    }
    PRICE_PRIORITY = (
        "pricewithdiscounts",
        "anprice",
        "price",
        "cena",
        "mpcena",
        "promotionprice",
        "anpromoprice",
        "retailprice",
        "anretailprice",
        "oldprice",
        "anoldprice",
        "anrecommendedretailprice",
    )
    IDENTIFIER_TEXT_FIELDS = {
        "ean",
        "ean13",
        "ean8",
        "upc",
        "upca",
        "upce",
        "gtin",
        "gtin13",
        "gtin14",
        "barcode",
        "barkod",
    }

    @classmethod
    def fields(
        cls,
        profile_id: uuid.UUID,
        rows: list[dict[str, object]],
    ) -> list[InferredField]:
        headers = list(dict.fromkeys(str(key) for row in rows for key in row))
        primary_price_header = cls._primary_price_header(headers)
        used: set[str] = set()
        result: list[InferredField] = []
        for position, header in enumerate(headers, 1):
            values = [row.get(header) for row in rows]
            samples = [
                str(value).strip()
                for value in values
                if value is not None and str(value).strip()
            ][:10]
            data_type, confidence = cls._type(samples)
            normalized_header = cls._normalized_header(header)
            compact_header = re.sub(r"[^a-z0-9]", "", normalized_header)
            if compact_header in cls.IDENTIFIER_TEXT_FIELDS:
                data_type, confidence = "STRING", 1.0
            elif (
                normalized_header in cls.DECIMAL_FIELDS
                or compact_header in cls.PRICE_FIELDS
            ):
                data_type, confidence = "DECIMAL", 1.0
            nullable = any(
                value is None or not str(value).strip() for value in values
            )
            semantic_limit = cls.STRING_LIMITS.get(
                normalized_header,
                cls.STRING_LIMITS.get(compact_header),
            )
            if compact_header in cls.IDENTIFIER_TEXT_FIELDS:
                semantic_limit = 64
            max_length = (
                semantic_limit
                or max((len(value) for value in samples), default=1)
                if data_type == "STRING"
                else None
            )
            is_price_field = (
                normalized_header in cls.DECIMAL_FIELDS
                or compact_header in cls.PRICE_FIELDS
            )
            is_price = header == primary_price_header
            precision = (
                38
                if is_price_field
                else cls._precision(samples) if data_type == "DECIMAL" else None
            )
            scale = (
                2
                if is_price_field
                else cls._scale(samples) if data_type == "DECIMAL" else None
            )
            result.append(
                InferredField(
                    entity=SupplierSchemaField(
                        schema_profile_id=profile_id,
                        field_code=cls._code(header, used),
                        name=header[:255],
                        position=position,
                        data_type=data_type,
                        required=not nullable,
                        nullable=nullable,
                        max_length=max_length,
                        precision=precision,
                        scale=scale,
                        example_value=samples[0][:4000] if samples else None,
                        path=header[:500],
                        is_identifier=(
                            compact_header in cls.IDENTIFIER_TEXT_FIELDS
                        ),
                        is_price=is_price,
                        is_active=True,
                        version=1,
                    ),
                    sample_values=[value[:500] for value in samples],
                    confidence=confidence,
                )
            )
        return result

    @classmethod
    def _primary_price_header(cls, headers: list[str]) -> str | None:
        candidates = {
            re.sub(r"[^a-z0-9]", "", cls._normalized_header(header)): header
            for header in headers
            if (
                cls._normalized_header(header) in cls.DECIMAL_FIELDS
                or re.sub(
                    r"[^a-z0-9]", "", cls._normalized_header(header)
                )
                in cls.PRICE_FIELDS
            )
        }
        return next(
            (candidates[name] for name in cls.PRICE_PRIORITY if name in candidates),
            next(iter(candidates.values()), None),
        )

    @staticmethod
    def _normalized_header(value: str) -> str:
        return (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode()
            .lower()
            .strip()
        )

    @staticmethod
    def _code(header: str, used: set[str]) -> str:
        value = (
            unicodedata.normalize("NFKD", header)
            .encode("ascii", "ignore")
            .decode()
        )
        value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.-")
        if not value or not value[0].isalpha():
            value = f"field_{value or 'value'}"
        base = value[:90]
        candidate = base
        suffix = 2
        while candidate.lower() in used:
            candidate = f"{base}_{suffix}"[:100]
            suffix += 1
        used.add(candidate.lower())
        return candidate

    @classmethod
    def _type(cls, samples: list[str]) -> tuple[str, float]:
        if not samples:
            return "STRING", 0.0
        checks = (
            ("BOOLEAN", cls._boolean),
            ("INTEGER", cls._integer),
            ("DECIMAL", cls._decimal),
            ("DATETIME", cls._datetime),
            ("DATE", cls._date),
        )
        for name, check in checks:
            matched = sum(check(value) for value in samples)
            if matched == len(samples):
                return name, matched / len(samples)
        return "STRING", 1.0

    @staticmethod
    def _boolean(value: str) -> bool:
        return value.lower() in {"true", "false", "yes", "no", "da", "ne"}

    @staticmethod
    def _integer(value: str) -> bool:
        return re.fullmatch(r"[+-]?\d+", value) is not None

    @staticmethod
    def _decimal(value: str) -> bool:
        try:
            Decimal(value.replace(",", "."))
            return "." in value or "," in value
        except InvalidOperation:
            return False

    @staticmethod
    def _datetime(value: str) -> bool:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return "T" in value or " " in value
        except ValueError:
            return False

    @staticmethod
    def _date(value: str) -> bool:
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _precision(values: list[str]) -> int:
        return max(
            (len(re.sub(r"[^0-9]", "", value)) for value in values),
            default=1,
        )

    @staticmethod
    def _scale(values: list[str]) -> int:
        return max(
            (
                len(re.split(r"[.,]", value, maxsplit=1)[1])
                if re.search(r"[.,]", value)
                else 0
                for value in values
            ),
            default=0,
        )


__all__ = ["InferredField", "SchemaFieldInferer"]
