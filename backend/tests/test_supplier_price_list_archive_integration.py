from __future__ import annotations

import asyncio
import uuid

import httpx

from tests.test_supplier_snapshot_integration import (
    API_ROOT,
    _csv_payload,
    _headers,
    _pipeline,
    _purge,
)


def test_supplier_price_list_archive_lists_import_and_reads_items_without_mutation() -> (
    None
):
    suffix = uuid.uuid4().hex[:12]
    supplier_id = ""
    with httpx.Client(base_url=API_ROOT, headers=_headers(), timeout=60) as client:
        try:
            supplier_id, source_id, source_root = _pipeline(client, suffix)
            payload = _csv_payload("Arhivirani opis")
            acquisition = client.post(
                f"{source_root}/acquisitions/upload",
                params={"filename": "archive.csv"},
                headers={"Content-Type": "text/csv"},
                content=payload,
            )
            assert acquisition.status_code == 201, acquisition.text
            assert acquisition.json()["status"] == "SUCCEEDED"

            filters = client.get("/price-list-archive/filters")
            assert filters.status_code == 200, filters.text
            assert any(
                item["id"] == supplier_id for item in filters.json()["suppliers"]
            )
            assert any(item["id"] == source_id for item in filters.json()["sources"])

            archive = client.get(
                "/price-list-archive",
                params={"supplier_id": supplier_id, "source_id": source_id},
            )
            assert archive.status_code == 200, archive.text
            assert archive.json()["total"] == 1
            entry = archive.json()["items"][0]
            assert entry["supplier_id"] == supplier_id
            assert entry["source_connection_id"] == source_id
            assert entry["storage_status"] == "LOCAL"
            assert entry["checksum_sha256"]

            items = client.get(
                f"/price-list-archive/{entry['acquisition_run_id']}/items",
                params={"search": "A-1", "validation_status": "ACCEPTED"},
            )
            assert items.status_code == 200, items.text
            assert items.json()["total"] == 1
            item = items.json()["items"][0]
            assert item["product_code"] == "A-1"
            assert item["mapped_data"]["product_code"] == "A-1"
            assert item["raw_data"]

            original = client.get(
                f"/price-list-archive/{entry['acquisition_run_id']}/original"
            )
            assert original.status_code == 200, original.text
            assert original.content == payload
            assert original.headers["x-content-sha256"] == entry["checksum_sha256"]
            assert "archive.csv" in original.headers["content-disposition"]

            repeated = client.get(
                f"/price-list-archive/{entry['acquisition_run_id']}/items",
                params={"search": "A-1", "validation_status": "ACCEPTED"},
            )
            assert repeated.json() == items.json()

            missing = client.get(f"/price-list-archive/{uuid.uuid4()}/items")
            assert missing.status_code == 404
            missing_original = client.get(
                f"/price-list-archive/{uuid.uuid4()}/original"
            )
            assert missing_original.status_code == 404
        finally:
            if supplier_id:
                asyncio.run(_purge(supplier_id))
