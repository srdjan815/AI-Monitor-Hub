from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from dataclasses import dataclass
from typing import Any

import asyncpg


DEPTHS = (0, 1_000, 10_000, 50_000, 99_000)
PAGE_SIZE = 100
SAMPLES = 20


@dataclass(frozen=True, slots=True)
class Domain:
    name: str
    table: str
    order_column: str
    direction: str
    predicate: str

    @property
    def comparator(self) -> str:
        return "<" if self.direction == "DESC" else ">"

    @property
    def order(self) -> str:
        return f"{self.order_column} {self.direction}, id {self.direction}"


DOMAINS = (
    Domain("jobs", "jobs", "created_at", "DESC", "TRUE"),
    Domain("inventory", "inventory", "created_at", "DESC", "is_active"),
    Domain(
        "movements",
        "inventory_movements",
        "occurred_at",
        "DESC",
        "TRUE",
    ),
    Domain(
        "reservations",
        "inventory_reservations",
        "created_at",
        "DESC",
        "status IN ('ACTIVE', 'PARTIALLY_FULFILLED')",
    ),
    Domain("products", "products", "created_at", "DESC", "is_active"),
    Domain(
        "resolved_attributes",
        "attribute_definitions",
        "created_at",
        "ASC",
        "is_active",
    ),
)


def percentile(values: list[float], percentage: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def scan_plan(plan: dict[str, Any]) -> tuple[int, set[str], set[str]]:
    rows_scanned = 0
    indexes: set[str] = set()
    sorts: set[str] = set()

    def visit(node: dict[str, Any]) -> None:
        nonlocal rows_scanned
        node_type = str(node.get("Node Type", ""))
        if "Scan" in node_type and not node.get("Plans"):
            rows = int(node.get("Actual Rows", 0))
            removed = int(node.get("Rows Removed by Filter", 0))
            loops = int(node.get("Actual Loops", 1))
            rows_scanned += (rows + removed) * loops
        if index_name := node.get("Index Name"):
            indexes.add(str(index_name))
        if "Sort" in node_type:
            method = node.get("Sort Method", node_type)
            sorts.add(str(method))
        for child in node.get("Plans", []):
            visit(child)

    visit(plan)
    return rows_scanned, indexes, sorts


async def boundary(
    connection: asyncpg.Connection,
    domain: Domain,
    depth: int,
) -> asyncpg.Record | None:
    if depth == 0:
        return None
    return await connection.fetchrow(
        f"""
        SELECT {domain.order_column}, id
        FROM {domain.table}
        WHERE {domain.predicate}
        ORDER BY {domain.order}
        OFFSET $1
        LIMIT 1
        """,
        depth - 1,
    )


def page_sql(
    domain: Domain,
    *,
    keyset: bool,
    explain: bool = False,
) -> str:
    continuation = ""
    if keyset:
        continuation = f"AND ({domain.order_column}, id) {domain.comparator} ($1, $2)"
    prefix = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " if explain else ""
    return (
        f"{prefix}SELECT * FROM {domain.table} "
        f"WHERE {domain.predicate} {continuation} "
        f"ORDER BY {domain.order} "
        f"{'LIMIT 100' if keyset else 'OFFSET $1 LIMIT 100'}"
    )


async def fetch_page(
    connection: asyncpg.Connection,
    domain: Domain,
    *,
    depth: int,
    position: asyncpg.Record | None,
) -> tuple[list[asyncpg.Record], list[asyncpg.Record]]:
    offset_rows = await connection.fetch(page_sql(domain, keyset=False), depth)
    if position is None:
        keyset_rows = await connection.fetch(
            (
                f"SELECT * FROM {domain.table} "
                f"WHERE {domain.predicate} "
                f"ORDER BY {domain.order} LIMIT 100"
            )
        )
    else:
        keyset_rows = await connection.fetch(
            page_sql(domain, keyset=True),
            position[domain.order_column],
            position["id"],
        )
    return list(offset_rows), list(keyset_rows)


async def explain_page(
    connection: asyncpg.Connection,
    domain: Domain,
    *,
    depth: int,
    position: asyncpg.Record | None,
    keyset: bool,
) -> dict[str, Any]:
    if keyset and position is None:
        query = (
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
            f"SELECT * FROM {domain.table} "
            f"WHERE {domain.predicate} "
            f"ORDER BY {domain.order} LIMIT 100"
        )
        raw = await connection.fetchval(query)
    elif keyset:
        raw = await connection.fetchval(
            page_sql(domain, keyset=True, explain=True),
            position[domain.order_column],
            position["id"],
        )
    else:
        raw = await connection.fetchval(
            page_sql(domain, keyset=False, explain=True),
            depth,
        )
    document = json.loads(raw) if isinstance(raw, str) else raw
    report = document[0]
    plan = report["Plan"]
    rows_scanned, indexes, sorts = scan_plan(plan)
    return {
        "planning_ms": report["Planning Time"],
        "execution_ms": report["Execution Time"],
        "rows_scanned": rows_scanned,
        "shared_hit_blocks": plan.get("Shared Hit Blocks", 0),
        "shared_read_blocks": plan.get("Shared Read Blocks", 0),
        "temp_read_blocks": plan.get("Temp Read Blocks", 0),
        "temp_written_blocks": plan.get("Temp Written Blocks", 0),
        "indexes": sorted(indexes),
        "sorts": sorted(sorts),
    }


async def benchmark_mode(
    connection: asyncpg.Connection,
    domain: Domain,
    *,
    depth: int,
    position: asyncpg.Record | None,
    keyset: bool,
) -> dict[str, Any]:
    durations: list[float] = []
    payload_bytes = 0
    count_sql = f"SELECT count(*) FROM {domain.table} WHERE {domain.predicate}"
    for sample in range(SAMPLES + 2):
        started = time.perf_counter()
        await connection.fetchval(count_sql)
        if keyset and position is None:
            rows = await connection.fetch(
                (
                    f"SELECT * FROM {domain.table} "
                    f"WHERE {domain.predicate} "
                    f"ORDER BY {domain.order} LIMIT 100"
                )
            )
        elif keyset:
            rows = await connection.fetch(
                page_sql(domain, keyset=True),
                position[domain.order_column],
                position["id"],
            )
        else:
            rows = await connection.fetch(
                page_sql(domain, keyset=False),
                depth,
            )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if sample >= 2:
            durations.append(elapsed_ms)
        payload_bytes = len(
            json.dumps(
                [dict(row) for row in rows],
                default=str,
                separators=(",", ":"),
            ).encode()
        )
    return {
        "average_ms": statistics.fmean(durations),
        "p95_ms": percentile(durations, 0.95),
        "p99_ms": percentile(durations, 0.99),
        "payload_bytes": payload_bytes,
        "query_count": 2,
        "plan": await explain_page(
            connection,
            domain,
            depth=depth,
            position=position,
            keyset=keyset,
        ),
    }


async def verify_full_traversal(
    connection: asyncpg.Connection,
    domain: Domain,
) -> dict[str, Any]:
    expected = int(
        await connection.fetchval(
            f"SELECT count(*) FROM {domain.table} WHERE {domain.predicate}"
        )
    )
    seen: set[Any] = set()
    position: tuple[Any, Any] | None = None
    pages = 0
    while True:
        if position is None:
            rows = await connection.fetch(
                f"""
                SELECT id, {domain.order_column}
                FROM {domain.table}
                WHERE {domain.predicate}
                ORDER BY {domain.order}
                LIMIT {PAGE_SIZE}
                """
            )
        else:
            rows = await connection.fetch(
                f"""
                SELECT id, {domain.order_column}
                FROM {domain.table}
                WHERE {domain.predicate}
                  AND ({domain.order_column}, id)
                      {domain.comparator} ($1, $2)
                ORDER BY {domain.order}
                LIMIT {PAGE_SIZE}
                """,
                position[0],
                position[1],
            )
        if not rows:
            break
        pages += 1
        for row in rows:
            if row["id"] in seen:
                raise RuntimeError(f"Duplicate {domain.name} row {row['id']}")
            seen.add(row["id"])
        last = rows[-1]
        position = (last[domain.order_column], last["id"])
    return {
        "expected_rows": expected,
        "seen_rows": len(seen),
        "pages": pages,
        "duplicates": 0,
        "skipped": expected - len(seen),
    }


async def main() -> None:
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://",
        "postgresql://",
    )
    connection = await asyncpg.connect(database_url)
    results: dict[str, Any] = {}
    try:
        for domain in DOMAINS:
            domain_result: dict[str, Any] = {
                "depths": {},
                "full_traversal": await verify_full_traversal(
                    connection,
                    domain,
                ),
            }
            for depth in DEPTHS:
                available = int(
                    await connection.fetchval(
                        f"""
                        SELECT count(*)
                        FROM {domain.table}
                        WHERE {domain.predicate}
                        """
                    )
                )
                if depth >= available:
                    continue
                position = await boundary(connection, domain, depth)
                offset_rows, keyset_rows = await fetch_page(
                    connection,
                    domain,
                    depth=depth,
                    position=position,
                )
                if [row["id"] for row in offset_rows] != [
                    row["id"] for row in keyset_rows
                ]:
                    raise RuntimeError(
                        f"{domain.name} keyset mismatch at depth {depth}"
                    )
                domain_result["depths"][str(depth)] = {
                    "offset": await benchmark_mode(
                        connection,
                        domain,
                        depth=depth,
                        position=position,
                        keyset=False,
                    ),
                    "keyset": await benchmark_mode(
                        connection,
                        domain,
                        depth=depth,
                        position=position,
                        keyset=True,
                    ),
                    "equivalent_ids": True,
                }
            results[domain.name] = domain_result
        print(json.dumps(results, indent=2, sort_keys=True))
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
