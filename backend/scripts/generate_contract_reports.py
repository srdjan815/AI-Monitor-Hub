from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
AUDIT_ROOT = BACKEND_ROOT.parent / "docs" / "audits"
HTTP_METHODS = {
    "delete",
    "get",
    "head",
    "options",
    "patch",
    "post",
    "put",
    "trace",
}
BOUNDARY_KEYS = {
    "exclusiveMaximum",
    "exclusiveMinimum",
    "maxItems",
    "maxLength",
    "maxProperties",
    "maximum",
    "minItems",
    "minLength",
    "minProperties",
    "minimum",
    "multipleOf",
    "pattern",
    "x-max-json-array-items",
    "x-max-json-bytes",
    "x-max-json-depth",
    "x-max-json-key-chars",
    "x-max-json-keys",
    "x-max-json-nodes",
}
SCHEMA_BRANCH_KEYS = ("allOf", "anyOf", "oneOf")
INTRINSICALLY_BOUNDED_STRING_FORMATS = {
    "date",
    "date-time",
    "time",
    "uuid",
}
JSON_STRUCTURAL_BOUNDARY_KEYS = {
    "x-max-json-array-items",
    "x-max-json-bytes",
    "x-max-json-depth",
    "x-max-json-key-chars",
    "x-max-json-keys",
    "x-max-json-nodes",
}
Usage = tuple[str, str, str]


def _schema_name(reference: str | None) -> str | None:
    if not reference:
        return None
    return reference.rsplit("/", 1)[-1]


def _request_schema(operation: dict[str, Any]) -> str | None:
    content = operation.get("requestBody", {}).get("content", {})
    media: dict[str, Any] = content.get("application/json") or next(
        iter(content.values()),
        {},
    )
    schema = media.get("schema", {})
    return _schema_name(schema.get("$ref"))


def _resolve_openapi_object(
    specification: dict[str, Any],
    value: dict[str, Any],
) -> dict[str, Any]:
    reference = value.get("$ref")
    if not reference or not reference.startswith("#/components/"):
        return value
    current: Any = specification
    for part in reference.removeprefix("#/").split("/"):
        if not isinstance(current, dict):
            return value
        current = current.get(part)
    return current if isinstance(current, dict) else value


def _media_schemas(content: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for media_type, media in sorted(content.items()):
        schema = media.get("schema")
        if isinstance(schema, dict):
            yield media_type, schema


def _record_schema_usage(
    schema: dict[str, Any],
    schemas: dict[str, Any],
    destination: dict[str, set[Usage]],
    usage: Usage,
    visited: set[str] | None = None,
) -> None:
    visited = set() if visited is None else visited
    reference_name = _schema_name(schema.get("$ref"))
    if reference_name and reference_name in schemas:
        destination[reference_name].add(usage)
        if reference_name not in visited:
            visited.add(reference_name)
            _record_schema_usage(
                schemas[reference_name],
                schemas,
                destination,
                usage,
                visited,
            )

    for key in SCHEMA_BRANCH_KEYS:
        for branch in schema.get(key, []):
            if isinstance(branch, dict):
                _record_schema_usage(
                    branch,
                    schemas,
                    destination,
                    usage,
                    visited,
                )
    for field in schema.get("properties", {}).values():
        if isinstance(field, dict):
            _record_schema_usage(
                field,
                schemas,
                destination,
                usage,
                visited,
            )
    for key in ("items", "additionalProperties"):
        child = schema.get(key)
        if isinstance(child, dict):
            _record_schema_usage(
                child,
                schemas,
                destination,
                usage,
                visited,
            )


def _effective_parameters(
    specification: dict[str, Any],
    path_item: dict[str, Any],
    operation: dict[str, Any],
) -> list[dict[str, Any]]:
    parameters: dict[tuple[Any, Any], dict[str, Any]] = {}
    for raw_parameter in (
        *path_item.get("parameters", []),
        *operation.get("parameters", []),
    ):
        parameter = _resolve_openapi_object(specification, raw_parameter)
        parameters[(parameter.get("name"), parameter.get("in"))] = parameter
    return [
        parameter
        for _, parameter in sorted(
            parameters.items(),
            key=lambda item: (str(item[0][1]), str(item[0][0])),
        )
    ]


def _component_usage(
    specification: dict[str, Any],
) -> tuple[dict[str, set[Usage]], dict[str, set[Usage]]]:
    schemas = specification.get("components", {}).get("schemas", {})
    request_usage: dict[str, set[Usage]] = defaultdict(set)
    response_usage: dict[str, set[Usage]] = defaultdict(set)

    for path, path_item in sorted(specification.get("paths", {}).items()):
        for method, operation in sorted(path_item.items()):
            if method not in HTTP_METHODS:
                continue
            method_name = method.upper()
            for parameter in _effective_parameters(
                specification,
                path_item,
                operation,
            ):
                schema = parameter.get("schema")
                if not isinstance(schema, dict):
                    continue
                source = f"parameter:{parameter.get('in')}:{parameter.get('name')}"
                _record_schema_usage(
                    schema,
                    schemas,
                    request_usage,
                    (path, method_name, source),
                )

            request_body = operation.get("requestBody", {})
            if isinstance(request_body, dict):
                request_body = _resolve_openapi_object(
                    specification,
                    request_body,
                )
                for media_type, schema in _media_schemas(
                    request_body.get("content", {}),
                ):
                    _record_schema_usage(
                        schema,
                        schemas,
                        request_usage,
                        (path, method_name, f"requestBody:{media_type}"),
                    )

            for status, raw_response in sorted(
                operation.get("responses", {}).items(),
            ):
                response = _resolve_openapi_object(
                    specification,
                    raw_response,
                )
                for media_type, schema in _media_schemas(
                    response.get("content", {}),
                ):
                    _record_schema_usage(
                        schema,
                        schemas,
                        response_usage,
                        (path, method_name, f"response:{status}:{media_type}"),
                    )

    return request_usage, response_usage


def _schema_properties(
    schema: dict[str, Any],
    schemas: dict[str, Any],
    visited: set[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    visited = set() if visited is None else visited
    properties: dict[str, dict[str, Any]] = {}
    required: set[str] = set()

    reference_name = _schema_name(schema.get("$ref"))
    if reference_name and reference_name in schemas and reference_name not in visited:
        visited.add(reference_name)
        inherited, inherited_required = _schema_properties(
            schemas[reference_name],
            schemas,
            visited,
        )
        properties.update(inherited)
        required.update(inherited_required)

    for branch in schema.get("allOf", []):
        if not isinstance(branch, dict):
            continue
        inherited, inherited_required = _schema_properties(
            branch,
            schemas,
            visited.copy(),
        )
        properties.update(inherited)
        required.update(inherited_required)

    for field_name, field in schema.get("properties", {}).items():
        if isinstance(field, dict):
            properties[field_name] = field
    required.update(schema.get("required", []))
    return properties, required


def _merge_effective_schema(
    destination: dict[str, Any],
    source: dict[str, Any],
) -> None:
    for key in (
        "additionalProperties",
        "enum",
        "format",
        "items",
        "properties",
        "type",
        *sorted(BOUNDARY_KEYS),
    ):
        if key in source:
            destination[key] = source[key]


def _effective_schema(
    schema: dict[str, Any],
    schemas: dict[str, Any],
    visited: set[str] | None = None,
) -> dict[str, Any]:
    visited = set() if visited is None else visited
    effective: dict[str, Any] = {}
    reference_name = _schema_name(schema.get("$ref"))
    if reference_name and reference_name in schemas and reference_name not in visited:
        visited.add(reference_name)
        _merge_effective_schema(
            effective,
            _effective_schema(schemas[reference_name], schemas, visited),
        )

    for branch in schema.get("allOf", []):
        if isinstance(branch, dict):
            _merge_effective_schema(
                effective,
                _effective_schema(branch, schemas, visited.copy()),
            )

    for union_key in ("anyOf", "oneOf"):
        concrete = [
            branch
            for branch in schema.get(union_key, [])
            if isinstance(branch, dict) and branch.get("type") != "null"
        ]
        if len(concrete) == 1:
            _merge_effective_schema(
                effective,
                _effective_schema(concrete[0], schemas, visited.copy()),
            )

    _merge_effective_schema(effective, schema)
    return effective


def _first_reference(schema: dict[str, Any]) -> str | None:
    reference_name = _schema_name(schema.get("$ref"))
    if reference_name:
        return reference_name
    for key in SCHEMA_BRANCH_KEYS:
        for branch in schema.get(key, []):
            if isinstance(branch, dict):
                reference_name = _first_reference(branch)
                if reference_name:
                    return reference_name
    return None


def _is_nullable(schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    if schema_type == "null":
        return True
    if isinstance(schema_type, list) and "null" in schema_type:
        return True
    return any(
        isinstance(branch, dict) and _is_nullable(branch)
        for key in ("anyOf", "oneOf")
        for branch in schema.get(key, [])
    )


def _numeric_union_schema(
    schema: dict[str, Any],
    schemas: dict[str, Any],
) -> dict[str, Any] | None:
    """Recognize Pydantic Decimal's bounded number/string JSON representation."""
    for union_key in ("anyOf", "oneOf"):
        branches = [
            _effective_schema(branch, schemas)
            for branch in schema.get(union_key, [])
            if isinstance(branch, dict) and branch.get("type") != "null"
        ]
        if len(branches) < 2:
            continue
        branch_types = {branch.get("type") for branch in branches}
        string_branches = [
            branch for branch in branches if branch.get("type") == "string"
        ]
        if (
            branch_types == {"number", "string"}
            and string_branches
            and all(branch.get("pattern") for branch in string_branches)
        ):
            number_branch = next(
                branch for branch in branches if branch.get("type") == "number"
            )
            return {
                **number_branch,
                "pattern": string_branches[0]["pattern"],
            }
    return None


def _has_finite_literal_pattern(pattern: Any) -> bool:
    """Recognize anchored alternations made only from literal identifier tokens."""
    if not isinstance(pattern, str):
        return False
    if not pattern.startswith("^(") or not pattern.endswith(")$"):
        return False
    choices = pattern[2:-2].split("|")
    return bool(choices) and all(
        choice
        and all(
            character.isascii() and (character.isalnum() or character in "_-")
            for character in choice
        )
        for choice in choices
    )


def _field_shape(
    field: dict[str, Any],
    schemas: dict[str, Any],
) -> dict[str, Any]:
    effective = _effective_schema(field, schemas)
    reference_name = _first_reference(field)
    primitive_type = effective.get("type")
    numeric_union = _numeric_union_schema(field, schemas)
    if primitive_type is None and numeric_union is not None:
        _merge_effective_schema(effective, numeric_union)
        primitive_type = "number"
    if isinstance(primitive_type, list):
        non_null_types = sorted(value for value in primitive_type if value != "null")
        primitive_type = "|".join(non_null_types) or "null"
    if primitive_type is None:
        primitive_type = "any"

    items = effective.get("items")
    item_effective = (
        _effective_schema(items, schemas) if isinstance(items, dict) else {}
    )
    item_reference = _first_reference(items) if isinstance(items, dict) else None
    item_type = item_reference or item_effective.get("type")
    if isinstance(items, dict) and item_type is None:
        item_type = "any"

    return {
        "type": reference_name or primitive_type,
        "primitive_type": primitive_type,
        "nullable": _is_nullable(field),
        "item_type": item_type,
        "boundaries": {
            key: effective[key] for key in sorted(BOUNDARY_KEYS) if key in effective
        },
        "item_boundaries": {
            key: item_effective[key]
            for key in sorted(BOUNDARY_KEYS)
            if key in item_effective
        },
        "format": effective.get("format"),
        "enum": effective.get("enum"),
        "has_properties": bool(effective.get("properties")),
        "additional_properties": effective.get("additionalProperties"),
    }


def _string_risk_reasons(shape: dict[str, Any]) -> list[str]:
    boundaries = shape["boundaries"]
    bounded = (
        "maxLength" in boundaries
        or bool(shape["enum"])
        or shape["format"] in INTRINSICALLY_BOUNDED_STRING_FORMATS
        or _has_finite_literal_pattern(boundaries.get("pattern"))
    )
    return [] if bounded else ["unbounded_string"]


def _array_risk_reasons(shape: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    boundaries = shape["boundaries"]
    structurally_bounded = JSON_STRUCTURAL_BOUNDARY_KEYS <= boundaries.keys()
    if "maxItems" not in boundaries and not structurally_bounded:
        reasons.append("unbounded_array")
    if shape["item_type"] == "any" and not structurally_bounded:
        reasons.append("unconstrained_array_items")
    elif shape["item_type"] == "string" and "maxLength" not in shape["item_boundaries"]:
        reasons.append("unbounded_array_item_string")
    return reasons


def _object_risk_reasons(shape: dict[str, Any]) -> list[str]:
    boundaries = shape["boundaries"]
    structurally_bounded = JSON_STRUCTURAL_BOUNDARY_KEYS <= boundaries.keys()
    free_form = (
        not shape["has_properties"]
        or shape["additional_properties"] is True
        or isinstance(shape["additional_properties"], dict)
    )
    if free_form and "maxProperties" not in boundaries and not structurally_bounded:
        return ["unbounded_object"]
    return []


def _any_risk_reasons(shape: dict[str, Any]) -> list[str]:
    structurally_bounded = JSON_STRUCTURAL_BOUNDARY_KEYS <= shape["boundaries"].keys()
    return [] if structurally_bounded else ["unconstrained_any"]


def _numeric_risk_reasons(shape: dict[str, Any]) -> list[str]:
    bounded = any(
        key in shape["boundaries"] for key in ("exclusiveMaximum", "maximum", "pattern")
    )
    return [] if bounded else ["unbounded_numeric"]


def _input_risk_reasons(shape: dict[str, Any]) -> list[str]:
    validators = {
        "string": _string_risk_reasons,
        "array": _array_risk_reasons,
        "object": _object_risk_reasons,
        "any": _any_risk_reasons,
        "integer": _numeric_risk_reasons,
        "number": _numeric_risk_reasons,
    }
    validator = validators.get(shape["primitive_type"])
    return validator(shape) if validator is not None else []


def _risk_metadata(
    shape: dict[str, Any],
    *,
    request_reachable: bool,
) -> dict[str, Any]:
    if not request_reachable:
        return {
            "tier": "none",
            "reasons": [],
            "review_required": False,
        }

    reasons = _input_risk_reasons(shape)
    high_risk = {
        "unbounded_array",
        "unbounded_object",
        "unconstrained_any",
        "unconstrained_array_items",
    }
    tier = "high" if high_risk.intersection(reasons) else "medium"
    if not reasons:
        tier = "none"
    return {
        "tier": tier,
        "reasons": reasons,
        "review_required": bool(reasons),
    }


def _usage_rows(usages: set[Usage]) -> list[dict[str, str]]:
    return [
        {"path": path, "method": method, "source": source}
        for path, method, source in sorted(usages)
    ]


def _build_field_row(
    *,
    schema_name: str | None,
    field_name: str,
    field_path: str,
    field: dict[str, Any],
    required: bool,
    request_usages: set[Usage],
    response_usages: set[Usage],
    location: str,
    schemas: dict[str, Any],
) -> dict[str, Any]:
    shape = _field_shape(field, schemas)
    request_reachable = bool(request_usages)
    response_reachable = bool(response_usages)
    if request_reachable and response_reachable:
        usage = "both"
    elif request_reachable:
        usage = "request"
    else:
        usage = "response"
    risk = _risk_metadata(
        shape,
        request_reachable=request_reachable,
    )
    return {
        "schema": schema_name,
        "field": field_name,
        "field_path": field_path,
        "location": location,
        "type": shape["type"],
        "primitive_type": shape["primitive_type"],
        "required": required,
        "nullable": shape["nullable"],
        "item_type": shape["item_type"],
        "boundaries": shape["boundaries"],
        "item_boundaries": shape["item_boundaries"],
        "format": shape["format"],
        "enum": shape["enum"],
        "description": field.get("description"),
        "usage": usage,
        "request_reachable": request_reachable,
        "response_reachable": response_reachable,
        "route_method_usage": _usage_rows(request_usages | response_usages),
        "risk": risk,
        "risk_tier": risk["tier"],
        "risk_reasons": risk["reasons"],
        "boundary_review_required": risk["review_required"],
    }


def _component_field_inventory(
    specification: dict[str, Any],
    request_usage: dict[str, set[Usage]],
    response_usage: dict[str, set[Usage]],
) -> list[dict[str, Any]]:
    schemas = specification.get("components", {}).get("schemas", {})
    rows: list[dict[str, Any]] = []
    reachable_names = sorted(set(request_usage) | set(response_usage))
    for schema_name in reachable_names:
        properties, required = _schema_properties(
            schemas[schema_name],
            schemas,
        )
        for field_name, field in sorted(properties.items()):
            rows.append(
                _build_field_row(
                    schema_name=schema_name,
                    field_name=field_name,
                    field_path=f"{schema_name}.{field_name}",
                    field=field,
                    required=field_name in required,
                    request_usages=request_usage.get(schema_name, set()),
                    response_usages=response_usage.get(schema_name, set()),
                    location="component",
                    schemas=schemas,
                )
            )
    return rows


def _query_parameter_inventory(
    specification: dict[str, Any],
) -> list[dict[str, Any]]:
    schemas = specification.get("components", {}).get("schemas", {})
    rows: list[dict[str, Any]] = []
    for path, path_item in sorted(specification.get("paths", {}).items()):
        for method, operation in sorted(path_item.items()):
            if method not in HTTP_METHODS:
                continue
            for parameter in _effective_parameters(
                specification,
                path_item,
                operation,
            ):
                if parameter.get("in") != "query":
                    continue
                field = parameter.get("schema", {})
                if not isinstance(field, dict):
                    field = {}
                name = str(parameter.get("name"))
                usage = {(path, method.upper(), f"parameter:query:{name}")}
                rows.append(
                    _build_field_row(
                        schema_name=None,
                        field_name=name,
                        field_path=f"{method.upper()} {path} query.{name}",
                        field=field,
                        required=bool(parameter.get("required")),
                        request_usages=usage,
                        response_usages=set(),
                        location="query",
                        schemas=schemas,
                    )
                )
    return rows


def _inline_properties(
    schema: dict[str, Any],
    schemas: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    if _first_reference(schema):
        return {}, set()
    return _schema_properties(schema, schemas)


def _inline_body_inventory(
    specification: dict[str, Any],
) -> list[dict[str, Any]]:
    schemas = specification.get("components", {}).get("schemas", {})
    rows: list[dict[str, Any]] = []
    for path, path_item in sorted(specification.get("paths", {}).items()):
        for method, operation in sorted(path_item.items()):
            if method not in HTTP_METHODS:
                continue
            raw_body = operation.get("requestBody")
            if not isinstance(raw_body, dict):
                continue
            request_body = _resolve_openapi_object(specification, raw_body)
            for media_type, schema in _media_schemas(
                request_body.get("content", {}),
            ):
                properties, required = _inline_properties(schema, schemas)
                usage = {
                    (path, method.upper(), f"requestBody:{media_type}"),
                }
                operation_name = operation.get("operationId") or (
                    f"{method.upper()} {path}"
                )
                for field_name, field in sorted(properties.items()):
                    rows.append(
                        _build_field_row(
                            schema_name=None,
                            field_name=field_name,
                            field_path=f"{operation_name}.body.{field_name}",
                            field=field,
                            required=field_name in required,
                            request_usages=usage,
                            response_usages=set(),
                            location="requestBody",
                            schemas=schemas,
                        )
                    )
    return rows


def _operation_inventory(specification: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    expected_errors = ("400", "401", "403", "404", "409", "413", "422", "429", "500")
    for path, path_item in specification["paths"].items():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            responses = operation.get("responses", {})
            success_codes = sorted(
                code for code in responses if str(code).startswith("2")
            )
            rows.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "operation_id": operation.get("operationId"),
                    "tags": operation.get("tags", []),
                    "deprecated": operation.get("deprecated", False),
                    "security": operation.get("security", []),
                    "request_schema": _request_schema(operation),
                    "parameters": [
                        {
                            "name": parameter.get("name"),
                            "in": parameter.get("in"),
                            "required": parameter.get("required", False),
                            "schema": parameter.get("schema", {}),
                        }
                        for parameter in operation.get("parameters", [])
                    ],
                    "success_codes": success_codes,
                    "success_schema_documented": all(
                        bool(
                            responses[code]
                            .get("content", {})
                            .get("application/json", {})
                            .get("schema")
                        )
                        or code == "204"
                        for code in success_codes
                    ),
                    "documented_errors": {
                        code: code in responses for code in expected_errors
                    },
                }
            )
    return sorted(rows, key=lambda row: (row["path"], row["method"]))


def _field_inventory(
    specification: dict[str, Any],
) -> list[dict[str, Any]]:
    request_usage, response_usage = _component_usage(specification)
    rows = _component_field_inventory(
        specification,
        request_usage,
        response_usage,
    )
    rows.extend(_inline_body_inventory(specification))
    rows.extend(_query_parameter_inventory(specification))
    return sorted(
        rows,
        key=lambda row: (
            row["location"],
            str(row["schema"]),
            row["field_path"],
        ),
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _application_openapi() -> dict[str, Any]:
    from app.main import app

    return app.openapi()


def main() -> None:
    specification = _application_openapi()
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    operations = _operation_inventory(specification)
    fields = _field_inventory(specification)
    _write_json(AUDIT_ROOT / "openapi-normalized.json", specification)
    _write_json(
        AUDIT_ROOT / "api-operation-matrix.json",
        {
            "operation_count": len(operations),
            "operations": operations,
        },
    )
    _write_json(
        AUDIT_ROOT / "request-boundary-inventory.json",
        {
            "field_count": len(fields),
            "request_field_count": sum(
                bool(field["request_reachable"]) for field in fields
            ),
            "response_only_field_count": sum(
                bool(field["response_reachable"] and not field["request_reachable"])
                for field in fields
            ),
            "query_parameter_count": sum(
                field["location"] == "query" for field in fields
            ),
            "fields_requiring_review": sum(
                bool(field["boundary_review_required"]) for field in fields
            ),
            "risk_tier_counts": {
                tier: sum(field["risk_tier"] == tier for field in fields)
                for tier in ("high", "medium", "none")
            },
            "fields": fields,
        },
    )


if __name__ == "__main__":
    main()
