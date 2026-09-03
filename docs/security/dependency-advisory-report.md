# Python dependency advisory report

## Reviewed baseline

The reviewed dependency source is `backend/requirements.lock`, containing 81
nonblank, exactly pinned entries. Its SHA-256 digest is:

```text
0161C9551DE7DE95DA01DFC5B2A606FF44A6AA6020A274A3644BFF7EE1D99141
```

`backend/pyproject.toml` declares the supported dependency ranges and direct
dependencies. The lock is the complete cross-platform installation set,
including runtime, build, development, test, typing, formatting, and security
tools. The package-by-package classification and license review is recorded in
`docs/operations/python-dependency-inventory.csv`.

The only intentional platform differences are:

- `colorama==0.4.6` on Windows;
- `uvloop==0.22.1` on non-Windows platforms.

All 81 lock entries have an identified permissive or weak-copyleft
OSI-compatible license. The review found no unknown, incompatible, or GPL
license. MPL-2.0 applies only to `certifi` and `pathspec`; it does not impose a
copyleft requirement on unrelated repository files.

## Current host advisory evidence

The following scans were executed on 2026-07-24 in the verified native Windows
environment using Python 3.12.10, pip 26.1.2, and `pip-audit` 2.10.1. The
scanner used its default PyPI vulnerability service.

| Command scope | Result |
|---|---|
| `python -m pip_audit -r backend/requirements.lock` | PASS — zero known vulnerabilities |
| `python -m pip_audit --local --skip-editable` | PASS — zero known vulnerabilities |
| `python -m pip check` | PASS — no broken requirements |

No vulnerability was ignored, suppressed, or accepted. The requirements scan
evaluates the complete cross-platform lock; the local scan independently checks
the installed Windows environment and intentionally skips only the editable
application package itself.

## Remediated findings observed during this sprint

| Package | Advisory | Exposure and reachability | Resolution |
|---|---|---|---|
| cryptography 46.0.7 | PYSEC-2026-3552, PYSEC-2026-3553, PYSEC-2026-3554 and GHSA-537c-gmf6-5ccf | Direct runtime dependency used for supplier PKCS#12 parsing, certificate validation and mTLS. Because this path is reachable while acquiring supplier data, release remained blocked until the complete fixed version was verified. | Upgraded to `cryptography==50.0.0` and constrained the supported range to `>=50.0.0,<51.0.0`. A clean Linux image reports zero known vulnerabilities; all 76 targeted certificate/acquisition unit tests and 278 isolated supplier tests pass. |
| Black 24.10.0 | CVE-2026-31900 / PYSEC-2026-2120 | Direct development/formatting dependency. The affected GitHub Action path is not part of the application request runtime and no Black Action execution path was identified in the reviewed repository, but retaining a vulnerable developer tool was not acceptable. | Upgraded to `black==26.3.1`; fixed from 26.3.0. |
| Black 24.10.0 | CVE-2026-32274 / PYSEC-2026-2121 | Direct development/formatting dependency. Black is invoked by developer and release checks, so the affected arbitrary cache-path behavior was potentially reachable in tooling even though it was outside the production API path. | Upgraded to `black==26.3.1`; fixed in 26.3.1. |
| pytest 8.4.2 | CVE-2025-71176 / PYSEC-2026-1845 | Direct test dependency. The predictable Unix temporary-path issue could affect Linux test execution through local denial of service and, under adverse local privilege conditions, broader impact. It was not reachable from a production HTTP request. | Upgraded to `pytest==9.0.3`, the first reviewed fixed target used by this lock. |

The pytest major-version correction also required upgrading
`pytest-asyncio` from 0.26.0 to `pytest-asyncio==1.3.0`, the reviewed compatible
release used with pytest 9. The resulting host environment passes dependency
resolution and the two advisory scans above.

## Container and release status

An additional controlled review on 2026-09-03 rebuilt the Linux images with
`cryptography==50.0.0`. `pip-audit` and `pip check` passed, and the supplier
regression ran against disposable PostgreSQL and Redis services which were
verified removed afterward. The image build did not restart the active
development services.

| Evidence | Status |
|---|---|
| Clean, no-cache Linux image rebuild from the final Dockerfile and lock | **PASS** — API `86056abbc018`, worker `54182b02d62e`, 2026-07-24 |
| `python -m pip check` in the rebuilt API image | **PASS** — no broken requirements |
| `python -m pip_audit -r requirements.lock` in the rebuilt API image | **PASS** — zero known vulnerabilities |
| Normalized Windows/Linux version parity, excluding only the two reviewed markers | **PASS** — 82 installed packages on each platform and zero version differences after excluding `uvloop` and `colorama` |

The authoritative Linux runtime uses Python 3.12.13 and pip 26.1.2. It imports
`uvloop==0.22.1`, `regex==2026.7.19`, and `redis==6.4.0`; mapper configuration
loads all 46 tables. Windows uses Python 3.12.10 and intentionally omits
`uvloop`. Linux intentionally omits Windows-only `colorama`.

## Release rule

A new dependency advisory blocks release unless it is fixed or accompanied by a
documented, approved risk acceptance containing applicability, reachability,
severity, compensating controls, owner, and expiry. An unknown or incompatible
license likewise blocks release review. Re-run both requirements and installed
environment scans whenever the lock changes, then repeat them inside the clean
Linux image.
