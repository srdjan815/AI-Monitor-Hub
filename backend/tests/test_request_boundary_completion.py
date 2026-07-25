from __future__ import annotations

import math
import uuid
from decimal import Decimal
from typing import Annotated

import pytest
from pydantic import Field, TypeAdapter, ValidationError

from app.core.limits import (
    MAX_BULK_ITEMS,
    MAX_CONTENT_CHARS,
    MAX_CURSOR_CHARS,
    MAX_DB_INTEGER,
    MAX_DESCRIPTION_CHARS,
    MAX_JSON_ARRAY_ITEMS,
    MAX_JSON_BYTES,
    MAX_JSON_DEPTH,
    MAX_JSON_KEY_CHARS,
    MAX_JSON_KEYS,
    MAX_JSON_NODES,
    MAX_LEGACY_OFFSET,
    MAX_NOTE_CHARS,
    MAX_PROMPT_CHARS,
    validate_json_size,
)
from app.core.pagination import InvalidCursorError, decode_cursor
from app.main import app
from app.modules.catalog.schemas.attribute_platform import (
    BulkProductChange,
    EnterpriseBulkWrite,
    TemplateImport,
)
from app.modules.catalog.schemas.product_attributes import (
    AttributeDefinitionCreate,
    ProductAttributeValueWrite,
    ReorderItem,
    ReorderRequest,
)
from app.modules.execution.schemas import JobCreate
from app.modules.inventory.schemas import InventoryCreate, InventoryMovementCreate
from app.modules.product_content.schemas import (
    ContentTypeCreate,
    ContentWrite,
    LandingWrite,
    LibraryWrite,
    PromptWrite,
    ReferenceWrite,
    RollbackRequest,
    SEOWrite,
    ScoringPolicyWrite,
    TemplateWrite,
)
from scripts.generate_contract_reports import _field_inventory


def _nested_json(depth: int) -> dict[str, object]:
    value: dict[str, object] = {}
    for _ in range(depth - 1):
        value = {"child": value}
    return value


def test_json_validator_enforces_exact_encoded_byte_boundary() -> None:
    exact = {"v": "x" * (MAX_JSON_BYTES - 8)}
    assert validate_json_size(exact, field_name="payload") is exact

    with pytest.raises(ValueError, match="encoded bytes"):
        validate_json_size(
            {"v": "x" * (MAX_JSON_BYTES - 7)},
            field_name="payload",
        )


def test_json_validator_enforces_structure_and_finite_values() -> None:
    assert validate_json_size(
        _nested_json(MAX_JSON_DEPTH),
        field_name="payload",
    )

    with pytest.raises(ValueError, match="nesting depth"):
        validate_json_size(
            _nested_json(MAX_JSON_DEPTH + 1),
            field_name="payload",
        )
    with pytest.raises(ValueError, match="array with more than"):
        validate_json_size(
            [None] * (MAX_JSON_ARRAY_ITEMS + 1),
            field_name="payload",
        )
    with pytest.raises(ValueError, match="JSON keys"):
        validate_json_size(
            {f"k{index}": None for index in range(MAX_JSON_KEYS + 1)},
            field_name="payload",
        )
    with pytest.raises(ValueError, match="JSON key longer"):
        validate_json_size(
            {"k" * (MAX_JSON_KEY_CHARS + 1): None},
            field_name="payload",
        )

    node_heavy = [[0, 0, 0, 0] for _ in range(MAX_JSON_ARRAY_ITEMS)]
    assert len(node_heavy) * 5 + 1 > MAX_JSON_NODES
    with pytest.raises(ValueError, match="JSON nodes"):
        validate_json_size(node_heavy, field_name="payload")

    for non_finite in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="non-finite"):
            validate_json_size({"number": non_finite}, field_name="payload")

    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError, match="cyclic"):
        validate_json_size(cyclic, field_name="payload")
    with pytest.raises(ValueError, match="non-JSON"):
        validate_json_size({"value": object()}, field_name="payload")

    shared: dict[str, object] = {"value": "reused"}
    repeated_reference = {"first": shared, "second": shared}
    assert (
        validate_json_size(repeated_reference, field_name="payload")
        is repeated_reference
    )


def test_json_constraints_apply_to_every_high_risk_request_family() -> None:
    invalid_json = {"value": math.nan}
    constructors = (
        lambda: JobCreate(job_type="system.synthetic", payload=invalid_json),
        lambda: AttributeDefinitionCreate(
            name="Bounded",
            default_value=invalid_json,
        ),
        lambda: ProductAttributeValueWrite(raw_value=invalid_json),
        lambda: BulkProductChange(
            product_id=uuid.uuid4(),
            attribute_id=uuid.uuid4(),
            raw_value=invalid_json,
        ),
        lambda: SEOWrite(
            language_id=uuid.uuid4(),
            seo_title="Title",
            seo_description="Description",
            slug="bounded",
            schema_org=invalid_json,
        ),
        lambda: LandingWrite(
            language_id=uuid.uuid4(),
            title="Title",
            slug="bounded",
            body="Body",
            meta=invalid_json,
        ),
    )
    for constructor in constructors:
        with pytest.raises(ValidationError):
            constructor()


def test_bulk_and_collection_boundaries_are_explicit() -> None:
    exact_reorder = [
        ReorderItem(id=uuid.uuid4(), sort_order=index)
        for index in range(MAX_BULK_ITEMS)
    ]
    assert len(ReorderRequest(items=exact_reorder).items) == MAX_BULK_ITEMS
    with pytest.raises(ValidationError):
        ReorderRequest(
            items=[
                *exact_reorder,
                ReorderItem(id=uuid.uuid4(), sort_order=MAX_BULK_ITEMS),
            ]
        )

    exact_bulk = [
        BulkProductChange(
            product_id=uuid.uuid4(),
            attribute_id=uuid.uuid4(),
            raw_value=index,
        )
        for index in range(MAX_BULK_ITEMS)
    ]
    assert len(EnterpriseBulkWrite(items=exact_bulk).items) == MAX_BULK_ITEMS
    with pytest.raises(ValidationError):
        EnterpriseBulkWrite(
            items=[
                *exact_bulk,
                BulkProductChange(
                    product_id=uuid.uuid4(),
                    attribute_id=uuid.uuid4(),
                    raw_value="over",
                ),
            ]
        )

    with pytest.raises(ValidationError):
        TemplateImport(
            name="Template",
            slug="template",
            items=[
                {
                    "attribute_definition_id": uuid.uuid4(),
                    "sort_order": index,
                }
                for index in range(MAX_BULK_ITEMS + 1)
            ],
        )


def test_text_unicode_null_and_database_column_boundaries() -> None:
    assert ContentTypeCreate(name="Type", slug=None).slug is None
    assert (
        len(
            ReferenceWrite(
                title="🚀" * 500,
                url="https://example.test",
                reference_type="document",
            ).title
        )
        == 500
    )

    invalid_payloads = (
        lambda: ContentTypeCreate(name="Type", slug="x" * 256),
        lambda: ContentWrite(
            language_id=uuid.uuid4(),
            content_type_id=uuid.uuid4(),
            content="Body",
            prompt_version="x" * 101,
        ),
        lambda: ReferenceWrite(
            title="e\u0301" * 251,
            url="https://example.test",
            reference_type="document",
        ),
        lambda: LibraryWrite(
            name="x" * 256,
            item_kind="BLOCK",
            language_id=uuid.uuid4(),
            content="Body",
        ),
        lambda: TemplateWrite(name=""),
        lambda: LandingWrite(
            language_id=uuid.uuid4(),
            title="Title",
            slug="landing",
            body="x" * (MAX_CONTENT_CHARS + 1),
        ),
    )
    for constructor in invalid_payloads:
        with pytest.raises(ValidationError):
            constructor()


def test_description_prompt_note_and_duplicate_field_boundaries() -> None:
    description = "d" * MAX_DESCRIPTION_CHARS
    assert (
        ContentTypeCreate(name="Type", description=description).description
        == description
    )
    with pytest.raises(ValidationError):
        ContentTypeCreate(
            name="Type",
            description=description + "x",
        )

    prompt = "p" * MAX_PROMPT_CHARS
    assert PromptWrite(prompt=prompt).prompt == prompt
    with pytest.raises(ValidationError):
        PromptWrite(prompt=prompt + "x")

    note = "n" * MAX_NOTE_CHARS
    movement = InventoryMovementCreate(
        movement_type="RECEIPT",
        product_id=uuid.uuid4(),
        destination_warehouse_id=uuid.uuid4(),
        quantity=1,
        note=note,
    )
    assert movement.note == note
    with pytest.raises(ValidationError):
        InventoryMovementCreate(
            movement_type="RECEIPT",
            product_id=uuid.uuid4(),
            destination_warehouse_id=uuid.uuid4(),
            quantity=1,
            note=note + "x",
        )

    assert ContentTypeCreate(name="Type", description="").description == ""
    assert PromptWrite(prompt="").prompt == ""

    repeated = ContentTypeCreate.model_validate_json('{"name":"first","name":"last"}')
    assert repeated.name == "last"
    with pytest.raises(ValidationError):
        ContentTypeCreate.model_validate_json(
            '{"name":"safe","name":"' + ("x" * 256) + '"}'
        )


def test_decimal_and_database_integer_boundaries() -> None:
    exact_decimal = Decimal("9" * 16 + "." + "9" * 8)
    definition = AttributeDefinitionCreate(
        name="Bounded decimal",
        minimum_value=exact_decimal,
        minimum_length=MAX_DB_INTEGER,
        confidence_threshold=Decimal("0.1234"),
    )
    assert definition.minimum_value == exact_decimal
    assert definition.minimum_length == MAX_DB_INTEGER

    invalid_definitions = (
        {
            "minimum_value": Decimal("9" * 17 + "." + "9" * 8),
        },
        {
            "minimum_value": Decimal("0.123456789"),
        },
        {
            "minimum_length": MAX_DB_INTEGER + 1,
        },
        {
            "confidence_threshold": Decimal("0.12345"),
        },
    )
    for values in invalid_definitions:
        with pytest.raises(ValidationError):
            AttributeDefinitionCreate(name="Invalid", **values)

    with pytest.raises(ValidationError):
        ContentWrite(
            language_id=uuid.uuid4(),
            content_type_id=uuid.uuid4(),
            content="Body",
            token_count=MAX_DB_INTEGER + 1,
        )
    with pytest.raises(ValidationError):
        ContentWrite(
            language_id=uuid.uuid4(),
            content_type_id=uuid.uuid4(),
            content="Body",
            generation_time_ms=MAX_DB_INTEGER + 1,
        )
    with pytest.raises(ValidationError):
        ScoringPolicyWrite(
            name="Overflow",
            short_description_weight=MAX_DB_INTEGER + 1,
        )
    with pytest.raises(ValidationError):
        RollbackRequest(revision=MAX_DB_INTEGER + 1)


def test_inventory_integer_and_cursor_limits_fail_before_persistence() -> None:
    with pytest.raises(ValidationError):
        InventoryCreate(
            warehouse_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            quantity_on_hand=MAX_DB_INTEGER + 1,
        )
    with pytest.raises(ValidationError):
        InventoryMovementCreate(
            movement_type="RECEIPT",
            product_id=uuid.uuid4(),
            destination_warehouse_id=uuid.uuid4(),
            quantity=MAX_DB_INTEGER + 1,
        )

    with pytest.raises(InvalidCursorError, match="maximum encoded length"):
        decode_cursor(
            "x" * (MAX_CURSOR_CHARS + 1),
            "test.resource",
            {},
        )

    with pytest.raises(InvalidCursorError) as exact_cursor_error:
        decode_cursor(
            "x" * MAX_CURSOR_CHARS,
            "test.resource",
            {},
        )
    assert "maximum encoded length" not in str(exact_cursor_error.value)


def test_openapi_schema_exposes_structural_and_collection_limits() -> None:
    job_payload = JobCreate.model_json_schema()["properties"]["payload"]
    assert job_payload["x-max-json-bytes"] == MAX_JSON_BYTES
    assert job_payload["x-max-json-depth"] == MAX_JSON_DEPTH
    assert job_payload["x-max-json-nodes"] == MAX_JSON_NODES

    examples = AttributeDefinitionCreate.model_json_schema()["properties"]["examples"]
    assert examples["maxItems"] == MAX_BULK_ITEMS
    assert examples["x-max-json-array-items"] == MAX_JSON_ARRAY_ITEMS

    enterprise_items = EnterpriseBulkWrite.model_json_schema()["properties"]["items"]
    assert enterprise_items["maxItems"] == MAX_BULK_ITEMS


def test_openapi_has_no_unreviewed_request_boundary_candidates() -> None:
    fields = _field_inventory(app.openapi())
    unresolved = [
        field["field_path"]
        for field in fields
        if field["request_reachable"] and field["boundary_review_required"]
    ]
    assert unresolved == []


def test_openapi_exposes_persistence_sized_query_filter_limits() -> None:
    expected_limits = {
        ("/api/v1/attributes", "scope"): 32,
        ("/api/v1/catalog/attribute-changes", "entity_type"): 80,
        ("/api/v1/catalog/attribute-definitions", "scope"): 32,
        ("/api/v1/catalog/attribute-formulas", "kind"): 32,
        (
            "/api/v1/catalog/categories/{category_id}/attributes/resolved",
            "scope",
        ): 32,
        ("/api/v1/catalog/products/{product_id}/attributes", "scope"): 32,
        (
            "/api/v1/catalog/products/{product_id}/attributes/resolved",
            "scope",
        ): 32,
        (
            "/api/v1/catalog/products/{product_id}/attributes/resolved/export",
            "scope",
        ): 32,
        ("/api/v1/content/entries", "approval"): 32,
        ("/api/v1/content/entries", "source"): 32,
        ("/api/v1/content/entries", "status"): 32,
        ("/api/v1/content/entries", "updated_from"): 64,
        ("/api/v1/content/library", "category"): 120,
        ("/api/v1/content/library", "kind"): 32,
        ("/api/v1/content/library", "tag"): 255,
        (
            "/api/v1/content/products/{product_id}/score-history",
            "score_type",
        ): 20,
        ("/api/v1/content/search", "approval"): 32,
        ("/api/v1/content/search", "status"): 32,
    }
    specification = app.openapi()
    for (path, name), expected in expected_limits.items():
        parameter = next(
            item
            for item in specification["paths"][path]["get"]["parameters"]
            if item["name"] == name and item["in"] == "query"
        )
        schema = parameter["schema"]
        if "anyOf" in schema:
            schema = next(
                branch for branch in schema["anyOf"] if branch.get("type") != "null"
            )
        assert schema["maxLength"] == expected, (path, name)


def test_every_legacy_offset_has_an_exact_compatibility_ceiling() -> None:
    specification = app.openapi()
    offset_schemas = [
        parameter["schema"]
        for path_item in specification["paths"].values()
        for method, operation in path_item.items()
        if method
        in {
            "delete",
            "get",
            "head",
            "options",
            "patch",
            "post",
            "put",
            "trace",
        }
        for parameter in operation.get("parameters", [])
        if parameter.get("in") == "query" and parameter.get("name") == "offset"
    ]
    assert len(offset_schemas) == 43
    assert all(schema.get("maximum") == MAX_LEGACY_OFFSET for schema in offset_schemas)

    offset_adapter = TypeAdapter(Annotated[int, Field(ge=0, le=MAX_LEGACY_OFFSET)])
    assert offset_adapter.validate_python(MAX_LEGACY_OFFSET) == MAX_LEGACY_OFFSET
    with pytest.raises(ValidationError):
        offset_adapter.validate_python(MAX_LEGACY_OFFSET + 1)
