from __future__ import annotations

import uuid
import ast
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.modules.catalog.attribute_value_mutation_service import (
    AttributeValueMutationService,
)
from app.modules.catalog.enums import AttributeSourceType
from app.modules.catalog.formula_engine import FormulaEngine, FormulaError
from app.modules.catalog.schemas.attribute_platform import (
    BulkProductChange,
    EnterpriseBulkWrite,
    LockRequest,
)


def mutation_service() -> tuple[
    AttributeValueMutationService,
    AsyncMock,
    AsyncMock,
    SimpleNamespace,
]:
    session = AsyncMock()
    service = AttributeValueMutationService(session)
    repository = AsyncMock()
    attributes = SimpleNamespace(
        validate_value=AsyncMock(),
        write_value=AsyncMock(),
        repository=SimpleNamespace(add=AsyncMock()),
        _event=AsyncMock(),
    )
    service.repository = repository
    service.attributes = attributes
    service._required = AsyncMock(return_value=SimpleNamespace())  # type: ignore[method-assign]
    return service, session, repository, attributes


def scalar_result(items: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def test_formula_engine_guards_numeric_safety_and_dependency_graphs() -> None:
    engine = FormulaEngine()
    assert engine.dependencies("left + max(right, 1)") == {"left", "right"}
    assert engine.evaluate("2 + 3 - 1", {}) == 4
    assert engine.evaluate("8 / 2 + 7 // 3 + 7 % 3", {}) == 7
    assert engine.evaluate("-2 + +3", {}) == 1
    assert engine.evaluate("abs(-2) + round(2.4)", {}) == 4
    assert engine.evaluate("2 ** 10", {}) == 1024

    with pytest.raises(FormulaError, match="Missing formula values"):
        engine.evaluate("missing + 1", {})
    with pytest.raises(FormulaError, match="result is not numeric"):
        engine.evaluate("value", {"value": object()})
    with pytest.raises(FormulaError, match="Invalid formula"):
        engine.evaluate("1 +", {})
    with pytest.raises(FormulaError, match="Unsupported formula element"):
        engine.evaluate("[1]", {})
    with pytest.raises(FormulaError, match="Unsupported formula function"):
        engine.evaluate("sum(1)", {})
    with pytest.raises(FormulaError, match="Unsupported formula function"):
        engine.evaluate("round(1, ndigits=0)", {})
    with pytest.raises(FormulaError, match="Only numeric constants"):
        engine.evaluate("'text'", {})
    with pytest.raises(FormulaError, match="Exponent is outside"):
        engine.evaluate("2 ** 11", {})
    with pytest.raises(FormulaError, match="Formula arithmetic failed"):
        engine.evaluate("1 / 0", {})
    with pytest.raises(FormulaError, match="Unsupported formula expression"):
        engine._eval(ast.Load(), {})

    engine.validate_graph(
        {
            "total": {"left", "right"},
            "left": {"shared"},
            "right": {"shared"},
            "shared": set(),
        }
    )
    with pytest.raises(FormulaError, match="dependency cycle"):
        engine.validate_graph({"left": {"right"}, "right": {"left"}})


@pytest.mark.asyncio
async def test_recalculation_resolves_chains_skips_unusable_formulas_and_commits() -> (
    None
):
    service, session, repository, attributes = mutation_service()
    product_id = uuid.uuid4()
    source_id = uuid.uuid4()
    derived_id = uuid.uuid4()
    chained_id = uuid.uuid4()
    definitions = [
        SimpleNamespace(id=source_id, api_name="source"),
        SimpleNamespace(id=derived_id, api_name="derived"),
        SimpleNamespace(id=chained_id, api_name="chained"),
    ]
    repository.list_definitions.return_value = definitions
    repository.values.return_value = [
        SimpleNamespace(
            attribute_definition_id=source_id,
            numeric_value=2,
            canonical_value="2",
        )
    ]
    chained_formula = SimpleNamespace(
        id=uuid.uuid4(),
        target_attribute_id=chained_id,
        expression="derived + 1",
    )
    missing_target = SimpleNamespace(
        id=uuid.uuid4(),
        target_attribute_id=uuid.uuid4(),
        expression="source",
    )
    unresolved = SimpleNamespace(
        id=uuid.uuid4(),
        target_attribute_id=chained_id,
        expression="unknown + 1",
    )
    direct_formula = SimpleNamespace(
        id=uuid.uuid4(),
        target_attribute_id=derived_id,
        expression="source + 1",
    )
    session.execute.return_value = scalar_result(
        [chained_formula, missing_target, unresolved, direct_formula]
    )
    service.formulas = MagicMock()
    service.formulas.dependencies.side_effect = lambda expression: {
        "derived + 1": {"derived"},
        "source": {"source"},
        "unknown + 1": {"unknown"},
        "source + 1": {"source"},
    }[expression]
    service.formulas.evaluate.side_effect = [3, 4]
    direct_record = SimpleNamespace(id=uuid.uuid4())
    chained_record = SimpleNamespace(id=uuid.uuid4())
    attributes.write_value.side_effect = [direct_record, chained_record]

    written = await service.recalculate_product(
        product_id,
        changed_attribute_id=source_id,
    )

    assert written == [direct_record, chained_record]
    assert attributes.write_value.await_count == 2
    first_payload = attributes.write_value.await_args_list[0].args[2]
    assert first_payload.source_type is AttributeSourceType.SYSTEM
    assert first_payload.raw_value == "3"
    session.commit.assert_awaited_once()
    assert session.refresh.await_count == 2


@pytest.mark.asyncio
async def test_recalculation_can_join_canonical_values_without_committing() -> None:
    service, session, repository, attributes = mutation_service()
    product_id = uuid.uuid4()
    source_id = uuid.uuid4()
    target_id = uuid.uuid4()
    repository.list_definitions.return_value = [
        SimpleNamespace(id=source_id, api_name="source"),
        SimpleNamespace(id=target_id, api_name="target"),
    ]
    repository.values.return_value = [
        SimpleNamespace(
            attribute_definition_id=source_id,
            numeric_value=None,
            canonical_value="text",
        )
    ]
    formula = SimpleNamespace(
        id=uuid.uuid4(),
        target_attribute_id=target_id,
        expression="source",
    )
    session.execute.return_value = scalar_result([formula])
    service.formulas = MagicMock()
    service.formulas.dependencies.return_value = {"source"}
    service.formulas.evaluate.return_value = "TEXT"
    record = SimpleNamespace(id=uuid.uuid4())
    attributes.write_value.return_value = record

    written = await service.recalculate_product(
        product_id,
        changed_attribute_id=uuid.uuid4(),
        commit=False,
    )

    assert written == [record]
    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_lock_and_unlock_write_history_event_and_guard_missing_value() -> None:
    service, session, repository, attributes = mutation_service()
    product_id = uuid.uuid4()
    attribute_id = uuid.uuid4()
    repository.values.return_value = []
    with pytest.raises(HTTPException) as missing:
        await service.lock_value(
            product_id,
            attribute_id,
            LockRequest(actor="operator"),
            True,
        )
    assert missing.value.status_code == 404

    for locked in (True, False):
        service, session, repository, attributes = mutation_service()
        record = SimpleNamespace(
            id=uuid.uuid4(),
            raw_value="raw",
            canonical_value="canonical",
            source_type="MANUAL",
            source_reference=None,
            confidence_score=None,
            is_locked=not locked,
            locked_by="old",
            locked_at=None,
            lock_reason="old",
            version=4,
        )
        repository.values.return_value = [record]
        returned = await service.lock_value(
            product_id,
            attribute_id,
            LockRequest(actor="operator", reason="review"),
            locked,
        )
        assert returned is record
        assert record.is_locked is locked
        assert record.locked_by == ("operator" if locked else None)
        assert record.lock_reason == ("review" if locked else None)
        assert record.version == 5
        session.flush.assert_awaited_once()
        history = attributes.repository.add.await_args.args[0]
        assert history.action == ("LOCKED" if locked else "UNLOCKED")
        attributes._event.assert_awaited_once()
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(record)


@pytest.mark.asyncio
async def test_bulk_preview_commit_and_failure_are_atomic() -> None:
    product_id = uuid.uuid4()
    attribute_id = uuid.uuid4()
    payload = EnterpriseBulkWrite(
        items=[
            BulkProductChange(
                product_id=product_id,
                attribute_id=attribute_id,
                raw_value="value",
                unit="kg",
            )
        ]
    )

    service, session, _, attributes = mutation_service()
    validation = MagicMock()
    validation.model_dump.return_value = {"valid": True}
    attributes.validate_value.return_value = validation
    preview = await service.bulk_update(payload, preview=True)
    assert preview[0]["validation"] == {"valid": True}
    attributes.write_value.assert_not_awaited()
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()

    service, session, _, attributes = mutation_service()
    attributes.validate_value.return_value = validation
    committed = await service.bulk_update(payload, preview=False)
    assert committed[0]["product_id"] == product_id
    write_payload = attributes.write_value.await_args.args[2]
    assert write_payload.source_type is AttributeSourceType.MANUAL
    assert write_payload.unit == "kg"
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()

    service, session, _, attributes = mutation_service()
    attributes.validate_value.side_effect = RuntimeError("validation failed")
    with pytest.raises(RuntimeError, match="validation failed"):
        await service.bulk_update(payload, preview=False)
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
