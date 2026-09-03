# Migration Operations

Never edit an applied revision. Add one corrective revision with exactly one
parent and verify a single head. Application models must be imported by
`alembic/env.py` before autogenerate comparison.

Required checks are `alembic heads`, `alembic current`, `alembic check`, and an
empty disposable database upgraded to head. The Foundation's single expected
head is `c7d8e9f0a1b2`. Release evidence must prove traversal from
`cea65f170298` through that head on an empty disposable database.

Downgrade/re-upgrade proof must target only disposable data. Never downgrade a
valuable or unknown database. The exact release result is recorded in
`../audits/post-freeze-repository-release-final-report.md`.
