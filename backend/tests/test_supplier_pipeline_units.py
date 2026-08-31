from __future__ import annotations

import logging
import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.suppliers.pipeline_contracts import (
    PipelineContext,
    PipelinePhaseResult,
    PipelineReferences,
    PipelineResult,
)
from app.modules.suppliers.pipeline_models import (
    SupplierSourcePipelineRun,
    SupplierSourceSchedule,
)
from app.modules.suppliers.pipeline_scheduler import (
    SupplierPipelineScheduleCalculator,
)
from app.modules.suppliers.schema_compatibility_service import (
    SupplierSchemaCompatibilityService,
)
from app.modules.suppliers.schema_profile_models import (
    SupplierSchemaField,
    SupplierSchemaProfile,
)
from app.modules.suppliers.schedule_schemas import (
    PipelineRunNowRequest,
    SupplierScheduleWrite,
)
from app.modules.suppliers.schedule_service import SupplierScheduleService


def _profile(**values: object) -> SupplierSchemaProfile:
    defaults: dict[str, object] = {
        "source_connection_id": uuid.uuid4(),
        "name": "Schema",
        "version_number": 1,
        "status": "ACTIVE",
        "is_active": True,
        "field_count": 1,
        "detected_format": "XML",
        "root_path": "/products",
        "record_path": "//product",
        "compatibility_policy": {},
        "analysis_metadata": {},
    }
    return SupplierSchemaProfile(**(defaults | values))


def _field(
    profile_id: uuid.UUID,
    *,
    path: str = "price",
    data_type: str = "DECIMAL",
    required: bool = True,
) -> SupplierSchemaField:
    return SupplierSchemaField(
        schema_profile_id=profile_id,
        field_code=path,
        name=path,
        position=1,
        data_type=data_type,
        required=required,
        nullable=not required,
        path=path,
        is_active=True,
    )


def test_pipeline_result_and_context_are_framework_neutral() -> None:
    run = SupplierSourcePipelineRun(
        source_connection_id=uuid.uuid4(),
        trigger_type="MANUAL",
        automation_depth="FETCH_ONLY",
        status="PENDING",
        current_phase="FETCH",
        phase_results={},
        idempotency_key=uuid.uuid4().hex,
        created_by="test",
    )
    context = PipelineContext(
        supplier=object(),  # type: ignore[arg-type]
        source=object(),  # type: ignore[arg-type]
        run=run,
        trigger="MANUAL",
        idempotency_key=run.idempotency_key,
        logger=logging.getLogger("test"),
    )
    result = PipelineResult(
        status="SUCCEEDED",
        completed_phase="TECHNICAL_VALIDATE",
        references=PipelineReferences(),
    )
    assert context.run is run
    assert result.successful
    with pytest.raises(FrozenInstanceError):
        context.trigger = "SCHEDULED"  # type: ignore[misc]


def test_phase_result_has_a_stable_persistent_shape() -> None:
    started = datetime.now(UTC)
    result = PipelinePhaseResult(
        status="SUCCEEDED",
        started_at=started,
        completed_at=started,
        duration_ms=12,
        warning_count=1,
        reference_id=str(uuid.uuid4()),
        processed_records=25,
    )
    assert set(result.as_dict()) == {
        "status",
        "started_at",
        "completed_at",
        "duration_ms",
        "error_code",
        "warning_count",
        "reference_id",
        "processed_records",
        "error_count",
    }


def test_compatibility_is_typed_and_missing_required_field_is_incompatible() -> None:
    active = _profile()
    analyzed = _profile(status="DRAFT")
    result = SupplierSchemaCompatibilityService().compare(
        active,
        [_field(active.id)],
        analyzed,
        [],
        mapped_field_ids=set(),
        baseline_record_count=None,
        current_record_count=100,
    )
    assert result.status == "INCOMPATIBLE"
    assert result.severity == "ERROR"
    assert result.changes[0].code == "FIELD_MISSING"


def test_record_drop_needs_an_explicit_policy_and_baseline() -> None:
    active = _profile()
    analyzed = _profile(status="DRAFT")
    service = SupplierSchemaCompatibilityService()
    without_baseline = service.compare(
        active,
        [],
        analyzed,
        [],
        mapped_field_ids=set(),
        baseline_record_count=None,
        current_record_count=1,
    )
    assert without_baseline.status == "COMPATIBLE"
    active.compatibility_policy = {"maximum_drop_percentage": 20}
    with_baseline = service.compare(
        active,
        [],
        analyzed,
        [],
        mapped_field_ids=set(),
        baseline_record_count=100,
        current_record_count=50,
    )
    assert with_baseline.status == "INCOMPATIBLE"


def test_schedule_next_run_supports_timezone_and_multiple_daily_times() -> None:
    schedule = type(
        "Schedule",
        (),
        {
            "timezone": "Europe/Belgrade",
            "schedule_type": "MULTI_DAILY",
            "schedule_configuration": {"times": ["06:00", "18:00"]},
        },
    )()
    after = datetime(2026, 7, 29, 5, 0, tzinfo=UTC)
    assert SupplierPipelineScheduleCalculator.next_run(
        schedule, after
    ) == datetime(2026, 7, 29, 16, 0, tzinfo=UTC)


def test_schedule_payload_validates_manual_interval_and_weekly_modes() -> None:
    manual = SupplierScheduleWrite(status="MANUAL")
    assert manual.configuration() == {"times": []}
    interval = SupplierScheduleWrite(
        status="ENABLED",
        schedule_type="INTERVAL",
        interval_hours=4,
    )
    assert interval.configuration() == {"interval_hours": 4}
    weekly = SupplierScheduleWrite(
        status="ENABLED",
        schedule_type="WEEKLY",
        times=["08:00"],
        weekdays=[1, 3, 5],
    )
    assert weekly.configuration() == {
        "times": ["08:00"],
        "weekdays": [1, 3, 5],
    }
    with pytest.raises(ValidationError):
        SupplierScheduleWrite(status="ENABLED", schedule_type="DAILY")


@pytest.mark.asyncio
async def test_schedule_optimistic_lock_and_pause_are_safe() -> None:
    now = datetime.now(UTC)
    schedule = SupplierSourceSchedule(
        id=uuid.uuid4(),
        source_connection_id=uuid.uuid4(),
        status="ENABLED",
        schedule_type="DAILY",
        timezone="Europe/Belgrade",
        schedule_configuration={"times": ["06:00"]},
        automation_depth="FULL_PIPELINE",
        next_run_at=now,
        timeout_seconds=300,
        max_attempts=3,
        consecutive_failures=0,
        version=2,
    )
    schedule.created_at = now
    schedule.updated_at = now
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        refresh=AsyncMock(),
    )
    service = SupplierScheduleService(session)  # type: ignore[arg-type]
    service._source = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(is_active=True, status="ACTIVE")
    )
    service.repository.schedule = AsyncMock(return_value=schedule)
    service.repository.mutate = AsyncMock(
        side_effect=lambda entity, changes: [
            setattr(entity, key, value) for key, value in changes.items()
        ]
    )

    with pytest.raises(HTTPException) as conflict:
        await service.save(
            uuid.uuid4(),
            schedule.source_connection_id,
            SupplierScheduleWrite(
                version=1,
                status="PAUSED",
                schedule_type="DAILY",
                times=["06:00"],
            ),
        )
    assert conflict.value.status_code == 409

    paused = await service.save(
        uuid.uuid4(),
        schedule.source_connection_id,
        SupplierScheduleWrite(
            version=2,
            status="PAUSED",
            schedule_type="DAILY",
            times=["06:00"],
        ),
    )
    assert paused.status == "PAUSED"
    assert paused.next_run_at is None
    assert paused.version == 3
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_now_rejects_parallel_pipeline_for_same_source() -> None:
    source_id = uuid.uuid4()
    session = SimpleNamespace(rollback=AsyncMock())
    service = SupplierScheduleService(session)  # type: ignore[arg-type]
    service._source = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            id=source_id,
            is_active=True,
            status="ACTIVE",
        )
    )
    service.repository.pipeline_by_idempotency = AsyncMock(return_value=None)
    service.repository.active_pipeline = AsyncMock(return_value=object())

    with pytest.raises(HTTPException) as conflict:
        await service.run_now(
            uuid.uuid4(),
            source_id,
            PipelineRunNowRequest(
                automation_depth="FULL_PIPELINE",
                idempotency_key=f"test:{uuid.uuid4()}",
            ),
        )
    assert conflict.value.status_code == 409
    assert conflict.value.detail["code"] == "supplier_pipeline_already_running"
