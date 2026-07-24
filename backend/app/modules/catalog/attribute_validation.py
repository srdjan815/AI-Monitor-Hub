from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import regex as timeout_regex

from app.modules.catalog.enums import (
    AttributeDataType,
    NormalizationRuleType,
    ValidationStatus,
)
from app.modules.catalog.models import AttributeDefinition
from app.modules.catalog.attribute_models import (
    AttributeNormalizationRule,
    AttributeOption,
)
from app.modules.catalog.schemas.product_attributes import ValidationResult

REGEX_TIMEOUT_SECONDS = 0.05


@dataclass(slots=True)
class _ConvertedValue:
    canonical: Any
    unit: str | None
    text: str | None = None
    numeric: Decimal | None = None
    boolean: bool | None = None
    date: date | None = None
    datetime: datetime | None = None
    json: Any | None = None
    applied: str | None = None


class AttributeValueValidator:
    """Deterministic, HTTP-independent normalization and validation."""

    def normalize(
        self,
        definition: AttributeDefinition,
        raw_value: Any,
        *,
        unit: str | None = None,
        options: list[AttributeOption] | None = None,
        rules: list[AttributeNormalizationRule] | None = None,
    ) -> ValidationResult:
        value, applied, messages = self._preprocess(raw_value, rules or [])
        normalized_unit = unit or definition.default_unit or definition.unit
        converted = _ConvertedValue(value, normalized_unit)
        try:
            converted = self._convert(
                self._data_type(definition),
                value,
                normalized_unit,
                self._option_map(options or []),
            )
        except (ValueError, TypeError, InvalidOperation, json.JSONDecodeError) as exc:
            messages.append(str(exc))
        if converted.applied:
            applied.append(converted.applied)
        messages.extend(self._constraint_messages(definition, converted))
        display = self._display(converted.canonical, converted.unit)
        return ValidationResult(
            raw_value=raw_value,
            canonical_value=converted.canonical if not messages else None,
            display_value=display if not messages else None,
            normalized_unit=converted.unit,
            validation_status=(
                ValidationStatus.INVALID if messages else ValidationStatus.VALID
            ),
            validation_messages=messages,
            rules_applied=applied,
            text_value=converted.text,
            numeric_value=converted.numeric,
            boolean_value=converted.boolean,
            date_value=converted.date,
            datetime_value=converted.datetime,
            json_value=converted.json,
        )

    def _preprocess(
        self,
        raw_value: Any,
        rules: list[AttributeNormalizationRule],
    ) -> tuple[Any, list[str], list[str]]:
        value = raw_value
        applied: list[str] = []
        messages: list[str] = []
        if isinstance(value, str):
            cleaned = " ".join(value.strip().split())
            if cleaned != value:
                applied.append("WHITESPACE")
            value = cleaned
        for rule in sorted(rules, key=lambda item: (item.priority, str(item.id))):
            if not rule.is_active:
                continue
            try:
                value, used = self._apply_rule(value, rule)
            except (re.error, timeout_regex.error, TimeoutError) as exc:
                messages.append(f"Invalid normalization regex: {exc}")
                continue
            if used:
                applied.append(f"{rule.rule_type}:{rule.id}")
        return value, applied, messages

    def _option_map(self, options: list[AttributeOption]) -> dict[str, AttributeOption]:
        result: dict[str, AttributeOption] = {}
        for option in options:
            if option.is_active:
                result[self._key(option.canonical_value)] = option
                result[self._key(option.display_value)] = option
                for alias in option.aliases:
                    result[self._key(alias.alias)] = option
        return result

    @staticmethod
    def _data_type(definition: AttributeDefinition) -> AttributeDataType:
        try:
            return AttributeDataType(definition.data_type)
        except ValueError:
            return AttributeDataType.TEXT

    def _convert(
        self,
        data_type: AttributeDataType,
        value: Any,
        unit: str | None,
        options: dict[str, AttributeOption],
    ) -> _ConvertedValue:
        numeric_types = {
            AttributeDataType.DECIMAL,
            AttributeDataType.DIMENSION,
            AttributeDataType.WEIGHT,
            AttributeDataType.POWER,
            AttributeDataType.CAPACITY,
            AttributeDataType.FREQUENCY,
        }
        if data_type == AttributeDataType.INTEGER:
            return self._convert_integer(value, unit)
        if data_type in numeric_types:
            return self._convert_numeric(data_type, value, unit)
        if data_type in {AttributeDataType.ENUM, AttributeDataType.SELECT}:
            return self._convert_option(value, unit, options)
        if data_type in {
            AttributeDataType.MULTI_ENUM,
            AttributeDataType.MULTISELECT,
        }:
            return self._convert_multi_option(value, unit, options)
        return self._convert_simple(data_type, value, unit)

    @staticmethod
    def _convert_integer(value: Any, unit: str | None) -> _ConvertedValue:
        numeric = Decimal(str(value))
        if numeric != numeric.to_integral_value():
            raise ValueError("Expected an integer")
        return _ConvertedValue(int(numeric), unit, numeric=numeric)

    def _convert_numeric(
        self, data_type: AttributeDataType, value: Any, unit: str | None
    ) -> _ConvertedValue:
        numeric, normalized_unit = self._numeric_with_unit(value, unit)
        number = format(numeric.normalize(), "f")
        canonical = (
            number
            if data_type == AttributeDataType.DECIMAL
            else f"{number}{normalized_unit or ''}"
        )
        return _ConvertedValue(canonical, normalized_unit, numeric=numeric)

    def _convert_option(
        self,
        value: Any,
        unit: str | None,
        options: dict[str, AttributeOption],
    ) -> _ConvertedValue:
        option = options.get(self._key(value))
        if option is None:
            raise ValueError("Value is not a configured option")
        return _ConvertedValue(
            option.canonical_value,
            unit,
            text=option.canonical_value,
            applied="ENUM_ALIAS",
        )

    def _convert_multi_option(
        self,
        value: Any,
        unit: str | None,
        options: dict[str, AttributeOption],
    ) -> _ConvertedValue:
        values = value if isinstance(value, list) else [value]
        canonical: list[str] = []
        for item in values:
            option = options.get(self._key(item))
            if option is None:
                raise ValueError(f"{item!r} is not a configured option")
            if option.canonical_value not in canonical:
                canonical.append(option.canonical_value)
        return _ConvertedValue(canonical, unit, json=canonical, applied="ENUM_ALIAS")

    def _convert_simple(
        self,
        data_type: AttributeDataType,
        value: Any,
        unit: str | None,
    ) -> _ConvertedValue:
        if data_type == AttributeDataType.BOOLEAN:
            boolean = self._boolean(value)
            return _ConvertedValue(boolean, unit, boolean=boolean)
        if data_type == AttributeDataType.DATE:
            converted = date.fromisoformat(str(value))
            return _ConvertedValue(converted.isoformat(), unit, date=converted)
        if data_type == AttributeDataType.DATETIME:
            converted_datetime = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
            return _ConvertedValue(
                converted_datetime.isoformat(),
                unit,
                datetime=converted_datetime,
            )
        if data_type == AttributeDataType.URL:
            parsed = urlparse(str(value))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Expected an absolute HTTP(S) URL")
            return _ConvertedValue(str(value), unit, text=str(value))
        if data_type == AttributeDataType.JSON:
            converted_json = json.loads(value) if isinstance(value, str) else value
            return _ConvertedValue(converted_json, unit, json=converted_json)
        return _ConvertedValue(str(value), unit, text=str(value))

    def _constraint_messages(
        self,
        definition: AttributeDefinition,
        converted: _ConvertedValue,
    ) -> list[str]:
        messages: list[str] = []
        canonical = converted.canonical
        if canonical in definition.forbidden_values:
            messages.append("Value is forbidden")
        if definition.is_required and canonical in (None, "", []):
            messages.append("Value is required")
        if isinstance(canonical, str):
            messages.extend(self._string_constraints(definition, canonical))
        if converted.numeric is not None:
            messages.extend(self._numeric_constraints(definition, converted.numeric))
        if (
            definition.accepted_units
            and converted.unit not in definition.accepted_units
        ):
            messages.append("Unit is not accepted")
        return messages

    @staticmethod
    def _string_constraints(
        definition: AttributeDefinition, canonical: str
    ) -> list[str]:
        messages: list[str] = []
        if (
            definition.minimum_length is not None
            and len(canonical) < definition.minimum_length
        ):
            messages.append("Value is shorter than minimum_length")
        if (
            definition.maximum_length is not None
            and len(canonical) > definition.maximum_length
        ):
            messages.append("Value is longer than maximum_length")
        if definition.regex_pattern:
            try:
                if (
                    timeout_regex.fullmatch(
                        definition.regex_pattern,
                        canonical,
                        timeout=REGEX_TIMEOUT_SECONDS,
                    )
                    is None
                ):
                    messages.append(
                        definition.validation_message
                        or "Value does not match regex_pattern"
                    )
            except TimeoutError:
                messages.append("Validation regex exceeded the execution limit")
            except timeout_regex.error as exc:
                messages.append(f"Invalid validation regex: {exc}")
        return messages

    @staticmethod
    def _numeric_constraints(
        definition: AttributeDefinition, numeric: Decimal
    ) -> list[str]:
        messages: list[str] = []
        if definition.minimum_value is not None and numeric < Decimal(
            str(definition.minimum_value)
        ):
            messages.append("Value is below minimum_value")
        if definition.maximum_value is not None and numeric > Decimal(
            str(definition.maximum_value)
        ):
            messages.append("Value exceeds maximum_value")
        return messages

    def _apply_rule(
        self, value: Any, rule: AttributeNormalizationRule
    ) -> tuple[Any, bool]:
        if not isinstance(value, str):
            return value, False
        replacement = rule.replacement or ""
        if rule.rule_type == NormalizationRuleType.WHITESPACE:
            result = re.sub(r"\s+", replacement or "", value).strip()
            return result, result != value
        if rule.rule_type == NormalizationRuleType.EXACT:
            if value == rule.pattern:
                return replacement, True
        elif rule.rule_type == NormalizationRuleType.CASE_INSENSITIVE_EXACT:
            if value.casefold() == rule.pattern.casefold():
                return replacement, True
        elif rule.rule_type in {
            NormalizationRuleType.REGEX,
            NormalizationRuleType.UNIT,
            NormalizationRuleType.CUSTOM_TEMPLATE,
        }:
            flags = 0 if rule.case_sensitive else timeout_regex.IGNORECASE
            result = timeout_regex.sub(
                rule.pattern,
                replacement,
                value,
                flags=flags,
                timeout=REGEX_TIMEOUT_SECONDS,
            )
            return result, result != value
        return value, False

    @staticmethod
    def _numeric_with_unit(value: Any, unit: str | None) -> tuple[Decimal, str | None]:
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value)), unit
        match = re.fullmatch(
            r"\s*([+-]?\d+(?:[.,]\d+)?)\s*([A-Za-zµ]+)?\s*", str(value)
        )
        if match is None:
            raise ValueError("Expected a numeric value with an optional unit")
        number = Decimal(match.group(1).replace(",", "."))
        parsed_unit = match.group(2)
        unit_key = (parsed_unit or unit or "").casefold()
        canonical_units = {
            "tb": "TB",
            "gb": "GB",
            "mb": "MB",
            "ghz": "GHz",
            "mhz": "MHz",
            "hz": "Hz",
            "w": "W",
            "kw": "kW",
            "kg": "kg",
            "g": "g",
            "mm": "mm",
            "cm": "cm",
        }
        normalized = canonical_units.get(unit_key, parsed_unit or unit)
        return number, normalized

    @staticmethod
    def _boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        lowered = str(value).strip().casefold()
        if lowered in {"true", "1", "yes", "da"}:
            return True
        if lowered in {"false", "0", "no", "ne"}:
            return False
        raise ValueError("Expected a boolean value")

    @staticmethod
    def _key(value: Any) -> str:
        return " ".join(str(value).split()).casefold()

    @staticmethod
    def _display(value: Any, unit: str | None) -> str:
        if isinstance(value, list):
            rendered = ", ".join(str(item) for item in value)
        elif isinstance(value, bool):
            rendered = "Da" if value else "Ne"
        else:
            rendered = str(value)
        if unit and not rendered.endswith(unit):
            return f"{rendered}{unit}"
        return rendered
