# AI Monitor Hub backend

The canonical project and development guides live at:

- [`../README.md`](../README.md)
- [`../docs/operations/developer-onboarding.md`](../docs/operations/developer-onboarding.md)
- [`../docs/operations/cross-platform-python-environment.md`](../docs/operations/cross-platform-python-environment.md)

`pyproject.toml` declares supported dependency ranges and project metadata.
`requirements.lock` is the complete exact environment validated on Windows and
Linux. Install the lock first, then register the local package with
`--no-build-isolation --no-deps`; do not let an editable install resolve a
second dependency graph.

Run host tooling through the repository-root `.venv`, or run the authoritative
database-backed gates from `/app` inside the Docker API container. Dependency
policy is documented in
[`../docs/operations/dependency-management.md`](../docs/operations/dependency-management.md).
