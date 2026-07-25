from __future__ import annotations

import uuid
from dataclasses import dataclass

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
                value = self._transform(rule, source)
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

    def _transform(self, rule: SupplierMappingRule, source: object) -> object:
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
            values = config.get("values", ["$value"])
            if not isinstance(values, list):
                raise ValueError("values")
            rendered = [text if value == "$value" else str(value) for value in values]
            return str(config.get("separator", "")).join(rendered)
        raise ValueError("unsupported transformation")

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
