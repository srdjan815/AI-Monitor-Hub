# Performance budgets

## Reference environment

Measurements use the local Docker Compose API and PostgreSQL deployment. The
completed safe reference dataset reached:

- 100,000 Products;
- 10,023 Attribute Definitions;
- 50,000 Product Attribute Values;
- 100,000 Inventory rows;
- 100,000 Execution Jobs;
- 500 Product Content rows;
- 20 languages;
- 100 warehouses.

The disposable benchmark database was removed after measurement. Medium and
million-row datasets were not executed in the available environment; no
large-scale number below is presented as measured.

## Interactive endpoint budgets

| Path/workload | Reference rows | Measured baseline avg / p95 | Baseline payload | Final budget | Query budget |
|---|---:|---:|---:|---:|---:|
| Product list, 500 | 1,000 | 9.57 / 45.27 ms | 168 KB | p95 < 100 ms, < 1 MB | 2 |
| Product detail | 1,000 | not isolated | one row | p95 < 50 ms, < 100 KB | 2 |
| Attribute definition page | 10,023 | 40.29 / 135.59 ms at 1,000 legacy rows | 450 KB | p95 < 150 ms, < 1 MB | 2 |
| Resolved attributes, first ordinary page (100 rows) | 10,023 | 27.07 / 35.96 ms | 154,066 bytes | avg < 100 ms, p95 < 200 ms, < 1 MB | 8 |
| Resolved attributes, middle ordinary page (100 rows) | 10,023 | 31.55 / 32.16 ms | 196,530 bytes | avg < 100 ms, p95 < 200 ms, < 1 MB | 7 |
| Resolved attributes, final ordinary page | 10,023 | 13.94 / 14.33 ms | 45,335 bytes | avg < 100 ms, p95 < 200 ms, < 1 MB | 7 |
| Product Content search, 100 | 500 | 18.28 / 181.97 ms | 97 KB | p95 < 250 ms, < 1 MB | bounded |
| Inventory list, 100 | 100,000 | 4.30 / 19.99 ms | 37 KB | p95 < 75 ms, < 1 MB | 2 |
| Availability lookup | 100,000 | not isolated | one row | p95 < 50 ms | 2 |
| Reservation | 100,000 | concurrency proof separate | one row | p95 < 150 ms | bounded lock query |
| Fulfillment | 100,000 | not isolated | one row | p95 < 200 ms | bounded transaction |
| Job list, 100 | 100,000 | 26.86 / 33.91 ms | 55 KB | p95 < 100 ms, < 1 MB | 2 |
| Job enqueue | 100,000 | not isolated | one row | p95 < 100 ms | idempotency lookup + insert |
| Job claim | 100,000 | 0.018 ms execution with `ix_jobs_claim_v3` | n/a | p95 < 50 ms | one fenced claim |
| Heartbeat | one leased job | not isolated | n/a | p95 < 25 ms | one conditional update |
| Inventory cursor at depth 99,000 | 100,000 | keyset 2.22 / 2.28 ms; offset 7.19 / 7.61 ms | 35,987 bytes | cursor p95 < 50 ms and depth-independent | 2 |
| Job cursor at depth 99,000 | 100,000 | keyset 2.29 / 2.43 ms; offset 6.84 / 7.50 ms | 60,828 bytes | cursor p95 < 50 ms and depth-independent | 2 |
| Product cursor at depth 99,000 | 100,000 | keyset 2.36 / 2.49 ms; offset 7.74 / 8.70 ms | 38,090 bytes | cursor p95 < 50 ms and depth-independent | 2 |
| Movement cursor at depth 99,000 | 100,000 | keyset 3.56 / 3.68 ms; offset 7.58 / 7.87 ms | 59,288 bytes | cursor p95 < 50 ms and depth-independent | 2 |
| Reservation cursor at depth 99,000 | 100,000 | keyset 2.43 / 2.54 ms; offset 8.43 / 8.74 ms | 54,988 bytes | cursor p95 < 50 ms and depth-independent | 2 |
| Export creation/stream start | 10,023 definitions | first byte 87.22 ms; complete 2,224.11 ms | 17,568,564-byte NDJSON export | first byte < 500 ms | streaming |

Worker timing names are deliberately distinct:

- SQL claim query latency is the isolated database statement execution time;
- transaction claim latency includes the claim transaction and round trips;
- polling interval delay is time waiting for the next poll;
- queue-to-worker-start is creation-to-handler-start wall time;
- handler execution latency is handler start-to-finish time;
- total job completion latency is creation-to-terminal-state wall time.

The benchmark field `eligible_to_attempt_start_ms` includes polling,
scheduling, queueing, claim-transaction, and worker availability delay. It must
not be presented as the indexed SQL claim query latency.

The resolved-attribute implementation is bounded and has a payload regression
assertion below 1 MB. The final warmed benchmark used all 10,023 definitions and
measured first, middle, and final ordinary pages, scoped filters,
`include_unset` modes, and the streaming export. Ordinary pages stayed below
200 KB and below 36 ms p95. Complete cursor traversals returned all 100,000
Jobs, Inventory rows, movements, reservations, and Products without duplicates
or skipped rows; resolved attributes returned all 10,023 rows in 101 pages.

## Regression policy

CI smoke thresholds may allow 50% variance above a stable local median to avoid
host noise, but they must fail a 2x regression or a response-boundary breach.
Release benchmarks use warmed connections, at least 20 samples, and report avg,
p95, p99, payload bytes, query count, and dataset size.

Indexes require `EXPLAIN (ANALYZE, BUFFERS)` before and after. An index is not
added solely from ORM inspection. The final claim comparison proved that the
old, direction-corrected v2, and status-leading alternatives still scanned and
sorted 100,000 candidates. The partial v3 index scanned one row with no sort or
temporary I/O.

## Reproduction commands

Run the repository benchmark scripts inside the API image against a disposable
database at Alembic head:

```text
python scripts/benchmark_resolved_attributes.py
python scripts/benchmark_cursor_pagination.py
python scripts/benchmark_worker_throughput.py
```

The disposable database must be seeded with
`scripts/seed_final_benchmark.sql`. Never run that seed against a valuable
database.
