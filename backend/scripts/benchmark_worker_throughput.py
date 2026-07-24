from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any

import asyncpg


TERMINAL_STATUSES = ("SUCCEEDED", "FAILED", "CANCELLED", "DEAD_LETTER")


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    jobs: int
    duration_ms: int
    outcome: str = "success"
    retry_until_attempt: int = 0
    max_attempts: int = 3


SCENARIOS = (
    Scenario("fast", 100, 0),
    Scenario("medium", 40, 50),
    Scenario(
        "retrying",
        12,
        0,
        outcome="retryable",
        retry_until_attempt=1,
        max_attempts=2,
    ),
    Scenario("failing", 40, 0, outcome="permanent"),
    Scenario("heartbeat_long", 8, 1_500),
)


def percentile(values: list[float], percentage: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def distribution(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    return {
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
    }


async def seed(
    connection: asyncpg.Connection,
    scenario: Scenario,
    queue: str,
) -> None:
    await connection.execute("TRUNCATE job_attempts, jobs CASCADE")
    await connection.execute(
        """
        INSERT INTO jobs (
            job_type,
            queue,
            priority,
            status,
            payload,
            attempt,
            max_attempts,
            available_at,
            correlation_id,
            idempotency_key,
            created_by,
            version,
            id,
            created_at,
            updated_at
        )
        SELECT
            'system.synthetic',
            $1,
            number % 10,
            'PENDING',
            jsonb_build_object(
                'duration_ms', $2::integer,
                'outcome', $3::text,
                'retry_until_attempt', $4::integer
            ),
            0,
            $5,
            clock_timestamp(),
            md5($6 || '-correlation-' || number)::uuid,
            $6 || '-' || number,
            'worker-benchmark',
            1,
            md5($6 || '-job-' || number)::uuid,
            clock_timestamp(),
            clock_timestamp()
        FROM generate_series(1, $7) AS series(number)
        """,
        queue,
        scenario.duration_ms,
        scenario.outcome,
        scenario.retry_until_attempt,
        scenario.max_attempts,
        f"{queue}-{scenario.name}",
        scenario.jobs,
    )


async def run_scenario(
    connection: asyncpg.Connection,
    scenario: Scenario,
    queue: str,
) -> dict[str, Any]:
    await seed(connection, scenario, queue)
    started = time.perf_counter()
    peak_connections = 0
    while True:
        terminal = int(
            await connection.fetchval(
                """
                SELECT count(*)
                FROM jobs
                WHERE queue = $1
                  AND status = ANY($2::varchar[])
                """,
                queue,
                list(TERMINAL_STATUSES),
            )
        )
        connections = int(
            await connection.fetchval(
                """
                SELECT count(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
                """
            )
        )
        peak_connections = max(peak_connections, connections)
        if terminal == scenario.jobs:
            break
        if time.perf_counter() - started > 120:
            states = await connection.fetch(
                """
                SELECT status, count(*) AS count
                FROM jobs
                WHERE queue = $1
                GROUP BY status
                """,
                queue,
            )
            raise TimeoutError(f"{scenario.name} did not drain: {states}")
        await asyncio.sleep(0.02)
    drain_seconds = time.perf_counter() - started

    rows = await connection.fetch(
        """
        SELECT
            extract(epoch FROM (started_at - created_at)) * 1000
                AS queue_to_start_ms,
            extract(epoch FROM (finished_at - started_at)) * 1000
                AS total_execution_ms,
            status,
            attempt
        FROM jobs
        WHERE queue = $1
        ORDER BY id
        """,
        queue,
    )
    attempts = await connection.fetch(
        """
        SELECT
            extract(
                epoch FROM (
                    attempt.started_at
                    - CASE
                        WHEN attempt.attempt_number = 1
                            THEN job.created_at
                        ELSE job.available_at
                      END
                )
            ) * 1000 AS eligible_to_attempt_start_ms,
            extract(
                epoch FROM (attempt.finished_at - attempt.started_at)
            ) * 1000 AS execution_ms,
            attempt.status,
            attempt.error_code
        FROM job_attempts AS attempt
        JOIN jobs AS job ON job.id = attempt.job_id
        WHERE job.queue = $1
        ORDER BY attempt.job_id, attempt.attempt_number
        """,
        queue,
    )
    duplicate_attempts = int(
        await connection.fetchval(
            """
            SELECT count(*)
            FROM (
                SELECT job_id, attempt_number
                FROM job_attempts
                GROUP BY job_id, attempt_number
                HAVING count(*) > 1
            ) AS duplicates
            """
        )
    )
    queue_latencies = [float(row["queue_to_start_ms"]) for row in rows]
    total_durations = [float(row["total_execution_ms"]) for row in rows]
    eligible_to_attempt_start_latencies = [
        float(row["eligible_to_attempt_start_ms"])
        for row in attempts
        if row["eligible_to_attempt_start_ms"] is not None
    ]
    attempt_durations = [
        float(row["execution_ms"])
        for row in attempts
        if row["execution_ms"] is not None
    ]
    lease_losses = sum(
        row["error_code"] in {"STALE_LOCK", "JobLeaseLostError"} for row in attempts
    )
    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    retries = sum(max(int(row["attempt"]) - 1, 0) for row in rows)
    return {
        "jobs": scenario.jobs,
        "jobs_per_second": scenario.jobs / drain_seconds,
        "queue_drain_seconds": drain_seconds,
        "queue_to_start_ms": distribution(queue_latencies),
        "eligible_to_attempt_start_ms": distribution(
            eligible_to_attempt_start_latencies
        ),
        "job_execution_ms": distribution(total_durations),
        "attempt_execution_ms": distribution(attempt_durations),
        "peak_database_connections": peak_connections,
        "retries": retries,
        "lease_losses": lease_losses,
        "duplicate_finalization_attempts": duplicate_attempts,
        "statuses": statuses,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--queue", required=True)
    arguments = parser.parse_args()

    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://",
        "postgresql://",
    )
    connection = await asyncpg.connect(database_url)
    try:
        results = {
            "workers": arguments.workers,
            "queue": arguments.queue,
            "scenarios": {},
        }
        for scenario in SCENARIOS:
            results["scenarios"][scenario.name] = await run_scenario(
                connection,
                scenario,
                arguments.queue,
            )
        print(json.dumps(results, indent=2, sort_keys=True))
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
