from __future__ import annotations

import hashlib
import json

from app.main import app

EXPECTED_PATHS = 62
EXPECTED_SCHEMAS = 36
EXPECTED_SHA256 = "b9e3cbd3f9fcaa4e2f59716b2fcf39121f36fe158d413b438def4f41e537b0b2"


def test_product_content_openapi_contract_snapshot() -> None:
    schema = app.openapi()
    contract = {
        "paths": {
            path: value
            for path, value in schema["paths"].items()
            if path.startswith("/api/v1/content")
        },
        "schemas": {
            name: value
            for name, value in schema["components"]["schemas"].items()
            if any(
                marker in name
                for marker in (
                    "Content",
                    "Language",
                    "SEO",
                    "Landing",
                    "Reference",
                    "Library",
                    "Template",
                    "Prompt",
                    "Scoring",
                    "Workflow",
                    "Preview",
                    "Rollback",
                    "LinkCheck",
                )
            )
        },
        "security_schemes": schema["components"].get("securitySchemes", {}),
    }
    serialized = json.dumps(
        contract,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert len(contract["paths"]) == EXPECTED_PATHS
    assert len(contract["schemas"]) == EXPECTED_SCHEMAS
    assert hashlib.sha256(serialized).hexdigest() == EXPECTED_SHA256
