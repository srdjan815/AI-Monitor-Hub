from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import regex

from app.modules.suppliers.acquisition_validation import RowProblem
from app.modules.suppliers.mapping_profile_models import SupplierMappingRule


@dataclass(frozen=True, slots=True)
class MappingResult:
    mapped: dict[str, object]
    problems: list[RowProblem]


class MappingExecutor:
    def execute(
        self,
        values: dict[uuid.UUID, object],
        rules: list[SupplierMappingRule],
    ) -> MappingResult:
        mapped: dict[str, object] = {}
        problems: list[RowProblem] = []
        for rule in sorted(rules, key=lambda item: item.priority):
            source = values.get(rule.schema_field_id)
            try:
                value = self._transform(rule, source, values)
                value = self._canonical_value(rule.target_attribute, value)
                self._validate_rule(rule, value)
                if rule.required and (value is None or value == ""):
                    raise ValueError("required mapping is empty")
                if value is not None:
                    mapped[rule.target_attribute] = value
            except (KeyError, TypeError, ValueError, regex.error, TimeoutError):
                problems.append(
                    RowProblem(
                        "acquisition_mapping_failed",
                        f"Mapiranje cilja {rule.target_attribute} nije uspelo",
                        mapping_rule_id=rule.id,
                        severity="ERROR" if rule.required else "WARNING",
                    )
                )
        return MappingResult(mapped, problems)

    def _transform(
        self,
        rule: SupplierMappingRule,
        source: object,
        all_values: dict[uuid.UUID, object],
    ) -> object:
        kind = rule.transformation_type
        config = rule.transformation_config or {}
        if kind in {"NONE", "COPY"}:
            return source
        if kind == "DEFAULT_VALUE":
            return rule.default_value if source in {None, ""} else source
        if kind == "CONSTANT":
            return rule.default_value
        text = "" if source is None else str(source)
        if kind == "TRIM":
            return text.strip()
        if kind == "UPPERCASE":
            return text.upper()
        if kind == "LOWERCASE":
            return text.lower()
        if kind == "SPLIT":
            delimiter = str(config["delimiter"])
            index = int(str(config.get("index", 0)))
            return text.split(delimiter)[index]
        if kind == "REPLACE":
            return text.replace(str(config["old"]), str(config.get("new", "")))
        if kind == "REGEX":
            return regex.sub(
                str(config["pattern"]),
                str(config.get("replacement", "")),
                text,
                timeout=0.05,
            )
        if kind == "CONCAT":
            field_ids = config.get("field_ids")
            if isinstance(field_ids, list):
                labels = config.get("labels", {})
                if not isinstance(labels, dict):
                    raise ValueError("labels")
                rendered_fields: list[str] = []
                normalized_fields: list[str] = []
                include_labels = bool(config.get("include_labels", True))
                deduplicate = bool(config.get("deduplicate", False))
                skip_contained = bool(config.get("skip_contained", False))
                for raw_id in field_ids:
                    field_id = uuid.UUID(str(raw_id))
                    raw_value = all_values.get(field_id)
                    normalized = str(raw_value).strip() if raw_value is not None else ""
                    if not normalized or normalized.casefold() in {
                        "0",
                        "false",
                        "ne",
                        "no",
                    }:
                        continue
                    comparable = normalized.casefold()
                    if deduplicate and comparable in normalized_fields:
                        continue
                    if skip_contained and any(
                        comparable in existing for existing in normalized_fields
                    ):
                        continue
                    label = str(labels.get(str(field_id), "")).strip()
                    if not include_labels:
                        rendered_fields.append(normalized)
                    elif comparable in {"1", "true", "da", "yes"}:
                        rendered_fields.append(label or normalized)
                    else:
                        rendered_fields.append(
                            f"{label}: {normalized}" if label else normalized
                        )
                    normalized_fields.append(comparable)
                return str(config.get("separator", " | ")).join(rendered_fields)
            values = config.get("values", ["$value"])
            if not isinstance(values, list):
                raise ValueError("values")
            rendered = [text if value == "$value" else str(value) for value in values]
            return str(config.get("separator", "")).join(rendered)
        raise ValueError("unsupported transformation")

    @staticmethod
    def _canonical_value(target: str, value: object) -> object:
        if value is None:
            return value
        if target in {"ean", "upc", "barcode", "gtin"}:
            return str(value).strip()
        if target in {
            "price",
            "promotion_price",
            "old_price",
            "discount_percentage",
        }:
            text = str(value).strip().replace(" ", "")
            if "," in text and "." in text:
                decimal_mark = "," if text.rfind(",") > text.rfind(".") else "."
                thousands = "." if decimal_mark == "," else ","
                text = text.replace(thousands, "").replace(decimal_mark, ".")
            else:
                text = text.replace(",", ".")
            try:
                return format(
                    Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "f",
                )
            except InvalidOperation as exc:
                raise ValueError("price") from exc
        return value

    @staticmethod
    def _validate_rule(rule: SupplierMappingRule, value: object) -> None:
        declaration = rule.validation_rule
        if not declaration:
            return
        text = "" if value is None else str(value)
        if declaration == "non_empty" and not text:
            raise ValueError("empty")
        if declaration.startswith("max_length:"):
            if len(text) > int(declaration.split(":", 1)[1]):
                raise ValueError("length")
            return
        if declaration.startswith("regex:"):
            if (
                regex.fullmatch(
                    declaration.split(":", 1)[1],
                    text,
                    timeout=0.05,
                )
                is None
            ):
                raise ValueError("regex")
            return
        if declaration != "non_empty":
            raise ValueError("unsupported validation rule")


__all__ = ["MappingExecutor", "MappingResult"]
