from __future__ import annotations

import asyncio
import uuid

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.main import app
from app.modules.suppliers.delta_models import SupplierDeltaRun
from tests.test_supplier_delta_integration import _shape
from tests.test_supplier_incident_integration import _cleanup
from tests.test_supplier_snapshot_integration import (
    API_ROOT,
    _csv_payload,
    _headers,
    _pipeline,
)


async def _add_delta_signal(delta_id: str) -> None:
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        delta = await session.get(SupplierDeltaRun, uuid.UUID(delta_id))
        assert delta is not None
        delta.anomaly_signals = [{"code": "HIGH_REMOVAL_RATIO", "ratio": 0.75}]
        await session.commit()
    await engine.dispose()


def test_supplier_api_openapi_contract() -> None:
    schema = app.openapi()
    operation_ids = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    assert len(operation_ids) == len(set(operation_ids))
    assert "/api/v1/suppliers/platform/overview" in schema["paths"]
    assert "/api/v1/suppliers/platform/search" in schema["paths"]
    assert "/api/v1/suppliers/platform/incidents" in schema["paths"]
    assert "/api/v1/suppliers/platform/supplier-incidents" in schema["paths"]
    assert schema["paths"]["/api/v1/supplier-incidents"]["get"]["deprecated"]
    assert not schema["paths"]["/api/v1/suppliers/platform/incidents"]["get"].get(
        "deprecated", False
    )
    supplier_operations = [
        operation
        for path, methods in schema["paths"].items()
        if "supplier" in path
        for operation in methods.values()
        if isinstance(operation, dict) and "summary" in operation
    ]
    assert all(operation["summary"].strip() for operation in supplier_operations)
    canonical_errors = schema["paths"][
        "/api/v1/suppliers/platform/search"
    ]["get"]["responses"]
    assert "SupplierApiErrorResponse" in str(canonical_errors["422"])


def test_supplier_api_error_and_request_identifiers() -> None:
    headers = {**_headers(), "X-Correlation-ID": "chapter-3.9-correlation"}
    with httpx.Client(base_url=API_ROOT, headers=headers, timeout=30) as client:
        invalid = client.get(
            "/suppliers/platform/incidents",
            params={"sort_by": "raw_data"},
        )
        assert invalid.status_code == 422
        payload = invalid.json()
        assert payload["code"] == "VALIDATION_ERROR"
        assert payload["error"]["code"] == "VALIDATION_ERROR"
        assert payload["error"]["field_errors"]
        assert payload["request_id"] == invalid.headers["x-request-id"]
        assert payload["correlation_id"] == "chapter-3.9-correlation"
        assert invalid.headers["x-correlation-id"] == "chapter-3.9-correlation"
        assert "traceback" not in invalid.text.lower()

        replaced = client.get(
            "/suppliers/platform/search",
            params={"query": "SUP"},
            headers={"X-Correlation-ID": "invalid correlation value"},
        )
        assert replaced.status_code == 200
        assert replaced.headers["x-correlation-id"] == replaced.headers["x-request-id"]


def test_supplier_api_end_to_end_scenario() -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id = ""
    correlation_id = f"supplier-api-{suffix}"
    headers = {**_headers(), "X-Correlation-ID": correlation_id}
    with httpx.Client(base_url=API_ROOT, headers=headers, timeout=90) as client:
        try:
            products_before = client.get("/products").json()["total"]
            inventory_before = client.get("/inventory").json()["total"]
            supplier_id, source_id, root = _pipeline(client, suffix)
            supplier = client.get(f"/suppliers/{supplier_id}").json()
            source = client.get(f"/suppliers/{supplier_id}/sources/{source_id}").json()

            snapshots: list[dict[str, object]] = []
            acquisitions: list[dict[str, object]] = []
            for index in range(2):
                acquisition = client.post(
                    f"{root}/acquisitions/upload",
                    params={"filename": f"api-{suffix}-{index}.csv"},
                    headers={"Content-Type": "text/csv"},
                    content=_csv_payload(f"opis-{index}"),
                )
                assert acquisition.status_code == 201, acquisition.text
                acquisitions.append(acquisition.json())
                fetched = client.get(
                    f"{root}/acquisitions/{acquisition.json()['id']}"
                )
                assert fetched.status_code == 200
                snapshot = client.post(
                    f"{root}/snapshots",
                    json={"acquisition_run_id": acquisition.json()["id"]},
                )
                assert snapshot.status_code == 201, snapshot.text
                snapshots.append(snapshot.json())
                summary = client.get(
                    f"{root}/snapshots/{snapshot.json()['id']}/statistics"
                )
                items = client.get(
                    f"{root}/snapshots/{snapshot.json()['id']}/items",
                    params={"limit": 2},
                )
                assert summary.status_code == 200
                assert items.status_code == 200

            asyncio.run(
                _shape(str(snapshots[0]["id"]), current=False, long_text="opis")
            )
            asyncio.run(
                _shape(str(snapshots[1]["id"]), current=True, long_text="opis")
            )
            delta = client.post(
                f"{root}/deltas",
                json={
                    "previous_snapshot_id": snapshots[0]["id"],
                    "current_snapshot_id": snapshots[1]["id"],
                    "idempotency_key": suffix,
                },
            )
            assert delta.status_code == 201, delta.text
            delta_row = delta.json()
            assert client.get(f"{root}/deltas/{delta_row['id']}/summary").status_code == 200
            changed = client.get(
                f"{root}/deltas/{delta_row['id']}/items",
                params={"limit": 10},
            )
            assert changed.status_code == 200 and changed.json()["total"] > 0
            asyncio.run(_add_delta_signal(delta_row["id"]))

            synchronized = client.post(
                "/suppliers/platform/supplier-incidents/sync/"
                f"delta-runs/{delta_row['id']}"
            )
            assert synchronized.status_code == 200, synchronized.text
            incident = synchronized.json()[0]
            acknowledged = client.post(
                "/suppliers/platform/supplier-incidents/"
                f"{incident['id']}/acknowledge"
            )
            assert acknowledged.status_code == 200
            comment = client.post(
                "/suppliers/platform/supplier-incidents/"
                f"{incident['id']}/comments",
                json={"body": "Provereno kroz objedinjeni API"},
            )
            assert comment.status_code == 201
            resolved = client.post(
                "/suppliers/platform/supplier-incidents/"
                f"{incident['id']}/resolve",
                json={
                    "resolution_code": "API_VERIFIED",
                    "resolution_summary": "Provera završena",
                },
            )
            assert resolved.status_code == 200

            expected_codes = {
                supplier["supplier_code"],
                source["source_code"],
                acquisitions[0]["acquisition_code"],
                snapshots[0]["snapshot_code"],
                delta_row["delta_code"],
                incident["incident_code"],
            }
            found_codes = set()
            for code in expected_codes:
                response = client.get(
                    "/suppliers/platform/search",
                    params={"query": code, "limit": 10},
                )
                assert response.status_code == 200
                found_codes.update(row["code"] for row in response.json()["items"])
            assert expected_codes <= found_codes

            overview = client.get("/suppliers/platform/overview")
            assert overview.status_code == 200
            assert overview.json()["active_suppliers"]["value"] >= 1
            page = client.get(
                "/suppliers/platform/incidents",
                params={"limit": 1, "sort_by": "incident_code"},
            )
            assert page.status_code == 200
            assert {"items", "total", "limit", "offset", "has_more"} <= set(
                page.json()
            )

            mixed = client.post(
                "/suppliers/platform/bulk/incidents/assign",
                json={
                    "items": [
                        {
                            "incident_id": incident["id"],
                            "assigned_user_id": "operator-39",
                        },
                        {
                            "incident_id": str(uuid.uuid4()),
                            "assigned_user_id": "operator-39",
                        },
                    ]
                },
            )
            assert mixed.status_code == 200
            assert mixed.json()["succeeded_count"] == 1
            assert mixed.json()["failed_count"] == 1
            assert client.get("/products").json()["total"] == products_before
            assert client.get("/inventory").json()["total"] == inventory_before
            assert overview.headers["x-correlation-id"] == correlation_id
            assert overview.headers["x-request-id"]
        finally:
            if supplier_id:
                asyncio.run(_cleanup(supplier_id))
