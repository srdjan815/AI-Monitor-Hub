from __future__ import annotations

import asyncio
import os
import re
import uuid

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.modules.suppliers.models import Supplier, SupplierContact
from app.modules.suppliers.schemas import (
    SupplierContactCreate,
    SupplierCreate,
)
from app.modules.suppliers.service import SupplierService

API_ROOT = "http://localhost:8000/api/v1"
DATABASE_URL = os.getenv(
    "PRODUCT_CONTENT_INTEGRATION_DATABASE_URL",
    settings.database_url,
)


async def purge_suppliers(*supplier_ids: str) -> None:
    ids = [uuid.UUID(value) for value in supplier_ids if value]
    if not ids:
        return
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            await session.execute(
                delete(SupplierContact).where(SupplierContact.supplier_id.in_(ids))
            )
            await session.execute(delete(Supplier).where(Supplier.id.in_(ids)))
            await session.commit()
    finally:
        await engine.dispose()


def bearer(subject: str, role: str = "system_admin") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject, (role,))}"}


@pytest.fixture
def api_client() -> httpx.Client:
    with httpx.Client(
        base_url=API_ROOT,
        timeout=15.0,
        headers=bearer("supplier-tests"),
    ) as client:
        yield client


def test_supplier_contact_schema_requires_a_valid_channel() -> None:
    with pytest.raises(ValidationError):
        SupplierContactCreate(name="Bez kontakta")
    with pytest.raises(ValidationError):
        SupplierContactCreate(name="Pogrešan email", email="invalid")

    assert SupplierContactCreate(name="Email", email=" TEST@EXAMPLE.COM ").email == (
        "test@example.com"
    )
    assert SupplierContactCreate(name="Telefon", phone="+381 11 123 456").phone


def test_supplier_and_contact_crud(api_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id: str | None = None
    other_supplier_id: str | None = None
    contact_id: str | None = None
    try:
        created = api_client.post(
            "/suppliers",
            json={
                "company_name": f"  Supplier Test {suffix}  ",
                "address": "  Test adresa 1  ",
                "tax_identifier": f"pib-{suffix}",
                "registration_number": f"reg-{suffix}",
                "status": "ACTIVE",
            },
        )
        assert created.status_code == 201, created.text
        supplier = created.json()
        supplier_id = supplier["id"]
        assert re.fullmatch(r"SUP-\d{6,}", supplier["supplier_code"])
        assert supplier["company_name"] == f"Supplier Test {suffix}"
        assert supplier["tax_identifier"] == f"PIB-{suffix.upper()}"
        assert created.headers["location"].endswith(supplier_id)

        duplicate_tax = api_client.post(
            "/suppliers",
            json={
                "company_name": f"Duplicate Tax {suffix}",
                "tax_identifier": f"pib-{suffix}",
            },
        )
        assert duplicate_tax.status_code == 409
        assert duplicate_tax.json()["code"] == "supplier_tax_identifier_conflict"
        assert duplicate_tax.json()["request_id"]

        duplicate_registration = api_client.post(
            "/suppliers",
            json={
                "company_name": f"Duplicate Registration {suffix}",
                "registration_number": f"reg-{suffix}",
            },
        )
        assert duplicate_registration.status_code == 409
        assert (
            duplicate_registration.json()["code"]
            == "supplier_registration_number_conflict"
        )

        fetched = api_client.get(f"/suppliers/{supplier_id}")
        assert fetched.status_code == 200
        assert fetched.json()["supplier_code"] == supplier["supplier_code"]

        filtered = api_client.get(
            "/suppliers",
            params={
                "company_name": suffix,
                "status": "ACTIVE",
                "tax_identifier": f"pib-{suffix}",
            },
        )
        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()["items"]] == [supplier_id]

        cursor_page = api_client.get(
            "/suppliers",
            params={"pagination": "cursor", "limit": 1},
        )
        assert cursor_page.status_code == 200
        assert cursor_page.headers["x-snapshot-at"]

        no_change = api_client.patch(
            f"/suppliers/{supplier_id}",
            json={
                "version": supplier["version"],
                "company_name": supplier["company_name"],
            },
        )
        assert no_change.status_code == 200
        assert no_change.json()["version"] == supplier["version"]

        updated = api_client.patch(
            f"/suppliers/{supplier_id}",
            json={"version": supplier["version"], "status": "SUSPENDED"},
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "SUSPENDED"
        assert updated.json()["version"] == supplier["version"] + 1

        stale = api_client.patch(
            f"/suppliers/{supplier_id}",
            json={"version": supplier["version"], "status": "ACTIVE"},
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "supplier_version_conflict"

        email_contact = api_client.post(
            f"/suppliers/{supplier_id}/contacts",
            json={
                "contact_type": "TECHNICAL",
                "name": "  Tehnička Podrška  ",
                "email": f"TECH-{suffix}@EXAMPLE.COM",
                "is_primary": True,
            },
        )
        assert email_contact.status_code == 201, email_contact.text
        contact = email_contact.json()
        contact_id = contact["id"]
        assert contact["email"] == f"tech-{suffix}@example.com"

        phone_contact = api_client.post(
            f"/suppliers/{supplier_id}/contacts",
            json={
                "contact_type": "COMMERCIAL",
                "name": "Prodaja",
                "phone": "+381 11 123 456",
            },
        )
        assert phone_contact.status_code == 201

        invalid_contact = api_client.post(
            f"/suppliers/{supplier_id}/contacts",
            json={"contact_type": "OTHER", "name": "Bez kanala"},
        )
        assert invalid_contact.status_code == 422

        primary_conflict = api_client.post(
            f"/suppliers/{supplier_id}/contacts",
            json={
                "contact_type": "TECHNICAL",
                "name": "Drugi glavni",
                "phone": "+381 11 999 999",
                "is_primary": True,
            },
        )
        assert primary_conflict.status_code == 409
        assert primary_conflict.json()["code"] == "supplier_contact_primary_conflict"

        contacts = api_client.get(
            f"/suppliers/{supplier_id}/contacts",
            params={"contact_type": "TECHNICAL", "is_primary": "true"},
        )
        assert contacts.status_code == 200
        assert [item["id"] for item in contacts.json()["items"]] == [contact_id]

        other = api_client.post(
            "/suppliers",
            json={"company_name": f"Other Supplier {suffix}"},
        )
        assert other.status_code == 201
        other_supplier_id = other.json()["id"]
        wrong_parent = api_client.get(
            f"/suppliers/{other_supplier_id}/contacts/{contact_id}"
        )
        assert wrong_parent.status_code == 404
        assert wrong_parent.json()["code"] == "supplier_contact_not_found"

        changed_contact = api_client.patch(
            f"/suppliers/{supplier_id}/contacts/{contact_id}",
            json={
                "version": contact["version"],
                "position": "Tehnički direktor",
            },
        )
        assert changed_contact.status_code == 200
        assert changed_contact.json()["version"] == contact["version"] + 1

        stale_contact = api_client.patch(
            f"/suppliers/{supplier_id}/contacts/{contact_id}",
            json={"version": contact["version"], "position": "Stara izmena"},
        )
        assert stale_contact.status_code == 409
        assert stale_contact.json()["code"] == "supplier_contact_version_conflict"

        assert (
            api_client.delete(
                f"/suppliers/{supplier_id}/contacts/{contact_id}"
            ).status_code
            == 204
        )
        assert (
            api_client.delete(
                f"/suppliers/{supplier_id}/contacts/{contact_id}"
            ).status_code
            == 204
        )
        inactive_contacts = api_client.get(
            f"/suppliers/{supplier_id}/contacts",
            params={"active_only": "false", "contact_type": "TECHNICAL"},
        )
        assert inactive_contacts.status_code == 200
        assert inactive_contacts.json()["items"][0]["is_active"] is False

        assert api_client.delete(f"/suppliers/{supplier_id}").status_code == 204
        assert api_client.delete(f"/suppliers/{supplier_id}").status_code == 204

        active_list = api_client.get(
            "/suppliers", params={"supplier_code": supplier["supplier_code"]}
        )
        assert active_list.status_code == 200
        assert active_list.json()["items"] == []
        all_list = api_client.get(
            "/suppliers",
            params={
                "supplier_code": supplier["supplier_code"],
                "active_only": "false",
            },
        )
        assert all_list.status_code == 200
        assert all_list.json()["items"][0]["status"] == "INACTIVE"

        archived_patch = api_client.patch(
            f"/suppliers/{supplier_id}",
            json={
                "version": all_list.json()["items"][0]["version"],
                "status": "ACTIVE",
            },
        )
        assert archived_patch.status_code == 409
        assert archived_patch.json()["code"] == "supplier_inactive"

        archived_contact = api_client.post(
            f"/suppliers/{supplier_id}/contacts",
            json={"name": "Novi kontakt", "phone": "+381 11 000 000"},
        )
        assert archived_contact.status_code == 409
        assert archived_contact.json()["code"] == "supplier_inactive"
    finally:
        asyncio.run(
            purge_suppliers(
                *(value for value in (supplier_id, other_supplier_id) if value)
            )
        )


def test_supplier_request_validation_and_immutable_code(
    api_client: httpx.Client,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    blank = api_client.post("/suppliers", json={"company_name": "   "})
    assert blank.status_code == 422
    assert blank.json()["code"] == "supplier_invalid"
    assert blank.json()["request_id"]

    invalid_status = api_client.post(
        "/suppliers",
        json={"company_name": "Invalid status", "status": "DELETED"},
    )
    assert invalid_status.status_code == 422
    assert invalid_status.json()["code"] == "VALIDATION_ERROR"

    created = api_client.post(
        "/suppliers",
        json={
            "company_name": f"Immutable {suffix}",
            "supplier_code": "SUP-999999",
        },
    )
    assert created.status_code == 201
    supplier = created.json()
    try:
        assert supplier["supplier_code"] != "SUP-999999"
        update = api_client.patch(
            f"/suppliers/{supplier['id']}",
            json={
                "version": supplier["version"],
                "supplier_code": "SUP-999999",
            },
        )
        assert update.status_code == 200
        assert update.json()["supplier_code"] == supplier["supplier_code"]
        assert update.json()["version"] == supplier["version"]
    finally:
        asyncio.run(purge_suppliers(supplier["id"]))


def test_supplier_filtering_and_cursor_traversal_is_deterministic(
    api_client: httpx.Client,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_ids: list[str] = []
    try:
        for index in range(3):
            response = api_client.post(
                "/suppliers",
                json={
                    "company_name": f"Cursor {suffix} {index}",
                    "tax_identifier": f"cursor-pib-{suffix}-{index}",
                    "status": "ACTIVE",
                },
            )
            assert response.status_code == 201
            supplier_ids.append(response.json()["id"])

        filtered = api_client.get(
            "/suppliers",
            params={
                "company_name": f"Cursor {suffix}",
                "status": "ACTIVE",
                "active_only": "true",
            },
        )
        assert filtered.status_code == 200
        assert [item["company_name"] for item in filtered.json()["items"]] == [
            f"Cursor {suffix} {index}" for index in range(3)
        ]

        seen: list[str] = []
        cursor: str | None = None
        snapshot: str | None = None
        while True:
            params = {
                "pagination": "cursor",
                "limit": 1,
                "company_name": f"Cursor {suffix}",
            }
            if cursor is not None:
                params["cursor"] = cursor
            page = api_client.get("/suppliers", params=params)
            assert page.status_code == 200
            if snapshot is None:
                snapshot = page.headers["x-snapshot-at"]
            assert page.headers["x-snapshot-at"] == snapshot
            seen.extend(item["id"] for item in page.json()["items"])
            cursor = page.headers.get("x-next-cursor")
            if cursor is None:
                break
        assert seen == list(reversed(supplier_ids))
        assert len(seen) == len(set(seen)) == 3
    finally:
        asyncio.run(purge_suppliers(*supplier_ids))


@pytest.mark.asyncio
async def test_supplier_permissions_are_domain_specific() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        anonymous = await client.get("/api/v1/suppliers")
        assert anonymous.status_code == 401

        catalog_only = await client.get(
            "/api/v1/suppliers",
            headers=bearer("catalog", "catalog_admin"),
        )
        assert catalog_only.status_code == 403

        supplier_read = await client.get(
            "/api/v1/suppliers",
            headers=bearer("supplier-admin", "supplier_admin"),
        )
        assert supplier_read.status_code == 200

        read_only_write = await client.post(
            "/api/v1/suppliers",
            headers=bearer("reader", "read_only"),
            json={"company_name": "Forbidden supplier"},
        )
        assert read_only_write.status_code == 403


@pytest.mark.asyncio
async def test_concurrent_supplier_codes_are_unique() -> None:
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:12]

    async def create(index: int) -> str:
        async with sessions() as session:
            supplier = await SupplierService(session).create_supplier(
                SupplierCreate(company_name=f"Concurrent {suffix} {index}")
            )
            return supplier.supplier_code

    try:
        codes = await asyncio.gather(*(create(index) for index in range(8)))
        assert len(set(codes)) == 8
        assert all(re.fullmatch(r"SUP-\d{6,}", code) for code in codes)
    finally:
        async with sessions() as session:
            ids = list(
                (
                    await session.scalars(
                        select(Supplier.id).where(
                            Supplier.company_name.like(f"Concurrent {suffix}%")
                        )
                    )
                ).all()
            )
            if ids:
                await session.execute(
                    delete(SupplierContact).where(SupplierContact.supplier_id.in_(ids))
                )
                await session.execute(delete(Supplier).where(Supplier.id.in_(ids)))
                await session.commit()
        await engine.dispose()


def test_supplier_openapi_contract_and_chapter_scope() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    expected = {
        "/api/v1/suppliers",
        "/api/v1/suppliers/{supplier_id}",
        "/api/v1/suppliers/{supplier_id}/contacts",
        "/api/v1/suppliers/{supplier_id}/contacts/{contact_id}",
    }
    assert expected <= set(paths)
    assert not any(
        token in path
        for path in paths
        for token in (
            "/supplier-sources",
                "/supplier-products",
                "/supplier-snapshots",
            )
    )
    supplier_schema = schema["components"]["schemas"]["SupplierRead"]
    assert (
        "automatski generiše"
        in (supplier_schema["properties"]["supplier_code"]["description"])
    )
    assert "paralel" in supplier_schema["properties"]["version"]["description"]
    for path in expected:
        for operation in paths[path].values():
            if isinstance(operation, dict) and "responses" in operation:
                assert operation.get("description")
