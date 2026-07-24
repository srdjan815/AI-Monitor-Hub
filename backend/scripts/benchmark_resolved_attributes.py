from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
import tracemalloc
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.modules.catalog.attribute_query_service import AttributeQueryService
from app.modules.catalog.models import Product
from app.modules.catalog.schemas.product_attributes import ResolvedAttributePage


SAMPLES = 12
PRODUCT_ID = uuid.UUID("9a35e4a8-f343-ca90-1a77-8eace34bfb89")
FAMILY_ID = uuid.UUID("5c5e23f9-b711-369b-4962-3fc2fd14b5e1")
TEMPLATE_ID = uuid.UUID("41c017a5-a1b4-799e-155e-79134bfbb96f")


def percentile(values: list[float], percentage: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


async def locate_cursor(
    service: AttributeQueryService,
    product: Product,
    *,
    page_number: int,
) -> str | None:
    cursor: str | None = None
    for _ in range(page_number):
        page = await service.resolved_page(
            product.category_id,
            product=product,
            include_unset=True,
            scope=None,
            group_id=None,
            family_id=None,
            template_id=None,
            limit=100,
            cursor=cursor,
        )
        cursor = page.next_cursor
        if cursor is None:
            break
    return cursor


async def measure_page(
    query_counter: dict[str, int],
    loader: Callable[[], Awaitable[ResolvedAttributePage]],
) -> dict[str, Any]:
    durations: list[float] = []
    query_counts: list[int] = []
    payload_bytes = 0
    peak_bytes = 0
    total = 0

    await loader()
    for _ in range(SAMPLES):
        query_counter["count"] = 0
        tracemalloc.start()
        started = time.perf_counter()
        page = await loader()
        payload = page.model_dump_json().encode()
        durations.append((time.perf_counter() - started) * 1000)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        query_counts.append(query_counter["count"])
        payload_bytes = len(payload)
        peak_bytes = max(peak_bytes, peak)
        total = page.total

    return {
        "average_ms": statistics.fmean(durations),
        "p95_ms": percentile(durations, 0.95),
        "p99_ms": percentile(durations, 0.99),
        "payload_bytes": payload_bytes,
        "peak_memory_bytes": peak_bytes,
        "query_count": max(query_counts),
        "total": total,
    }


async def measure_export(
    service: AttributeQueryService,
    product: Product,
    query_counter: dict[str, int],
) -> dict[str, Any]:
    cursor: str | None = None
    rows = 0
    payload_bytes = 0
    first_byte_ms: float | None = None
    query_counter["count"] = 0
    tracemalloc.start()
    started = time.perf_counter()
    while True:
        page = await service.resolved_page(
            product.category_id,
            product=product,
            include_unset=True,
            scope=None,
            group_id=None,
            family_id=None,
            template_id=None,
            limit=500,
            cursor=cursor,
        )
        for item in page.items:
            payload_bytes += len(item.model_dump_json().encode()) + 1
            rows += 1
            if first_byte_ms is None:
                first_byte_ms = (time.perf_counter() - started) * 1000
        cursor = page.next_cursor
        if cursor is None:
            break
    duration_ms = (time.perf_counter() - started) * 1000
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "first_byte_ms": first_byte_ms,
        "complete_ms": duration_ms,
        "rows": rows,
        "payload_bytes": payload_bytes,
        "peak_memory_bytes": peak_bytes,
        "query_count": query_counter["count"],
    }


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, pool_size=5)
    query_counter = {"count": 0}

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def count_query(
        _connection: object,
        _cursor: object,
        _statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        query_counter["count"] += 1

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        product = await session.get(Product, PRODUCT_ID)
        if product is None:
            raise RuntimeError("Benchmark product is missing")
        service = AttributeQueryService(session)
        middle_cursor = await locate_cursor(service, product, page_number=50)
        final_cursor = await locate_cursor(service, product, page_number=100)

        async def page(
            *,
            cursor: str | None = None,
            include_unset: bool = True,
            scope: str | None = None,
            family_id: uuid.UUID | None = None,
            template_id: uuid.UUID | None = None,
        ) -> ResolvedAttributePage:
            return await service.resolved_page(
                product.category_id,
                product=product,
                include_unset=include_unset,
                scope=scope,
                group_id=None,
                family_id=family_id,
                template_id=template_id,
                limit=100,
                cursor=cursor,
            )

        results = {
            "dataset": {
                "definitions": 10_023,
                "product_id": str(product.id),
                "category_id": str(product.category_id),
            },
            "first_page": await measure_page(query_counter, page),
            "middle_page": await measure_page(
                query_counter,
                lambda: page(cursor=middle_cursor),
            ),
            "final_page": await measure_page(
                query_counter,
                lambda: page(cursor=final_cursor),
            ),
            "include_unset_false": await measure_page(
                query_counter,
                lambda: page(include_unset=False),
            ),
            "scope_filter": await measure_page(
                query_counter,
                lambda: page(scope="CATEGORY"),
            ),
            "family_filter": await measure_page(
                query_counter,
                lambda: page(family_id=FAMILY_ID),
            ),
            "template_filter": await measure_page(
                query_counter,
                lambda: page(template_id=TEMPLATE_ID),
            ),
            "export": await measure_export(service, product, query_counter),
        }
        print(json.dumps(results, indent=2, sort_keys=True))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
