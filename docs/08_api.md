# API contract

The authoritative API contract is generated from FastAPI:

- [audits/openapi-normalized.json](audits/openapi-normalized.json);
- [audits/api-operation-matrix.json](audits/api-operation-matrix.json);
- [security/api-authorization-matrix.md](security/api-authorization-matrix.md).

Regenerate these artifacts with
`python backend/scripts/generate_contract_reports.py` after a public schema or
route change.
