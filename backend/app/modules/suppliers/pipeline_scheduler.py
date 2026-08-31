from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.execution.models import Job
from app.modules.suppliers.pipeline_models import SupplierSourcePipelineRun
from app.modules.suppliers.pipeline_repository import SupplierPipelineRepository


class SupplierPipelineScheduleCalculator:
    @classmethod
    def next_run(cls, schedule: object, after: datetime) -> datetime:
        timezone_name = str(getattr(schedule, "timezone"))
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("schedule_timezone_invalid") from exc
        local = after.astimezone(zone)
        kind = getattr(schedule, "schedule_type")
        config = getattr(schedule, "schedule_configuration")
        if kind == "INTERVAL":
            hours = config.get("interval_hours")
            if not isinstance(hours, int) or not 1 <= hours <= 720:
                raise ValueError("schedule_interval_invalid")
            return (after + timedelta(hours=hours)).astimezone(UTC)
        times = cls._times(config)
        weekdays = cls._weekdays(kind, config)
        for day_offset in range(0, 15):
            day = local.date() + timedelta(days=day_offset)
            if weekdays is not None and day.isoweekday() not in weekdays:
                continue
            for hour, minute in times:
                candidate = datetime(
                    day.year,
                    day.month,
                    day.day,
                    hour,
                    minute,
                    tzinfo=zone,
                )
                if candidate > local:
                    return candidate.astimezone(UTC)
        raise ValueError("schedule_next_run_unavailable")

    @staticmethod
    def _times(config: dict[str, object]) -> list[tuple[int, int]]:
        values = config.get("times")
        if not isinstance(values, list) or not values:
            raise ValueError("schedule_times_invalid")
        result: list[tuple[int, int]] = []
        for value in values:
            try:
                hour, minute = (int(item) for item in str(value).split(":", 1))
            except (TypeError, ValueError) as exc:
                raise ValueError("schedule_times_invalid") from exc
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError("schedule_times_invalid")
            result.append((hour, minute))
        return sorted(set(result))

    @staticmethod
    def _weekdays(
        kind: str | None, config: dict[str, object]
    ) -> set[int] | None:
        if kind in {"DAILY", "MULTI_DAILY"}:
            return None
        if kind == "WEEKDAYS":
            return {1, 2, 3, 4, 5}
        if kind == "WEEKLY":
            values = config.get("weekdays")
            if (
                not isinstance(values, list)
                or not values
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or not 1 <= value <= 7
                    for value in values
                )
            ):
                raise ValueError("schedule_weekdays_invalid")
            return set(values)
        raise ValueError("schedule_type_invalid")


class SupplierPipelineScheduler:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierPipelineRepository(session)

    async def dispatch_due(
        self,
        now: datetime | None = None,
        *,
        limit: int = 25,
    ) -> int:
        current = now or datetime.now(UTC)
        schedules = await self.repository.due_schedules(current, limit=limit)
        count = 0
        try:
            for schedule in schedules:
                occurrence = schedule.next_run_at
                if occurrence is None:
                    continue
                active = await self.repository.active_pipeline(
                    schedule.source_connection_id
                )
                if active is not None:
                    await self.repository.mutate(
                        schedule,
                        {
                            "last_run_at": occurrence,
                            "last_result": "SKIPPED",
                            "next_run_at": (
                                SupplierPipelineScheduleCalculator.next_run(
                                    schedule, occurrence
                                )
                            ),
                            "version": schedule.version + 1,
                        },
                    )
                    continue
                idempotency = f"supplier-schedule:{schedule.id}:{occurrence.isoformat()}"
                existing = await self.repository.pipeline_by_idempotency(idempotency)
                if existing is None:
                    run = SupplierSourcePipelineRun(
                        source_connection_id=schedule.source_connection_id,
                        schedule_id=schedule.id,
                        trigger_type="SCHEDULED",
                        automation_depth=schedule.automation_depth,
                        status="PENDING",
                        current_phase="FETCH",
                        phase_results={},
                        idempotency_key=idempotency,
                        schedule_occurrence_at=occurrence,
                        created_by="scheduler",
                    )
                    await self.repository.add(run)
                    job = Job(
                        job_type="supplier.pipeline",
                        queue="default",
                        priority=100,
                        status="PENDING",
                        payload={
                            "source_id": str(schedule.source_connection_id),
                            "pipeline_run_id": str(run.id),
                            "timeout_seconds": schedule.timeout_seconds,
                        },
                        max_attempts=schedule.max_attempts,
                        available_at=current,
                        idempotency_key=f"{idempotency}:job",
                        created_by="scheduler",
                    )
                    self.session.add(job)
                    await self.session.flush()
                    await self.repository.mutate(run, {"job_id": job.id})
                    count += 1
                await self.repository.mutate(
                    schedule,
                    {
                        "last_run_at": occurrence,
                        "next_run_at": SupplierPipelineScheduleCalculator.next_run(
                            schedule, occurrence
                        ),
                        "version": schedule.version + 1,
                    },
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return count


__all__ = [
    "SupplierPipelineScheduleCalculator",
    "SupplierPipelineScheduler",
]
