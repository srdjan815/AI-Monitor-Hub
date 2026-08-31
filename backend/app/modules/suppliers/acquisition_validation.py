from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from urllib.parse import urlparse

from app.modules.suppliers.schema_profile_models import SupplierSchemaField

MINIMUM_TEXT_LENGTHS = {
    "code": 255,
    "productcode": 255,
    "sku": 255,
    "sifra": 255,
    "partnumber": 255,
    "manufacturercode": 255,
    "acname": 255,
    "artikal": 255,
    "name": 255,
    "naziv": 255,
    "productname": 255,
    "acdept": 25,
    "brand": 25,
    "manufacturer": 25,
    "proizvodjac": 25,
    "accategory": 45,
    "acmaincategory": 45,
    "category": 45,
    "grupa": 45,
    "itemgroup": 45,
    "nadgrupa": 45,
    "acsubcategory": 50,
    "podkategorija": 50,
    "subcategory": 50,
    "acinlinespecification": 150_000,
    "acproductdescription": 150_000,
    "description": 150_000,
    "opis": 150_000,
    "attributes": 150_000,
    "imageurl": 150_000,
    "imageurls": 150_000,
    "urlimages": 150_000,
}

IDENTIFIER_TEXT_CODES = {
    "ean",
    "ean8",
    "ean13",
    "upc",
    "upca",
    "upce",
    "gtin",
    "gtin13",
    "gtin14",
    "barcode",
    "barkod",
    "acean",
}

PRICE_CODES = {
    "cena",
    "mpcena",
    "price",
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


@dataclass(frozen=True, slots=True)
class RowProblem:
    code: str
    message: str
    schema_field_id: uuid.UUID | None = None
    mapping_rule_id: uuid.UUID | None = None
    severity: str = "ERROR"


@dataclass(frozen=True, slots=True)
class ValidatedRow:
    values: dict[uuid.UUID, object]
    source_key: str | None
    source_identifier: str | None
    problems: list[RowProblem]


class SchemaRecordValidator:
    def validate(
        self,
        record: dict[str, object],
        fields: list[SupplierSchemaField],
        *,
        validate_unknown_fields: bool = True,
        strict_field_ids: set[uuid.UUID] | None = None,
    ) -> ValidatedRow:
        values: dict[uuid.UUID, object] = {}
        problems: list[RowProblem] = []
        consumed: set[str] = set()
        key: str | None = None
        identifier: str | None = None
        for field in fields:
            found, value, source_name = self._resolve(record, field)
            if source_name:
                consumed.add(source_name)
            if strict_field_ids is not None and field.id not in strict_field_ids:
                values[field.id] = value if found else None
                text_value = None if value is None else str(value)
                if field.is_key:
                    key = text_value
                if field.is_identifier:
                    identifier = text_value
                continue
            if not found or value is None or value == "":
                if field.default_value is not None:
                    value = field.default_value
                elif field.required:
                    problems.append(
                        RowProblem(
                            "acquisition_required_field_missing",
                            f"Obavezno polje {field.field_code} nedostaje",
                            field.id,
                        )
                    )
                    continue
                elif not field.nullable and found:
                    problems.append(
                        RowProblem(
                            "acquisition_null_not_allowed",
                            f"Polje {field.field_code} ne dozvoljava null",
                            field.id,
                        )
                    )
                    continue
                else:
                    value = None
            value = self._normalized_value(value, field)
            problem = self._validate_value(value, field)
            if problem:
                problems.append(problem)
                continue
            values[field.id] = value
            text_value = None if value is None else str(value)
            if field.is_key:
                key = text_value
            if field.is_identifier:
                identifier = text_value
        unknown = sorted(set(record) - consumed)
        if validate_unknown_fields and unknown:
            problems.append(
                RowProblem(
                    "acquisition_unknown_fields",
                    "Ulaz sadrži polja koja nisu definisana Schema Profile-om",
                )
            )
        return ValidatedRow(values, key, identifier, problems)

    @classmethod
    def _normalized_value(
        cls,
        value: object,
        field: SupplierSchemaField,
    ) -> object:
        code = cls._semantic_code(field)
        if value is None:
            return value
        if code in IDENTIFIER_TEXT_CODES:
            return str(value).strip()
        scale = 2 if code in PRICE_CODES or field.is_price else field.scale
        if field.data_type != "DECIMAL" and code not in PRICE_CODES:
            return value
        if scale is None:
            return value
        try:
            decimal = Decimal(cls._decimal_text(str(value)))
            exponent = decimal.as_tuple().exponent
            current_scale = max(0, -exponent) if isinstance(exponent, int) else 0
            if current_scale <= scale:
                return format(decimal, "f") if code in PRICE_CODES else value
            quantum = Decimal(1).scaleb(-scale)
            return format(decimal.quantize(quantum, rounding=ROUND_HALF_UP), "f")
        except (InvalidOperation, TypeError, ValueError):
            return value

    @staticmethod
    def _resolve(
        record: dict[str, object],
        field: SupplierSchemaField,
    ) -> tuple[bool, object, str | None]:
        candidates = [field.field_code, field.name, field.path]
        tail = re.split(r"[./!\[\]]+", field.path.strip())[-1]
        if tail:
            candidates.append(tail)
        column = re.fullmatch(r"column\s+(\d+)", field.path, re.IGNORECASE)
        if column:
            index = int(column.group(1)) - 1
            if 0 <= index < len(record):
                key = list(record)[index]
                return True, record[key], key
        for candidate in candidates:
            if candidate in record:
                return True, record[candidate], candidate
        lowered: dict[str, str] = {key.lower(): key for key in record}
        for candidate in candidates:
            matched_key = lowered.get(candidate.lower())
            if matched_key is not None:
                return True, record[matched_key], matched_key
        return False, None, None

    def _validate_value(
        self,
        value: object,
        field: SupplierSchemaField,
    ) -> RowProblem | None:
        if value is None:
            return None
        text = str(value)
        normalized_code = self._semantic_code(field)
        configured_max = field.max_length
        policy_minimum = (
            64
            if normalized_code in IDENTIFIER_TEXT_CODES
            else MINIMUM_TEXT_LENGTHS.get(normalized_code)
        )
        effective_max = (
            max(configured_max or 0, policy_minimum)
            if policy_minimum is not None
            else configured_max
        )
        if effective_max is not None and len(text) > effective_max:
            return self._problem(
                "acquisition_max_length", "Vrednost je predugačka", field
            )
        try:
            self._type_check(value, text, field)
        except (InvalidOperation, TypeError, ValueError, json.JSONDecodeError):
            return self._problem(
                "acquisition_data_type_invalid",
                f"Vrednost polja {field.field_code} nije tipa {field.data_type}",
                field,
            )
        return None

    @classmethod
    def _type_check(
        cls,
        value: object,
        text: str,
        field: SupplierSchemaField,
    ) -> None:
        code = cls._semantic_code(field)
        if code in IDENTIFIER_TEXT_CODES:
            if re.fullmatch(r"\d+", text) is None:
                raise ValueError("identifier")
            return
        if code in PRICE_CODES or field.is_price:
            decimal = Decimal(cls._decimal_text(text))
            if not decimal.is_finite() or len(decimal.as_tuple().digits) > 38:
                raise ValueError("precision")
            return
        kind = field.data_type
        if kind == "INTEGER":
            int(text)
        elif kind == "DECIMAL":
            decimal = Decimal(SchemaRecordValidator._decimal_text(text))
            digits = len(decimal.as_tuple().digits)
            exponent = decimal.as_tuple().exponent
            scale = max(0, -exponent) if isinstance(exponent, int) else 0
            if field.precision is not None and digits > field.precision:
                raise ValueError("precision")
            if field.scale is not None and scale > field.scale:
                raise ValueError("scale")
        elif kind == "BOOLEAN" and text.lower() not in {
            "true",
            "false",
            "1",
            "0",
            "yes",
            "no",
        }:
            raise ValueError("boolean")
        elif kind == "DATE":
            date.fromisoformat(text)
        elif kind == "DATETIME":
            datetime.fromisoformat(text)
        elif kind == "TIME":
            time.fromisoformat(text)
        elif kind == "UUID":
            uuid.UUID(text)
        elif kind == "EMAIL" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text):
            raise ValueError("email")
        elif kind == "URL" and not urlparse(text).scheme:
            raise ValueError("url")
        elif kind == "PHONE" and not re.fullmatch(r"[+0-9() .-]{5,64}", text):
            raise ValueError("phone")
        elif kind == "JSON" and isinstance(value, str):
            json.loads(value)
        elif kind == "BINARY" and not isinstance(value, (bytes, str)):
            raise ValueError("binary")

    @staticmethod
    def _semantic_code(field: SupplierSchemaField) -> str:
        return re.sub(r"[^a-z0-9]+", "", field.field_code.casefold())

    @staticmethod
    def _decimal_text(value: str) -> str:
        compact = value.strip().replace(" ", "")
        comma = compact.rfind(",")
        dot = compact.rfind(".")
        if comma >= 0 and dot >= 0:
            decimal_separator = "," if comma > dot else "."
            thousands_separator = "." if decimal_separator == "," else ","
            return compact.replace(thousands_separator, "").replace(
                decimal_separator, "."
            )
        if comma >= 0:
            return compact.replace(".", "").replace(",", ".")
        return compact.replace(",", "")

    @staticmethod
    def _problem(
        code: str,
        message: str,
        field: SupplierSchemaField,
    ) -> RowProblem:
        return RowProblem(code, message, field.id)


__all__ = ["RowProblem", "SchemaRecordValidator", "ValidatedRow"]
