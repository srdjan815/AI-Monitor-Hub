from __future__ import annotations

import asyncio
import os
import re
import uuid

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.schema_profile_models import (
    SupplierSchemaField,
    SupplierSchemaProfile,
)

API_ROOT = "http://localhost:8000/api/v1"
DATABASE_URL = os.getenv(
    "PRODUCT_CONTENT_INTEGRATION_DATABASE_URL",
    settings.database_url,
)


def bearer(subject: str, role: str = "system_admin") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject, (role,))}"}


@pytest.fixture
def api_client() -> httpx.Client:
    with httpx.Client(
        base_url=API_ROOT,
        timeout=20.0,
        headers=bearer("supplier-schema-tests"),
    ) as client:
        yield client


async def purge(supplier_id: str) -> None:
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            profile_ids = (
                await session.scalars(
                    SupplierSchemaProfile.__table__.select()
                    .with_only_columns(SupplierSchemaProfile.id)
                    .where(
                        SupplierSchemaProfile.source_connection_id.in_(
                            SupplierSource.__table__.select()
                            .with_only_columns(SupplierSource.id)
                            .where(SupplierSource.supplier_id == uuid.UUID(supplier_id))
                        )
                    )
                )
            ).all()
            if profile_ids:
                await session.execute(
                    delete(SupplierSchemaField).where(
                        SupplierSchemaField.schema_profile_id.in_(profile_ids)
                    )
                )
                await session.execute(
                    delete(SupplierSchemaProfile).where(
                        SupplierSchemaProfile.id.in_(profile_ids)
                    )
                )
            await session.execute(
                delete(SupplierSource).where(
                    SupplierSource.supplier_id == uuid.UUID(supplier_id)
                )
            )
            await session.execute(
                delete(Supplier).where(Supplier.id == uuid.UUID(supplier_id))
            )
            await session.commit()
    finally:
        await engine.dispose()


def setup_source(client: httpx.Client, suffix: str) -> tuple[str, str]:
    supplier = client.post(
        "/suppliers",
        json={"company_name": f"Schema Supplier {suffix}"},
    )
    assert supplier.status_code == 201, supplier.text
    supplier_id = supplier.json()["id"]
    source = client.post(
        f"/suppliers/{supplier_id}/sources",
        json={
            "name": f"Schema Source {suffix}",
            "source_type": "MANUAL_UPLOAD",
            "configuration": {
                "accepted_file_types": ["CSV"],
                "maximum_file_size_mb": 10,
            },
        },
    )
    assert source.status_code == 201, source.text
    return supplier_id, source.json()["id"]


def field_payload(code: str, position: int, **flags: bool) -> dict[str, object]:
    return {
        "field_code": code,
        "name": code.title(),
        "position": position,
        "data_type": "STRING",
        "required": True,
        "nullable": False,
        "max_length": 255,
        "path": f"column {position}",
        **flags,
    }


def test_profile_field_version_lifecycle(api_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id, source_id = setup_source(api_client, suffix)
    root = f"/suppliers/{supplier_id}/sources/{source_id}/schema-profiles"
    try:
        created = api_client.post(
            root,
            json={"name": f"Price List {suffix}", "description": "Version one"},
        )
        assert created.status_code == 201, created.text
        profile = created.json()
        assert re.fullmatch(r"SCH-\d{6,}", profile["schema_code"])
        assert profile["version_number"] == 1
        assert profile["status"] == "DRAFT"
        assert profile["field_count"] == 0
        assert created.headers["location"].endswith(profile["id"])

        empty_activation = api_client.post(
            f"{root}/{profile['id']}/activate",
            json={"version": profile["version"]},
        )
        assert empty_activation.status_code == 409
        assert empty_activation.json()["code"] == "schema_profile_empty"

        fields = f"{root}/{profile['id']}/fields"
        sku = api_client.post(
            fields,
            json=field_payload("sku", 1, is_key=True, is_identifier=True),
        )
        assert sku.status_code == 201, sku.text
        sku_data = sku.json()

        duplicate_code = api_client.post(
            fields,
            json=field_payload("SKU", 2),
        )
        assert duplicate_code.status_code == 409
        assert duplicate_code.json()["code"] == "schema_field_code_conflict"
        duplicate_position = api_client.post(
            fields,
            json=field_payload("name", 1),
        )
        assert duplicate_position.status_code == 409
        second_key = api_client.post(
            fields,
            json=field_payload("ean", 2, is_key=True),
        )
        assert second_key.status_code == 409

        price = api_client.post(
            fields,
            json=field_payload("price", 2, is_price=True),
        )
        assert price.status_code == 201
        second_price = api_client.post(
            fields,
            json=field_payload("retail_price", 3, is_price=True),
        )
        assert second_price.status_code == 409

        fetched = api_client.get(f"{fields}/{sku_data['id']}")
        assert fetched.status_code == 200
        profile = api_client.get(f"{root}/{profile['id']}").json()
        assert profile["field_count"] == 2

        stale = api_client.patch(
            f"{root}/{profile['id']}",
            json={"version": 1, "description": "stale"},
        )
        assert stale.status_code == 409

        activated = api_client.post(
            f"{root}/{profile['id']}/activate",
            json={"version": profile["version"]},
        )
        assert activated.status_code == 200, activated.text
        active = activated.json()
        assert active["status"] == "ACTIVE"

        immutable = api_client.patch(
            f"{fields}/{sku_data['id']}",
            json={**field_payload("sku", 1), "version": sku_data["version"]},
        )
        assert immutable.status_code == 409
        assert immutable.json()["code"] == "schema_profile_immutable"

        cloned = api_client.post(
            f"{root}/{profile['id']}/clone",
            json={"version": active["version"]},
        )
        assert cloned.status_code == 201, cloned.text
        clone = cloned.json()
        assert clone["version_number"] == 2
        assert clone["status"] == "DRAFT"
        clone_fields = api_client.get(f"{root}/{clone['id']}/fields").json()
        assert clone_fields["total"] == 2
        cloned_sku = next(
            item for item in clone_fields["items"] if item["field_code"] == "sku"
        )
        partial = api_client.patch(
            f"{root}/{clone['id']}/fields/{cloned_sku['id']}",
            json={"version": cloned_sku["version"], "example_value": "SKU-123"},
        )
        assert partial.status_code == 200, partial.text
        assert partial.json()["example_value"] == "SKU-123"
        clone = api_client.get(f"{root}/{clone['id']}").json()

        activated_clone = api_client.post(
            f"{root}/{clone['id']}/activate",
            json={"version": clone["version"]},
        )
        assert activated_clone.status_code == 200
        assert activated_clone.json()["status"] == "ACTIVE"
        assert api_client.get(f"{root}/{profile['id']}").json()["status"] == "ARCHIVED"

        listing = api_client.get(root, params={"status": "ACTIVE"}).json()
        assert [item["id"] for item in listing["items"]] == [clone["id"]]

        assert api_client.delete(f"{root}/{clone['id']}").status_code == 204
        assert api_client.get(root, params={"status": "ACTIVE"}).json()["total"] == 0
        all_rows = api_client.get(root, params={"active_only": "false"}).json()
        assert any(item["id"] == clone["id"] for item in all_rows["items"])

        assert (
            api_client.delete(
                f"/suppliers/{supplier_id}/sources/{source_id}"
            ).status_code
            == 204
        )
        assert api_client.get(root, params={"active_only": "false"}).status_code == 200
        blocked = api_client.post(root, json={"name": "Blocked profile"})
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "schema_profile_source_inactive"
    finally:
        asyncio.run(purge(supplier_id))


def test_analysis_rejects_draft_source_with_clear_error(
    api_client: httpx.Client,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id, source_id = setup_source(api_client, suffix)
    root = f"/suppliers/{supplier_id}/sources/{source_id}/schema-profiles"
    try:
        response = api_client.post(
            f"{root}/analyze",
            json={"name": f"Analysis {suffix}"},
        )
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "schema_analysis_source_not_active"
        assert "aktivirana" in response.text
    finally:
        asyncio.run(purge(supplier_id))


def test_profile_validation_permissions_and_parent_isolation(
    api_client: httpx.Client,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id, source_id = setup_source(api_client, suffix)
    other_supplier, other_source = setup_source(api_client, f"other-{suffix}")
    root = f"/suppliers/{supplier_id}/sources/{source_id}/schema-profiles"
    try:
        invalid_path = field_payload("sku", 1)
        invalid_path["path"] = "../secret"
        profile = api_client.post(root, json={"name": f"Profile {suffix}"}).json()
        response = api_client.post(
            f"{root}/{profile['id']}/fields",
            json=invalid_path,
        )
        assert response.status_code == 422

        invalid_decimal = field_payload("price", 1)
        invalid_decimal.update(
            {"data_type": "DECIMAL", "max_length": 10, "precision": 8, "scale": 9}
        )
        assert (
            api_client.post(
                f"{root}/{profile['id']}/fields",
                json=invalid_decimal,
            ).status_code
            == 422
        )

        wrong_parent = api_client.get(
            f"/suppliers/{other_supplier}/sources/{other_source}/"
            f"schema-profiles/{profile['id']}"
        )
        assert wrong_parent.status_code == 404

        with httpx.Client(
            base_url=API_ROOT,
            timeout=20.0,
            headers=bearer("schema-editor", "schema_profile_editor"),
        ) as editor:
            assert editor.get(root).status_code == 200
            denied = editor.post(
                f"{root}/{profile['id']}/activate",
                json={"version": profile["version"]},
            )
            assert denied.status_code == 403
        with httpx.Client(
            base_url=API_ROOT,
            timeout=20.0,
            headers=bearer("schema-activator", "schema_profile_activator"),
        ) as activator:
            assert activator.get(root).status_code == 200
            assert (
                activator.post(root, json={"name": "Forbidden write"}).status_code
                == 403
            )
    finally:
        asyncio.run(purge(supplier_id))
        asyncio.run(purge(other_supplier))
