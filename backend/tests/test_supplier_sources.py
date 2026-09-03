from __future__ import annotations

import asyncio
import os
import re
import uuid

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import security
from app.core.config import settings
from app.core.security import (
    SUPPLIER_SOURCES_READ,
    SUPPLIER_SOURCES_VALIDATE,
    SUPPLIER_SOURCES_WRITE,
    LocalHMACAuthenticationAdapter,
    create_access_token,
)
from app.main import app
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.source_schemas import (
    SupplierSourceCreate,
    SupplierSourceUpdate,
)
from app.modules.suppliers.source_service import SupplierSourceService

API_ROOT = "http://localhost:8000/api/v1"
DATABASE_URL = os.getenv(
    "PRODUCT_CONTENT_INTEGRATION_DATABASE_URL",
    settings.database_url,
)


def bearer(subject: str, role: str = "system_admin") -> dict[str, str]:
    if role == "system_admin" and settings.auth_mode == "static":
        assert settings.ai_monitor_admin_token is not None
        return {
            "Authorization": (
                f"Bearer {settings.ai_monitor_admin_token.get_secret_value()}"
            )
        }
    return {"Authorization": f"Bearer {create_access_token(subject, (role,))}"}


@pytest.fixture
def api_client() -> httpx.Client:
    with httpx.Client(
        base_url=API_ROOT,
        timeout=20.0,
        headers=bearer("supplier-source-tests"),
    ) as client:
        yield client


async def purge(*supplier_ids: str) -> None:
    ids = [uuid.UUID(value) for value in supplier_ids if value]
    if not ids:
        return
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            await session.execute(
                delete(SupplierSource).where(SupplierSource.supplier_id.in_(ids))
            )
            await session.execute(delete(Supplier).where(Supplier.id.in_(ids)))
            await session.commit()
    finally:
        await engine.dispose()


def create_supplier(client: httpx.Client, name: str) -> dict:
    response = client.post("/suppliers", json={"company_name": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_supplier_source_crud_lifecycle_and_isolation(
    api_client: httpx.Client,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_ids: list[str] = []
    try:
        supplier = create_supplier(api_client, f"Source Supplier {suffix}")
        other = create_supplier(api_client, f"Other Source Supplier {suffix}")
        supplier_ids.extend([supplier["id"], other["id"]])
        path = f"/suppliers/{supplier['id']}/sources"
        payload = {
            "name": f"Primary API {suffix}",
            "source_type": "API",
            "configuration": {
                "base_url": "http://localhost:8000/health",
                "authentication_type": "BEARER",
            },
        }
        created_response = api_client.post(path, json=payload)
        assert created_response.status_code == 201, created_response.text
        source = created_response.json()
        assert re.fullmatch(r"SRC-\d{6,}", source["source_code"])
        assert source["status"] == "DRAFT"
        assert source["has_secret_reference"] is False
        assert "secret_reference" not in source
        assert created_response.headers["location"].endswith(source["id"])

        with httpx.Client(
            base_url=API_ROOT,
            timeout=20.0,
            headers=bearer("source-validator", "supplier_source_validator"),
        ) as validator_client:
            permitted = validator_client.post(f"{path}/{source['id']}/validate")
            assert permitted.status_code == 200, permitted.text
            denied = validator_client.patch(
                f"{path}/{source['id']}",
                json={
                    "version": permitted.json()["version"],
                    "description": "Forbidden",
                },
            )
        source["version"] = permitted.json()["version"]
        assert denied.status_code == 403

        duplicate = api_client.post(
            path, json={**payload, "name": payload["name"].upper()}
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "supplier_source_name_conflict"
        assert duplicate.json()["request_id"]

        same_name_other = api_client.post(
            f"/suppliers/{other['id']}/sources",
            json=payload,
        )
        assert same_name_other.status_code == 201

        wrong_parent = api_client.get(
            f"/suppliers/{other['id']}/sources/{source['id']}"
        )
        assert wrong_parent.status_code == 404
        assert wrong_parent.json()["code"] == "supplier_source_not_found"

        immutable = api_client.patch(
            f"{path}/{source['id']}",
            json={"version": source["version"], "source_type": "FTP"},
        )
        assert immutable.status_code == 409
        assert immutable.json()["code"] == "supplier_source_type_immutable"

        validation = api_client.post(f"{path}/{source['id']}/validate")
        assert validation.status_code == 200
        assert validation.json()["valid"] is False
        assert validation.json()["status"] == "INVALID"
        source["version"] = validation.json()["version"]

        missing_secret = api_client.patch(
            f"{path}/{source['id']}",
            json={"version": source["version"], "status": "ACTIVE"},
        )
        assert missing_secret.status_code == 409
        assert (
            missing_secret.json()["code"] == "supplier_source_missing_secret_reference"
        )

        configured = api_client.put(
            f"{path}/{source['id']}/credentials",
            json={
                "placement": "HEADER",
                "token": "disposable-test-token",
            },
        )
        assert configured.status_code == 200, configured.text
        probed = api_client.post(f"{path}/{source['id']}/probe")
        assert probed.status_code == 200, probed.text
        assert probed.json()["successful"] is True
        source = api_client.get(f"{path}/{source['id']}").json()
        activated = api_client.patch(
            f"{path}/{source['id']}",
            json={"version": source["version"], "status": "ACTIVE"},
        )
        assert activated.status_code == 200, activated.text
        active = activated.json()
        assert active["status"] == "ACTIVE"
        assert active["has_secret_reference"] is True
        assert "secret_reference" not in active
        assert "disposable-test-token" not in activated.text

        valid = api_client.post(f"{path}/{source['id']}/validate")
        assert valid.status_code == 200
        assert valid.json()["valid"] is True
        active["version"] = valid.json()["version"]

        stale = api_client.patch(
            f"{path}/{source['id']}",
            json={"version": source["version"], "status": "INACTIVE"},
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "supplier_source_version_conflict"

        inactive = api_client.patch(
            f"{path}/{source['id']}",
            json={"version": active["version"], "status": "INACTIVE"},
        )
        assert inactive.status_code == 200
        assert inactive.json()["status"] == "INACTIVE"

        filtered = api_client.get(
            path,
            params={"source_type": "API", "status": "INACTIVE", "name": suffix},
        )
        assert [item["id"] for item in filtered.json()["items"]] == [source["id"]]

        assert api_client.delete(f"{path}/{source['id']}").status_code == 204
        assert api_client.delete(f"{path}/{source['id']}").status_code == 204
        assert api_client.get(path).json()["items"] == []
        archived = api_client.get(path, params={"active_only": "false"}).json()
        row = next(item for item in archived["items"] if item["id"] == source["id"])
        assert row["is_active"] is False

        reactivate = api_client.patch(
            f"{path}/{source['id']}",
            json={"version": row["version"], "status": "ACTIVE"},
        )
        assert reactivate.status_code == 409
        assert reactivate.json()["code"] == "supplier_source_inactive"

        reused_name = api_client.post(path, json=payload)
        assert reused_name.status_code == 201
        assert reused_name.json()["id"] != source["id"]
    finally:
        asyncio.run(purge(*supplier_ids))


def test_source_validation_and_request_bounds(api_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier = create_supplier(api_client, f"Validation Supplier {suffix}")
    path = f"/suppliers/{supplier['id']}/sources"
    try:
        blank = api_client.post(
            path,
            json={
                "name": "   ",
                "source_type": "HTTP",
                "configuration": {"url": "https://example.test/feed"},
            },
        )
        assert blank.status_code == 422
        assert blank.json()["code"] == "supplier_source_invalid_configuration"

        unknown = api_client.post(
            path,
            json={
                "name": "Unknown",
                "source_type": "FTP",
                "configuration": {
                    "host": "ftp.example.test",
                    "filename_pattern": "*.csv",
                    "password": "forbidden",
                },
            },
        )
        assert unknown.status_code == 422
        assert unknown.json()["code"] == "supplier_source_invalid_configuration"
        assert "forbidden" not in unknown.text

        invalid_type = api_client.post(
            path,
            json={
                "name": "Invalid",
                "source_type": "DATABASE",
                "configuration": {"host": "db"},
            },
        )
        assert invalid_type.status_code == 422
        assert invalid_type.json()["code"] == "VALIDATION_ERROR"

        invalid_transition = api_client.post(
            path,
            json={
                "name": "Error status",
                "source_type": "MANUAL_UPLOAD",
                "configuration": {"accepted_file_types": ["CSV"]},
                "status": "ERROR",
            },
        )
        assert invalid_transition.status_code == 409
        assert (
            invalid_transition.json()["code"]
            == "supplier_source_invalid_status_transition"
        )
    finally:
        asyncio.run(purge(supplier["id"]))


def test_supplier_source_cursor_traversal_is_deterministic(
    api_client: httpx.Client,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier = create_supplier(api_client, f"Cursor Source Supplier {suffix}")
    path = f"/suppliers/{supplier['id']}/sources"
    source_ids: list[str] = []
    try:
        for index in range(3):
            response = api_client.post(
                path,
                json={
                    "name": f"Cursor Source {suffix} {index}",
                    "source_type": "MANUAL_UPLOAD",
                    "configuration": {"accepted_file_types": ["CSV"]},
                },
            )
            assert response.status_code == 201
            source_ids.append(response.json()["id"])

        seen: list[str] = []
        cursor: str | None = None
        snapshot: str | None = None
        while True:
            params = {
                "pagination": "cursor",
                "limit": 1,
                "name": f"Cursor Source {suffix}",
            }
            if cursor is not None:
                params["cursor"] = cursor
            page = api_client.get(path, params=params)
            assert page.status_code == 200
            if snapshot is None:
                snapshot = page.headers["x-snapshot-at"]
            assert page.headers["x-snapshot-at"] == snapshot
            seen.extend(item["id"] for item in page.json()["items"])
            cursor = page.headers.get("x-next-cursor")
            if cursor is None:
                break
        assert seen == list(reversed(source_ids))
        assert len(seen) == len(set(seen)) == 3
    finally:
        asyncio.run(purge(supplier["id"]))


def test_archived_supplier_blocks_source_activation_without_cascade(
    api_client: httpx.Client,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier = create_supplier(api_client, f"Archived Source Supplier {suffix}")
    path = f"/suppliers/{supplier['id']}/sources"
    try:
        source_response = api_client.post(
            path,
            json={
                "name": f"Preserved {suffix}",
                "source_type": "MANUAL_UPLOAD",
                "configuration": {"accepted_file_types": ["CSV"]},
            },
        )
        assert source_response.status_code == 201
        source = source_response.json()
        assert api_client.delete(f"/suppliers/{supplier['id']}").status_code == 204

        preserved = api_client.get(f"{path}/{source['id']}")
        assert preserved.status_code == 200
        assert preserved.json()["id"] == source["id"]

        blocked = api_client.patch(
            f"{path}/{source['id']}",
            json={"version": source["version"], "status": "ACTIVE"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "supplier_source_supplier_inactive"

        create_blocked = api_client.post(
            path,
            json={
                "name": "Blocked",
                "source_type": "MANUAL_UPLOAD",
                "configuration": {"accepted_file_types": ["CSV"]},
            },
        )
        assert create_blocked.status_code == 409
        assert create_blocked.json()["code"] == "supplier_source_supplier_inactive"
    finally:
        asyncio.run(purge(supplier["id"]))


@pytest.mark.asyncio
async def test_supplier_source_permissions_are_domain_specific(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Static development authentication intentionally represents only the local
    # system administrator. Use the production-equivalent signed-token adapter
    # here so this test continues to exercise every domain role boundary.
    monkeypatch.setattr(
        security,
        "authentication_adapter",
        LocalHMACAuthenticationAdapter(settings),
    )
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        anonymous = await client.get(f"/api/v1/suppliers/{uuid.uuid4()}/sources")
        assert anonymous.status_code == 401

        catalog = await client.get(
            f"/api/v1/suppliers/{uuid.uuid4()}/sources",
            headers=bearer("catalog", "catalog_admin"),
        )
        assert catalog.status_code == 403

        read_only_headers = bearer("reader", "read_only")
        read_only_token = read_only_headers["Authorization"].removeprefix("Bearer ")
        read_only_principal = security.authenticate_token(read_only_token)
        assert SUPPLIER_SOURCES_READ in read_only_principal.permissions
        assert SUPPLIER_SOURCES_WRITE not in read_only_principal.permissions
        assert SUPPLIER_SOURCES_VALIDATE not in read_only_principal.permissions

        read_only_write = await client.post(
            f"/api/v1/suppliers/{uuid.uuid4()}/sources",
            headers=read_only_headers,
            json={
                "name": "Forbidden",
                "source_type": "MANUAL_UPLOAD",
                "configuration": {"accepted_file_types": ["CSV"]},
            },
        )
        assert read_only_write.status_code == 403


@pytest.mark.asyncio
async def test_concurrent_source_codes_are_unique() -> None:
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    supplier_id: uuid.UUID | None = None
    suffix = uuid.uuid4().hex[:12]
    try:
        async with sessions() as session:
            supplier = Supplier(company_name=f"Concurrent Sources {suffix}")
            session.add(supplier)
            await session.commit()
            await session.refresh(supplier)
            supplier_id = supplier.id

        async def create(index: int) -> str:
            async with sessions() as session:
                source = await SupplierSourceService(session).create_source(
                    supplier.id,
                    SupplierSourceCreate(
                        name=f"Concurrent Source {suffix} {index}",
                        source_type="MANUAL_UPLOAD",
                        configuration={"accepted_file_types": ["CSV"]},
                    ),
                )
                return source.source_code

        codes = await asyncio.gather(*(create(index) for index in range(8)))
        assert len(codes) == len(set(codes)) == 8
        assert all(re.fullmatch(r"SRC-\d{6,}", code) for code in codes)
    finally:
        if supplier_id is not None:
            async with sessions() as session:
                await session.execute(
                    delete(SupplierSource).where(
                        SupplierSource.supplier_id == supplier_id
                    )
                )
                await session.execute(
                    delete(Supplier).where(Supplier.id == supplier_id)
                )
                await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_error_source_can_recover_to_draft() -> None:
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    supplier_id: uuid.UUID | None = None
    try:
        async with sessions() as session:
            supplier = Supplier(company_name=f"Recovery {uuid.uuid4().hex}")
            session.add(supplier)
            await session.flush()
            source = SupplierSource(
                supplier_id=supplier.id,
                name="Recovery source",
                source_type="MANUAL_UPLOAD",
                status="ERROR",
                configuration={"accepted_file_types": ["CSV"]},
            )
            session.add(source)
            await session.commit()
            await session.refresh(source)
            supplier_id = supplier.id
            recovered = await SupplierSourceService(session).update_source(
                supplier.id,
                source.id,
                SupplierSourceUpdate(version=source.version, status="DRAFT"),
            )
            assert recovered.status == "DRAFT"
            assert recovered.version == 2
    finally:
        if supplier_id is not None:
            async with sessions() as session:
                await session.execute(
                    delete(SupplierSource).where(
                        SupplierSource.supplier_id == supplier_id
                    )
                )
                await session.execute(
                    delete(Supplier).where(Supplier.id == supplier_id)
                )
                await session.commit()
        await engine.dispose()


def test_supplier_source_openapi_and_scope() -> None:
    schema = app.openapi()
    source_paths = {
        path
        for path in schema["paths"]
        if "/sources" in path
        and "/schema-profiles" not in path
        and "/acquisitions" not in path
        and "/snapshots" not in path
        and "/deltas" not in path
    }
    assert source_paths == {
        "/api/v1/suppliers/{supplier_id}/sources",
        "/api/v1/suppliers/{supplier_id}/sources/{source_id}",
        "/api/v1/suppliers/{supplier_id}/sources/{source_id}/credentials",
        "/api/v1/suppliers/{supplier_id}/sources/{source_id}/probe",
        "/api/v1/suppliers/{supplier_id}/sources/{source_id}/probe-upload",
        "/api/v1/suppliers/{supplier_id}/sources/{source_id}/validate",
        "/api/v1/suppliers/{supplier_id}/sources/{source_id}/pipeline-runs",
        "/api/v1/suppliers/{supplier_id}/sources/{source_id}/schedule",
        "/api/v1/suppliers/{supplier_id}/sources/{source_id}/schedule-readiness-incident",
    }
    assert set(
        schema["paths"][
            "/api/v1/suppliers/{supplier_id}/sources/{source_id}/pipeline-runs"
        ]
    ) == {"post"}
    assert set(
        schema["paths"]["/api/v1/suppliers/{supplier_id}/sources/{source_id}/schedule"]
    ) == {"get", "put"}
    assert not any(
        token in path
        for path in source_paths
        for token in ("/download", "/import", "/preview", "/refresh", "/upload")
    )
    source_schema = schema["components"]["schemas"]["SupplierSourceRead"]
    assert (
        "automatski generiše"
        in (source_schema["properties"]["source_code"]["description"])
    )
    assert "secret_reference" not in source_schema["properties"]
