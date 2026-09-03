# Post-freeze pre-Git checkpoint

Captured: `2026-07-24T15:19:25.4105748+02:00`
Branch: `feature/product-core`
Repository: `<repository-root>`

This checkpoint was completed before the post-freeze hygiene sprint changed any
repository file.

## Recovery checkpoint

The complete working tree was archived outside the repository at:

```text
%TEMP%\
  AI-Monitor-Hub-post-freeze-20260724T151925\
  AI-Monitor-Hub-working-tree.zip
```

Archive verification:

| Check | Result |
|---|---|
| Size | 554,113 bytes |
| SHA-256 | `248145BA20BA246A114F5C936FEF24FB2C5C2D98D193162E567449690BA8C7BE` |
| Readable archive entries | 312 |
| Forbidden `.git`/`.venv`/cache/coverage/`.env` entries | 0 |
| Extracted `backend/requirements.lock` SHA-256 | `478D1C33931E44CB61053C9BA9B7B7B99A650706C8BA8574FD305B07825490DE` |
| Extracted lock matches working tree | yes |

The archive deliberately excludes `.git`, `.venv`, `.env`, bytecode, tool
caches, coverage output, logs, and disposable outputs. It contains all
Git-visible source, migrations, tests, scripts, configuration, generated
contract artifacts, and documentation needed to recover the pre-hygiene
working tree.

The checkpoint directory also contains:

| File | Purpose | SHA-256 |
|---|---|---|
| `checkpoint-metadata.txt` | Key state and artifact identifiers | `EA90FD41CD6AED54E60A24FE4B03E0DAACB1EF1254BA5E9CF94BC425AC1B15AB` |
| `git-status-short.txt` | Expanded short status | `A6294738765F986615D7C93132CEA3DF9DAA80CDB951FA30D3C1FE57D48D1B2C` |
| `git-status-porcelain-v2.txt` | Complete porcelain-v2 status | `39956955BB65C180572B33AB6B28382ED8BB22E48C015C5F7718C305597BD10C` |
| `tracked-modified-files.txt` | Tracked modifications | `A6907B594C4082D08CCEE770E9086397E0BEB535067DBF6E4881032D1D63240D` |
| `untracked-files.txt` | Complete untracked inventory | `38031434E8018EEF90F89DB3BD7B23B7B80B6DF5A7D1246982B03C77C628A37D` |
| `staged-files.txt` | Staged inventory (empty) | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |
| `ignored-files.txt` | Complete ignored inventory | `E79AF238C4979DB829AD369B281265FD568CCB2ACCE9303BA36F3B01A04B8E59` |
| `migration-pairs.txt` | Revision/down-revision pairs | `513321609E480858C97DE047AE75C5FCD42292B5782241DDB88602DE5500097C` |
| `sha256-manifest.csv` | SHA-256 for every Git-visible file | `48185A9ACD9A61BF8B10B53107417CA786962D533E6E3F24ECBBC13708C0EDDA` |

The hash manifest contains exactly 285 files and is sufficient to compare any
recovered copy path-by-path.

## Git state

| Item | Count |
|---|---:|
| `git status --short --untracked-files=all` entries | 236 |
| `git status --porcelain=v2 --untracked-files=all` entries | 236 |
| Tracked modified files | 47 |
| Untracked files | 189 |
| Staged files | 0 |
| Deleted/renamed/conflicted files | 0 |
| Ignored files reported by Git | 875 |
| Modified tracked Alembic revision files | 0 |

Ignored-file composition:

| Root | Count |
|---|---:|
| `.venv` | 872 |
| `.ruff_cache` | 2 |
| `.env` | 1 |

The full path-level inventories are the checkpoint sidecar files listed above.

## Migration graph

The pre-change graph is one 20-revision chain:

| Revision | Down revision | Filename |
|---|---|---|
| `cea65f170298` | `None` | `cea65f170298_initial_database_schema.py` |
| `8b2f4d1c6a10` | `cea65f170298` | `8b2f4d1c6a10_execution_core.py` |
| `d4a9c8e7f621` | `8b2f4d1c6a10` | `d4a9c8e7f621_product_core_foundation.py` |
| `eb5f2829e72e` | `d4a9c8e7f621` | `eb5f2829e72e_add_products_table.py` |
| `f1a2b3c4d5e6` | `eb5f2829e72e` | `f1a2b3c4d5e6_inventory_foundation.py` |
| `b2c3d4e5f6a7` | `f1a2b3c4d5e6` | `b2c3d4e5f6a7_inventory_movements.py` |
| `c3d4e5f6a7b8` | `b2c3d4e5f6a7` | `c3d4e5f6a7b8_inventory_reservations.py` |
| `d5e6f7a8b9c0` | `c3d4e5f6a7b8` | `d5e6f7a8b9c0_product_attribute_system.py` |
| `e6f7a8b9c0d1` | `d5e6f7a8b9c0` | `e6f7a8b9c0d1_attribute_platform_completion.py` |
| `f7a8b9c0d1e2` | `e6f7a8b9c0d1` | `f7a8b9c0d1e2_product_content_platform.py` |
| `a8b9c0d1e2f3` | `f7a8b9c0d1e2` | `a8b9c0d1e2f3_product_content_completion.py` |
| `b9c0d1e2f3a4` | `a8b9c0d1e2f3` | `b9c0d1e2f3a4_content_template_conditions.py` |
| `c0d1e2f3a4b5` | `b9c0d1e2f3a4` | `c0d1e2f3a4b5_product_content_quality.py` |
| `d1e2f3a4b5c6` | `c0d1e2f3a4b5` | `d1e2f3a4b5c6_product_content_invariants.py` |
| `e2f3a4b5c6d7` | `d1e2f3a4b5c6` | `e2f3a4b5c6d7_execution_job_leases.py` |
| `f3a4b5c6d7e8` | `e2f3a4b5c6d7` | `f3a4b5c6d7e8_execution_job_query_indexes.py` |
| `f4a5b6c7d8e9` | `f3a4b5c6d7e8` | `f4a5b6c7d8e9_fix_execution_claim_priority_index.py` |
| `a5b6c7d8e9f0` | `f4a5b6c7d8e9` | `a5b6c7d8e9f0_normalize_attribute_check_constraint_names.py` |
| `b6c7d8e9f0a1` | `a5b6c7d8e9f0` | `b6c7d8e9f0a1_optimize_execution_claim_index.py` |
| `c7d8e9f0a1b2` | `b6c7d8e9f0a1` | `c7d8e9f0a1b2_add_cursor_pagination_indexes.py` |

Runtime state:

- `alembic heads`: `c7d8e9f0a1b2`;
- `alembic branches`: none;
- `alembic current`: `c7d8e9f0a1b2 (head)`;
- `alembic check`: no new upgrade operations.

## Runtime and contract identity

| Artifact | Identity |
|---|---|
| API image | `sha256:c47d0e84efc41961fc98d0ea11856d04fa1ac9269c8d978053f1678517a37590` |
| Worker image | `sha256:fffd90b8d5c2db7c62f4d2f472cedcf76b80b3924a7d1cfb69af865f4412ec79` |
| OpenAPI snapshot SHA-256 | `CE6958860A0B6889D031696104D89C185543871679173AFB0CD636C58F102AD2` |
| Requirements lock SHA-256 | `478D1C33931E44CB61053C9BA9B7B7B99A650706C8BA8574FD305B07825490DE` |

At capture time the API, PostgreSQL, Redis, and two worker containers were
running; API/PostgreSQL/Redis health checks passed.

## Recovery procedure

1. Copy the checkpoint directory to durable storage if retention beyond the
   operating-system temporary-file policy is required.
2. Verify the ZIP and manifest SHA-256 values above.
3. Extract the ZIP into a new empty directory.
4. Initialize or attach the intended Git metadata separately; `.git` is
   intentionally absent.
5. Compare extracted files with `sha256-manifest.csv`.
6. Restore machine-specific `.env` separately from an approved secret source.

The archive was listed successfully, the locked requirements file was read
directly from it, and the extracted lock hash matched the working-tree hash.
Recovery is therefore verified before Git cleanup or staging begins.
