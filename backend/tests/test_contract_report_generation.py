from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import generate_contract_reports as reports


def _specification() -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "paths": {
            "/items": {
                "parameters": [
                    {"$ref": "#/components/parameters/SharedSearch"},
                ],
                "get": {
                    "operationId": "listItems",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/RequestModel",
                                    },
                                },
                            },
                        },
                    },
                },
                "post": {
                    "operationId": "createItem",
                    "parameters": [
                        {
                            "name": "cursor",
                            "in": "query",
                            "schema": {"type": "string"},
                        },
                    ],
                    "requestBody": {
                        "$ref": "#/components/requestBodies/ItemBody",
                    },
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ResponseModel",
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "/inline": {
                "patch": {
                    "operationId": "patchInline",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["payload"],
                                    "properties": {
                                        "payload": {},
                                    },
                                },
                            },
                        },
                    },
                    "responses": {"204": {"description": "updated"}},
                },
            },
        },
        "components": {
            "parameters": {
                "SharedSearch": {
                    "name": "search",
                    "in": "query",
                    "schema": {
                        "anyOf": [
                            {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 100,
                            },
                            {"type": "null"},
                        ],
                    },
                },
            },
            "requestBodies": {
                "ItemBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/RequestModel",
                            },
                        },
                    },
                },
            },
            "schemas": {
                "BaseInput": {
                    "type": "object",
                    "required": ["bounded_nullable"],
                    "properties": {
                        "bounded_nullable": {
                            "anyOf": [
                                {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": 12,
                                },
                                {"type": "null"},
                            ],
                        },
                        "metadata": {
                            "type": "object",
                            "additionalProperties": {},
                        },
                        "bounded_metadata": {
                            "type": "object",
                            "additionalProperties": {},
                            "x-max-json-array-items": 5_000,
                            "x-max-json-bytes": 524_288,
                            "x-max-json-depth": 32,
                            "x-max-json-key-chars": 1_000,
                            "x-max-json-keys": 10_000,
                            "x-max-json-nodes": 20_000,
                        },
                        "decimal_value": {
                            "anyOf": [
                                {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1,
                                },
                                {
                                    "type": "string",
                                    "pattern": "^[0-9]+(?:\\.[0-9]+)?$",
                                },
                                {"type": "null"},
                            ],
                        },
                        "finite_enum": {
                            "type": "string",
                            "enum": ["FIRST", "SECOND"],
                        },
                        "finite_pattern": {
                            "type": "string",
                            "pattern": "^(FIRST|SECOND)$",
                        },
                        "identifier": {
                            "type": "string",
                            "format": "uuid",
                        },
                        "unbounded_count": {
                            "type": "integer",
                            "minimum": 0,
                        },
                        "raw": {},
                    },
                },
                "NestedInput": {
                    "allOf": [
                        {"$ref": "#/components/schemas/BaseInput"},
                        {
                            "type": "object",
                            "properties": {
                                "label": {
                                    "type": "string",
                                    "maxLength": 50,
                                },
                            },
                        },
                    ],
                },
                "RequestModel": {
                    "type": "object",
                    "required": ["nested"],
                    "properties": {
                        "nested": {
                            "$ref": "#/components/schemas/NestedInput",
                        },
                        "tags": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "maxLength": 20,
                            },
                        },
                    },
                },
                "ResponseModel": {
                    "type": "object",
                    "properties": {
                        "output_only": {"type": "string"},
                    },
                },
                "UnusedModel": {
                    "type": "object",
                    "properties": {
                        "unused": {"type": "string"},
                    },
                },
            },
        },
    }


def _find(
    rows: list[dict[str, Any]],
    *,
    schema: str | None = None,
    field: str,
    location: str = "component",
    path_fragment: str | None = None,
) -> dict[str, Any]:
    matches = [
        row
        for row in rows
        if row["schema"] == schema
        and row["field"] == field
        and row["location"] == location
        and (path_fragment is None or path_fragment in row["field_path"])
    ]
    assert len(matches) == 1
    return matches[0]


def test_inventory_tracks_reachability_nested_refs_and_all_of() -> None:
    rows = reports._field_inventory(_specification())

    inherited = _find(rows, schema="NestedInput", field="bounded_nullable")
    assert inherited["required"] is True
    assert inherited["nullable"] is True
    assert inherited["boundaries"] == {"maxLength": 12, "minLength": 1}
    assert inherited["usage"] == "both"
    assert inherited["request_reachable"] is True
    assert inherited["response_reachable"] is True
    assert inherited["boundary_review_required"] is False
    assert inherited["route_method_usage"] == [
        {
            "path": "/items",
            "method": "GET",
            "source": "response:200:application/json",
        },
        {
            "path": "/items",
            "method": "POST",
            "source": "requestBody:application/json",
        },
    ]

    response_only = _find(
        rows,
        schema="ResponseModel",
        field="output_only",
    )
    assert response_only["usage"] == "response"
    assert response_only["request_reachable"] is False
    assert response_only["risk"] == {
        "tier": "none",
        "reasons": [],
        "review_required": False,
    }
    assert not any(row["schema"] == "UnusedModel" for row in rows)


def test_inventory_includes_query_inline_and_structural_risks() -> None:
    rows = reports._field_inventory(_specification())

    search = _find(
        rows,
        field="search",
        location="query",
        path_fragment="POST /items",
    )
    assert search["nullable"] is True
    assert search["boundaries"] == {"maxLength": 100, "minLength": 1}
    assert search["risk_tier"] == "none"

    cursor = _find(rows, field="cursor", location="query")
    assert cursor["risk_tier"] == "medium"
    assert cursor["risk_reasons"] == ["unbounded_string"]

    raw = _find(rows, schema="BaseInput", field="raw")
    assert raw["risk_tier"] == "high"
    assert raw["risk_reasons"] == ["unconstrained_any"]

    metadata = _find(rows, schema="BaseInput", field="metadata")
    assert metadata["risk_tier"] == "high"
    assert metadata["risk_reasons"] == ["unbounded_object"]

    bounded_metadata = _find(
        rows,
        schema="BaseInput",
        field="bounded_metadata",
    )
    assert bounded_metadata["risk_tier"] == "none"
    assert bounded_metadata["boundaries"]["x-max-json-bytes"] == 524_288

    decimal_value = _find(rows, schema="BaseInput", field="decimal_value")
    assert decimal_value["primitive_type"] == "number"
    assert decimal_value["boundaries"]["maximum"] == 1
    assert decimal_value["boundaries"]["minimum"] == 0
    assert decimal_value["boundaries"]["pattern"]
    assert decimal_value["risk_tier"] == "none"

    for field in ("finite_enum", "finite_pattern", "identifier"):
        assert _find(rows, schema="BaseInput", field=field)["risk_tier"] == "none"

    unbounded_count = _find(rows, schema="BaseInput", field="unbounded_count")
    assert unbounded_count["risk_tier"] == "medium"
    assert unbounded_count["risk_reasons"] == ["unbounded_numeric"]

    tags = _find(rows, schema="RequestModel", field="tags")
    assert tags["risk_tier"] == "high"
    assert tags["risk_reasons"] == ["unbounded_array"]
    assert tags["item_boundaries"] == {"maxLength": 20}

    inline = _find(
        rows,
        field="payload",
        location="requestBody",
        path_fragment="patchInline",
    )
    assert inline["required"] is True
    assert inline["risk_reasons"] == ["unconstrained_any"]


def test_inventory_is_deterministic_and_main_emits_request_summary(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    specification = _specification()
    first = reports._field_inventory(specification)
    second = reports._field_inventory(specification)
    assert first == second
    assert first == sorted(
        first,
        key=lambda row: (
            row["location"],
            str(row["schema"]),
            row["field_path"],
        ),
    )

    monkeypatch.setattr(
        reports,
        "_application_openapi",
        lambda: specification,
    )
    monkeypatch.setattr(reports, "AUDIT_ROOT", tmp_path)
    reports.main()

    inventory = json.loads(
        (tmp_path / "request-boundary-inventory.json").read_text(
            encoding="utf-8",
        )
    )
    assert inventory["field_count"] == len(first)
    assert inventory["request_field_count"] == sum(
        row["request_reachable"] for row in first
    )
    assert inventory["response_only_field_count"] == 1
    assert inventory["query_parameter_count"] == 3
    assert inventory["fields_requiring_review"] == sum(
        row["boundary_review_required"] for row in first
    )
    assert sum(inventory["risk_tier_counts"].values()) == len(first)
