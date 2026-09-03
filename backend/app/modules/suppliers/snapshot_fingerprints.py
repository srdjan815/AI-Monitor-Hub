from __future__ import annotations

import hashlib
import json
import uuid


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def item_fingerprint(
    mapped_data: dict[str, object],
    image_links: list[dict[str, object]],
    source_key: str | None,
    source_identifier: str | None,
) -> str:
    payload = {
        "mapped_data": mapped_data,
        "source_image_links": image_links,
        "source_identifier": source_identifier,
        "source_key": source_key,
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def snapshot_fingerprint(
    *,
    item_fingerprints: list[str],
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    acquisition_run_id: uuid.UUID,
    schema_version: int,
    mapping_version: int,
) -> str:
    payload = {
        "acquisition_run_id": str(acquisition_run_id),
        "item_fingerprints": sorted(item_fingerprints),
        "mapping_version": mapping_version,
        "schema_version": schema_version,
        "source_id": str(source_id),
        "supplier_id": str(supplier_id),
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def payload_checksum(items: list[dict[str, object]]) -> str:
    return hashlib.sha256(canonical_json(items)).hexdigest()


__all__ = [
    "canonical_json",
    "item_fingerprint",
    "payload_checksum",
    "snapshot_fingerprint",
]
