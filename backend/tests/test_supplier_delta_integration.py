from __future__ import annotations

import asyncio
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.suppliers.snapshot_fingerprints import (
    item_fingerprint,
    payload_checksum,
    snapshot_fingerprint,
)
from app.modules.suppliers.snapshot_models import SupplierSnapshot, SupplierSnapshotItem
from tests.test_supplier_snapshot_integration import (
    API_ROOT, _csv_payload, _headers, _pipeline, _purge,
)


async def _shape(snapshot_id: str, *, current: bool, long_text: str) -> None:
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        snapshot = await session.get(SupplierSnapshot, uuid.UUID(snapshot_id))
        assert snapshot is not None
        items = list(await session.scalars(select(SupplierSnapshotItem).where(SupplierSnapshotItem.snapshot_id == snapshot.id).order_by(SupplierSnapshotItem.record_number)))
        for position, item in enumerate(items, 1):
            code = f"SKU-00{position}"
            if current and position == 3:
                code = "SKU-004"
            item.source_key = code
            data = dict(item.mapped_data)
            data["product_code"] = code
            data["price"] = {"SKU-001": "55.00" if current else "50.00", "SKU-002": "100.00", "SKU-003": "200.00", "SKU-004": "300.00"}[code]
            data["stock"] = {"SKU-001": 0 if current else 10, "SKU-002": 5, "SKU-003": 1, "SKU-004": 4}[code]
            if code == "SKU-001":
                data["name"] = "Gaming Mouse"
                data["description"] = long_text + (" PROMENA" if current else "")
                item.source_image_links = [
                    {"url": "https://img.test/image-a.jpg", "role": "GALLERY"},
                    {"url": f"https://img.test/{'image-c' if current else 'image-b'}.jpg", "role": "GALLERY"},
                ]
            item.mapped_data = data
            item.item_fingerprint = item_fingerprint(data, item.source_image_links, item.source_key, item.source_identifier)
        snapshot.snapshot_fingerprint = snapshot_fingerprint(
            item_fingerprints=[item.item_fingerprint for item in items],
            supplier_id=snapshot.supplier_id, source_id=snapshot.source_connection_id,
            acquisition_run_id=snapshot.acquisition_run_id,
            schema_version=snapshot.schema_version_reference,
            mapping_version=snapshot.mapping_version_reference,
        )
        snapshot.payload_checksum = payload_checksum([
            {
                "record_number": item.record_number,
                "item_fingerprint": item.item_fingerprint,
                "mapped_data": item.mapped_data,
                "source_image_links": item.source_image_links,
            }
            for item in items
        ])
        await session.commit()
    await engine.dispose()


def test_supplier_delta_real_snapshot_cycle() -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id = ""
    long_text = "Unicode čćž <p>HTML</p>\nviše redova " * 3000
    with httpx.Client(base_url=API_ROOT, headers=_headers(), timeout=60) as client:
        try:
            supplier_id, source_id, root = _pipeline(client, suffix)
            snapshots_root = f"{root}/snapshots"
            snapshot_ids: list[str] = []
            for index in range(2):
                run = client.post(
                    f"{root}/acquisitions/upload",
                    params={"filename": f"delta-{index}.csv"},
                    headers={"Content-Type": "text/csv"},
                    content=_csv_payload(long_text),
                )
                assert run.status_code == 201, run.text
                snapshot = client.post(snapshots_root, json={"acquisition_run_id": run.json()["id"]})
                assert snapshot.status_code == 201, snapshot.text
                snapshot_ids.append(snapshot.json()["id"])
            asyncio.run(_shape(snapshot_ids[0], current=False, long_text=long_text))
            asyncio.run(_shape(snapshot_ids[1], current=True, long_text=long_text))
            products_before = client.get("/products").json()["total"]
            endpoint = f"{root}/deltas"
            response = client.post(endpoint, json={"previous_snapshot_id": snapshot_ids[0], "current_snapshot_id": snapshot_ids[1], "idempotency_key": suffix})
            assert response.status_code == 201, response.text
            delta = response.json()
            assert delta["status"] == "SUCCEEDED"
            assert (delta["added_items"], delta["removed_items"], delta["modified_items"], delta["unchanged_items"]) == (1, 1, 1, 1)
            assert delta["price_increased_items"] == 1
            assert delta["became_unavailable_items"] == 1
            assert delta["image_changed_items"] == 1
            repeated = client.post(endpoint, json={"previous_snapshot_id": snapshot_ids[0], "current_snapshot_id": snapshot_ids[1]})
            assert repeated.json()["id"] == delta["id"]
            changed = client.get(f"{endpoint}/{delta['id']}/items", params={"change_type": "MODIFIED"}).json()["items"][0]
            fields = client.get(f"{endpoint}/{delta['id']}/items/{changed['id']}/field-changes").json()["items"]
            description = next(field for field in fields if field["field_path"] == "description")
            assert description["previous_value_hash"] != description["current_value_hash"]
            assert len(description["previous_value_preview"]) <= 240
            assert long_text not in str(fields)
            exported = client.post(f"{snapshots_root}/{snapshot_ids[0]}/archive", json={"include_source_artifact": False}).json()
            offloaded = client.post(f"{snapshots_root}/{snapshot_ids[0]}/offload", json={"operation_id": exported["id"], "archive_reference": exported["archive_reference"], "archive_checksum": exported["archive_checksum"]})
            assert offloaded.status_code == 200
            archived = client.get(f"{endpoint}/compatibility", params={"previous_snapshot_id": snapshot_ids[0], "current_snapshot_id": snapshot_ids[1]})
            assert archived.status_code == 409
            assert archived.json()["code"] == "SNAPSHOT_RESTORATION_REQUIRED"
            assert client.get("/products").json()["total"] == products_before
        finally:
            if supplier_id:
                asyncio.run(_purge(supplier_id))
