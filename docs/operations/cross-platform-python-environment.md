# Cross-platform Python environment

## Supported versions

AI Monitor Hub supports CPython `>=3.12,<3.13` on native Windows and Linux
containers; PyPy and Cygwin are outside the supported matrix. The verified
native Windows interpreter is Python 3.12.10. The Linux container uses the
exact Python 3.12
patch release and image digest declared by `backend/Dockerfile`; do not replace
that reference with a floating `python:3.12` tag.

Pip is pinned to 26.1.2. `backend/requirements.lock` is the one exact
cross-platform dependency set. `backend/pyproject.toml` declares compatible
ranges but is not a replacement for the lock.

## Native Windows setup

Run PowerShell 5.1 from the repository root. Prefer `python.exe` from `PATH`;
the fallback below uses the normal per-user Python.org installation without
embedding a username:

```powershell
$PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($null -ne $PythonCommand) {
    $Python312 = $PythonCommand.Source
} else {
    $Python312 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
}

if (-not (Test-Path -LiteralPath $Python312)) {
    throw "Install Python 3.12.x from python.org and reopen PowerShell."
}

& $Python312 --version
& $Python312 -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==26.1.2
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e backend
.\.venv\Scripts\python.exe -m pip check
```

Confirm that the first command reports Python 3.12.x. Do not reuse a `.venv`
whose `pyvenv.cfg` points to a removed interpreter.

## Native validation

The native environment supports imports, static tools, mapper configuration,
and database-free tests:

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
.\.venv\Scripts\python.exe -c "import app.api.router; from sqlalchemy.orm import configure_mappers; configure_mappers(); print('mappers configured')"
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
Set-Location backend
..\.venv\Scripts\python.exe -m mypy app
..\.venv\Scripts\python.exe -m pytest tests\test_health.py tests\test_module_boundaries.py
Set-Location ..
```

The standard `.env` uses the Compose DNS name `db`. That name does not resolve
from Windows, and PostgreSQL is not published to a host port by the canonical
Compose file. Run the complete database-backed suite in Docker rather than
rewriting local connection settings.

## Docker and Linux setup

The default Compose stack is the authoritative application runtime:

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose build --no-cache api worker
docker compose up -d
docker compose ps
docker compose exec -T api python --version
docker compose exec -T api python -m pip check
docker compose exec -T api python -c "import uvloop; print(uvloop.__version__)"
docker compose exec -T api python -c "from app.main import app; print(app.title)"
docker compose exec -T api python -c "import app.api.router; from sqlalchemy.orm import configure_mappers; configure_mappers(); print('mappers configured')"
```

Uvicorn runs in its default automatic loop-selection mode. On supported Linux
images it can import and select `uvloop`; on Windows it falls back to the native
asyncio loop.

## Why `uvloop` is conditional

`uvloop` does not support Windows. The lock therefore contains:

```text
uvloop==0.22.1; sys_platform != "win32"
```

Windows developer tooling may install `colorama` under the inverse platform
marker. These two intentional marker differences must not conceal drift in
FastAPI, SQLAlchemy, Pydantic, Redis, security, or other application packages.
Compare normalized `python -m pip freeze` results from both environments and
exclude only these reviewed marker differences.

## VS Code

Open the repository root, install the recommended workspace extensions, and
select:

```text
${workspaceFolder}\.venv\Scripts\python.exe
```

Shared settings configure the backend analysis path, pytest working directory,
Ruff, MyPy, formatting, and terminal root. They contain no user-specific
absolute path. The Docker workflow remains authoritative for PostgreSQL-backed
tests.

## Troubleshooting

- If Python is missing, install a Python.org 3.12.x per-user build and reopen
  PowerShell.
- If the venv launcher reports a missing base executable, preserve any needed
  evidence, remove only the verified `.venv` directory, and recreate it with
  the current interpreter.
- If imports resolve outside `.venv`, run them explicitly through
  `.\.venv\Scripts\python.exe`.
- If `db` cannot resolve on Windows, use Docker; do not change the committed
  Compose database hostname.
- If Docker still exposes old code or dependencies, rebuild the pinned image
  without cache and recreate the affected service.
- If `uvloop` attempts to install on Windows, verify the exact PEP 508 marker in
  `backend/requirements.lock` and ensure pip is 26.1.2.
