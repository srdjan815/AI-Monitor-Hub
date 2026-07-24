# Dependency Management

## Sources of truth

`backend/pyproject.toml` declares supported Python and dependency ranges.
`backend/requirements.lock` is the complete, exact environment tested on
Windows and Linux. Both must change together when a declared dependency changes.

One combined lock is intentional for the Foundation baseline. It contains:

- application runtime and build dependencies;
- development and test tools;
- typing stubs and MyPy;
- Ruff and Black;
- coverage, randomization, and parallel-test tools;
- `pip-audit` and its transitive advisory/SBOM dependencies.

The combined environment lets the same checked image execute every release
gate. It is broader than a minimal production-only environment; splitting it
requires a separate reviewed runtime lock and parity proof, not silent package
removal.

## Exact installation

Use Python 3.12.x and the reviewed pip version:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==26.1.2
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e backend
.\.venv\Scripts\python.exe -m pip check
```

The exact `setuptools` and `wheel` build requirements are present in both
`pyproject.toml` and the lock. `--no-build-isolation --no-deps` prevents editable
registration from resolving an uncontrolled second graph.

Docker uses the same sequence from a digest-pinned Python 3.12 image. PostgreSQL
and Redis Compose images are also version-and-digest pinned. The Dockerfiles and
Compose files, rather than copied values in prose, are the canonical image
identities.

## Platform markers

Only supported platform differences belong in the combined lock:

| Package | Marker | Reason |
|---|---|---|
| `colorama` | `sys_platform == "win32"` | Windows terminal support pulled by developer tooling |
| `uvloop` | `sys_platform != "win32"` | Uvicorn's optimized POSIX event loop; unsupported on Windows |

All platform-independent application packages must resolve to the same versions
on Windows and Linux. A parity report may omit `colorama` and `uvloop` only for
the stated marker reasons.

## Controlled lock update

Change a dependency only for a confirmed vulnerability, compatibility problem,
installation failure, or critical defect:

1. Create clean Python 3.12 Windows and digest-pinned Linux environments.
2. Update the applicable range in `pyproject.toml`.
3. Resolve the complete dependency graph independently on both platforms.
4. Merge only proven platform differences and attach explicit PEP 508 markers.
5. Pin every package, including transitive and build packages, exactly once.
6. Install the resulting lock from scratch on both platforms.
7. Compare normalized package/version inventories.
8. Record package category, direct/transitive status, marker, license, and
   advisory status.
9. Compute the lock hash:

   ```powershell
   (Get-FileHash -Algorithm SHA256 backend\requirements.lock).Hash
   ```

10. Rebuild without cache and run every mandatory static, test, migration,
    contract, and recovery gate.

Do not generate the combined cross-platform lock from `pip freeze` on only one
operating system; that would omit the other platform's marked package.

## Security and license gates

Run the advisory scanner on the host and in the rebuilt Linux image:

```powershell
.\.venv\Scripts\python.exe -m pip_audit -r backend\requirements.lock
docker compose run --rm api python -m pip_audit -r requirements.lock
```

For every advisory, record applicability, reachability, direct/transitive
status, severity, fixed version, and the smallest compatible correction. Do not
suppress a finding without a documented risk acceptance. The current evidence
belongs in `docs/security/dependency-advisory-report.md`.

License inventory must be generated from both installed environments and mapped
back to every lock entry. An unknown or incompatible license is a release review
item even when `pip check` passes.

After any dependency edit, rerun at minimum:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
Set-Location backend
..\.venv\Scripts\python.exe -m mypy app
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m alembic check
Set-Location ..
```
