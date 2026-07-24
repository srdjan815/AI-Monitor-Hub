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
from app.modules.suppliers.mapping_profile_models import (
    SupplierMappingProfile,
    SupplierMappingRule,
)
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
        headers=bearer("supplier-mapping-tests"),
    ) as client:
        yield client


async def purge(supplier_id: str) -> None:
    identifier = uuid.UUID(supplier_id)
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            source_ids = (
                await session.scalars(
                    SupplierSource.__table__.select()
                    .with_only_columns(SupplierSource.id)
                    .where(SupplierSource.supplier_id == identifier)
                )
            ).all()
            schema_ids = (
                await session.scalars(
                    SupplierSchemaProfile.__table__.select()
                    .with_only_columns(SupplierSchemaProfile.id)
                    .where(SupplierSchemaProfile.source_connection_id.in_(source_ids))
                )
            ).all()
            mapping_ids = (
                await session.scalars(
                    SupplierMappingProfile.__table__.select()
                    .with_only_columns(SupplierMappingProfile.id)
                    .where(SupplierMappingProfile.schema_profile_id.in_(schema_ids))
                )
            ).all()
            if mapping_ids:
                await session.execute(
                    delete(SupplierMappingRule).where(
                        SupplierMappingRule.mapping_profile_id.in_(mapping_ids)
                    )
                )
                await session.execute(
                    delete(SupplierMappingProfile).where(
                        SupplierMappingProfile.id.in_(mapping_ids)
                    )
                )
            if schema_ids:
                await session.execute(
                    delete(SupplierSchemaField).where(
                        SupplierSchemaField.schema_profile_id.in_(schema_ids)
                    )
                )
                await session.execute(
                    delete(SupplierSchemaProfile).where(
                        SupplierSchemaProfile.id.in_(schema_ids)
                    )
                )
            await session.execute(
                delete(SupplierSource).where(SupplierSource.supplier_id == identifier)
            )
            await session.execute(delete(Supplier).where(Supplier.id == identifier))
            await session.commit()
    finally:
        await engine.dispose()


def setup_active_schema(
    client: httpx.Client,
    suffix: str,
) -> tuple[str, str, dict, list[dict]]:
    supplier = client.post(
        "/suppliers",
        json={"company_name": f"Mapping Supplier {suffix}"},
    ).json()
    supplier_id = supplier["id"]
    source = client.post(
        f"/suppliers/{supplier_id}/sources",
        json={
            "name": f"Mapping Source {suffix}",
            "source_type": "MANUAL_UPLOAD",
            "configuration": {"accepted_file_types": ["CSV"]},
        },
    ).json()
    source_id = source["id"]
    schema_root = f"/suppliers/{supplier_id}/sources/{source_id}/schema-profiles"
    schema_response = client.post(
        schema_root,
        json={"name": f"Mapping Schema {suffix}"},
    )
    assert schema_response.status_code == 201, schema_response.text
    schema = schema_response.json()
    field_root = f"{schema_root}/{schema['id']}/fields"
    fields: list[dict] = []
    for code, position in (("sku", 1), ("description", 2), ("price", 3)):
        response = client.post(
            field_root,
            json={
                "field_code": code,
                "name": code.title(),
                "position": position,
                "data_type": "STRING",
                "required": code == "sku",
                "nullable": code != "sku",
                "path": f"column {position}",
            },
        )
        assert response.status_code == 201, response.text
        fields.append(response.json())
    schema = client.get(f"{schema_root}/{schema['id']}").json()
    activated = client.post(
        f"{schema_root}/{schema['id']}/activate",
        json={"version": schema["version"]},
    )
    assert activated.status_code == 200, activated.text
    return supplier_id, source_id, activated.json(), fields


def rule(
    field_id: str,
    target: str,
    priority: int,
    **extra: object,
) -> dict[str, object]:
    return {
        "schema_field_id": field_id,
        "target_attribute": target,
        "transformation_type": "COPY",
        "priority": priority,
        **extra,
    }


def test_mapping_profile_rule_version_lifecycle(api_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id, source_id, schema, fields = setup_active_schema(api_client, suffix)
    root = (
        f"/suppliers/{supplier_id}/sources/{source_id}/schema-profiles/"
        f"{schema['id']}/mapping-profiles"
    )
    try:
        created = api_client.post(
            root,
            json={"name": f"Catalog Mapping {suffix}"},
        )
        assert created.status_code == 201, created.text
        profile = created.json()
        assert re.fullmatch(r"MAP-\d{6,}", profile["mapping_code"])
        assert profile["version_number"] == 1
        assert profile["status"] == "DRAFT"
        assert profile["rule_count"] == 0

        empty = api_client.post(
            f"{root}/{profile['id']}/activate",
            json={"optimistic_version": profile["optimistic_version"]},
        )
        assert empty.status_code == 409
        rules = f"{root}/{profile['id']}/rules"
        sku = api_client.post(rules, json=rule(fields[0]["id"], "product_code", 1))
        assert sku.status_code == 201, sku.text
        sku_rule = sku.json()

        assert (
            api_client.post(
                rules,
                json=rule(fields[0]["id"], "ean", 2),
            ).json()["code"]
            == "mapping_rule_field_conflict"
        )
        assert (
            api_client.post(
                rules,
                json=rule(fields[1]["id"], "product_code", 2),
            ).json()["code"]
            == "mapping_rule_target_conflict"
        )
        assert (
            api_client.post(
                rules,
                json=rule(fields[1]["id"], "description", 1),
            ).json()["code"]
            == "mapping_rule_priority_conflict"
        )

        long_text = "x" * 50_000
        description = api_client.post(
            rules,
            json=rule(
                fields[1]["id"],
                "description",
                2,
                transformation_type="CONSTANT",
                default_value=long_text,
                validation_rule=long_text,
            ),
        )
        assert description.status_code == 201, description.text
        assert description.json()["default_value"] == long_text

        partial = api_client.patch(
            f"{rules}/{sku_rule['id']}",
            json={
                "optimistic_version": sku_rule["optimistic_version"],
                "required": True,
            },
        )
        assert partial.status_code == 200
        assert partial.json()["required"] is True
        stale = api_client.patch(
            f"{rules}/{sku_rule['id']}",
            json={
                "optimistic_version": sku_rule["optimistic_version"],
                "required": False,
            },
        )
        assert stale.status_code == 409

        profile = api_client.get(f"{root}/{profile['id']}").json()
        activated = api_client.post(
            f"{root}/{profile['id']}/activate",
            json={"optimistic_version": profile["optimistic_version"]},
        )
        assert activated.status_code == 200, activated.text
        active = activated.json()

        immutable = api_client.patch(
            f"{rules}/{sku_rule['id']}",
            json={
                "optimistic_version": partial.json()["optimistic_version"],
                "required": False,
            },
        )
        assert immutable.status_code == 409
        assert immutable.json()["code"] == "mapping_profile_immutable"

        clone_response = api_client.post(
            f"{root}/{profile['id']}/clone",
            json={"optimistic_version": active["optimistic_version"]},
        )
        assert clone_response.status_code == 201, clone_response.text
        clone = clone_response.json()
        assert clone["version_number"] == 2
        assert api_client.get(f"{root}/{clone['id']}/rules").json()["total"] == 2
        activated_clone = api_client.post(
            f"{root}/{clone['id']}/activate",
            json={"optimistic_version": clone["optimistic_version"]},
        )
        assert activated_clone.status_code == 200
        assert api_client.get(f"{root}/{profile['id']}").json()["status"] == "ARCHIVED"

        assert api_client.delete(f"{root}/{clone['id']}").status_code == 204
        assert api_client.get(root, params={"status": "ACTIVE"}).json()["total"] == 0
        archived = api_client.get(root, params={"active_only": "false"}).json()
        assert any(item["id"] == clone["id"] for item in archived["items"])
    finally:
        asyncio.run(purge(supplier_id))


def test_mapping_validation_permissions_and_schema_integration(
    api_client: httpx.Client,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id, source_id, schema, fields = setup_active_schema(api_client, suffix)
    root = (
        f"/suppliers/{supplier_id}/sources/{source_id}/schema-profiles/"
        f"{schema['id']}/mapping-profiles"
    )
    try:
        invalid = api_client.post(
            root,
            json={"name": f"Invalid mapping {suffix}"},
        ).json()
        rules = f"{root}/{invalid['id']}/rules"
        missing_config = api_client.post(
            rules,
            json=rule(
                fields[0]["id"],
                "product_code",
                1,
                transformation_type="REGEX",
            ),
        )
        assert missing_config.status_code == 422
        wrong_field = api_client.post(
            rules,
            json=rule(str(uuid.uuid4()), "ean", 2),
        )
        assert wrong_field.status_code == 404

        with httpx.Client(
            base_url=API_ROOT,
            timeout=20.0,
            headers=bearer("mapping-editor", "mapping_profile_editor"),
        ) as editor:
            assert editor.get(root).status_code == 200
            denied = editor.post(
                f"{root}/{invalid['id']}/activate",
                json={"optimistic_version": invalid["optimistic_version"]},
            )
            assert denied.status_code == 403
        with httpx.Client(
            base_url=API_ROOT,
            timeout=20.0,
            headers=bearer("mapping-activator", "mapping_profile_activator"),
        ) as activator:
            assert activator.get(root).status_code == 200
            assert activator.post(root, json={"name": "Denied"}).status_code == 403

        valid_rule = api_client.post(
            rules,
            json=rule(fields[0]["id"], "product_code", 1),
        )
        assert valid_rule.status_code == 201
        invalid = api_client.get(f"{root}/{invalid['id']}").json()
        activated = api_client.post(
            f"{root}/{invalid['id']}/activate",
            json={"optimistic_version": invalid["optimistic_version"]},
        )
        assert activated.status_code == 200

        schema_root = f"/suppliers/{supplier_id}/sources/{source_id}/schema-profiles"
        clone_schema = api_client.post(
            f"{schema_root}/{schema['id']}/clone",
            json={"version": schema["version"]},
        ).json()
        activated_schema = api_client.post(
            f"{schema_root}/{clone_schema['id']}/activate",
            json={"version": clone_schema["version"]},
        )
        assert activated_schema.status_code == 200, activated_schema.text
        assert api_client.get(f"{root}/{invalid['id']}").json()["status"] == "ARCHIVED"
        blocked = api_client.post(root, json={"name": "Inactive schema mapping"})
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "mapping_profile_schema_inactive"
    finally:
        asyncio.run(purge(supplier_id))
