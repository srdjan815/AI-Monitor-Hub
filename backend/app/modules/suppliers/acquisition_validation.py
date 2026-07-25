from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from app.modules.suppliers.schema_profile_models import SupplierSchemaField


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
        if unknown:
            problems.append(
                RowProblem(
                    "acquisition_unknown_fields",
                    "Ulaz sadrži polja koja nisu definisana Schema Profile-om",
                )
            )
        return ValidatedRow(values, key, identifier, problems)

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
        if field.max_length is not None and len(text) > field.max_length:
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

    @staticmethod
    def _type_check(
        value: object,
        text: str,
        field: SupplierSchemaField,
    ) -> None:
        kind = field.data_type
        if kind == "INTEGER":
            int(text)
        elif kind == "DECIMAL":
            decimal = Decimal(text)
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
    def _problem(
        code: str,
        message: str,
        field: SupplierSchemaField,
    ) -> RowProblem:
        return RowProblem(code, message, field.id)


__all__ = ["RowProblem", "SchemaRecordValidator", "ValidatedRow"]
