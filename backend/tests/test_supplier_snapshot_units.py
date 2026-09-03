from __future__ import annotations

import hashlib
import json
import uuid
import zipfile
from pathlib import Path

import pytest

from app.modules.suppliers.snapshot_archive_format import SnapshotArchiveFormat
from app.modules.suppliers.snapshot_archive_storage import (
    LocalSnapshotArchiveStorage,
)
from app.modules.suppliers.snapshot_contracts import (
    SnapshotFailure,
    SnapshotItemPayload,
)
from app.modules.suppliers.snapshot_fingerprints import (
    item_fingerprint,
    snapshot_fingerprint,
)
from app.modules.suppliers.snapshot_images import extract_image_links


def test_fingerprints_are_canonical_and_content_sensitive() -> None:
    links = [{"url": "https://images.test/a.jpg", "position": 0}]
    first = item_fingerprint({"b": 2, "a": "č"}, links, "key", "id")
    reordered = item_fingerprint({"a": "č", "b": 2}, links, "key", "id")
    changed = item_fingerprint({"a": "č", "b": 3}, links, "key", "id")
    changed_links = item_fingerprint(
        {"a": "č", "b": 2},
        [{"url": "https://images.test/b.jpg", "position": 0}],
        "key",
        "id",
    )
    assert first == reordered
    assert first != changed
    assert first != changed_links
    identity = {
        "item_fingerprints": [first],
        "supplier_id": uuid.uuid4(),
        "source_id": uuid.uuid4(),
        "acquisition_run_id": uuid.uuid4(),
        "schema_version": 1,
        "mapping_version": 2,
    }
    assert snapshot_fingerprint(**identity) == snapshot_fingerprint(**identity)


def test_image_links_preserve_order_deduplicate_and_reject_dangerous_schemes() -> None:
    mapped = {
        "primary_image_url": "https://images.test/manual-photo.jpg",
        "image_urls": [
            "https://images.test/a.jpg",
            "https://images.test/a.jpg",
            "javascript:alert(1)",
            {"url": "https://images.test/b.jpg", "role": "gallery", "position": 9},
        ],
        "gallery_images": "file:///etc/passwd",
    }
    links = extract_image_links(mapped)
    assert [link["url"] for link in links] == [
        "https://images.test/a.jpg",
        "https://images.test/b.jpg",
        "https://images.test/manual-photo.jpg",
    ]
    assert links[1]["role"] == "gallery"
    assert links[1]["position"] == 9
    assert links[2]["role"] == "primary"


def _archive_payload(
    long_text: str,
) -> tuple[dict[str, object], list[SnapshotItemPayload]]:
    snapshot_id = str(uuid.uuid4())
    snapshot = {
        "id": snapshot_id,
        "snapshot_code": "SNP-000001",
        "supplier_id": str(uuid.uuid4()),
        "source_connection_id": str(uuid.uuid4()),
        "acquisition_run_id": str(uuid.uuid4()),
        "schema_profile_id": str(uuid.uuid4()),
        "mapping_profile_id": str(uuid.uuid4()),
        "schema_version_reference": 1,
        "mapping_version_reference": 1,
        "snapshot_fingerprint": "a" * 64,
        "payload_checksum": "b" * 64,
        "total_items": 1,
    }
    item = SnapshotItemPayload(
        id=str(uuid.uuid4()),
        source_staged_record_id=str(uuid.uuid4()),
        record_number=1,
        source_key="A-1",
        source_identifier="860000000001",
        item_fingerprint="c" * 64,
        mapped_data={"description": long_text},
        source_image_links=[
            {
                "url": "https://images.test/manual.jpg",
                "source_attribute": "image_url",
                "position": 0,
            }
        ],
    )
    return snapshot, [item]


def test_archive_round_trip_preserves_long_text_and_image_links(tmp_path: Path) -> None:
    long_text = "Unicode čćž\n<html>opis</html>\n" + ("dugačak opis " * 4000)
    snapshot, items = _archive_payload(long_text)
    storage = LocalSnapshotArchiveStorage(tmp_path, 10 * 1024 * 1024)
    temporary, destination = storage.allocate("SNP-000001")
    SnapshotArchiveFormat().write(
        temporary,
        snapshot=snapshot,
        items=items,
        item_count=1,
    )
    stored = storage.finalize(temporary, destination)
    assert stored.checksum == hashlib.sha256(stored.path.read_bytes()).hexdigest()
    SnapshotArchiveFormat().verify(
        stored.path,
        expected_snapshot_id=str(snapshot["id"]),
        expected_fingerprint="a" * 64,
        expected_item_count=1,
    )
    restored = list(SnapshotArchiveFormat().iter_items(stored.path))
    assert restored[0].mapped_data["description"] == long_text
    assert restored[0].source_image_links == items[0].source_image_links


def test_archive_storage_rejects_traversal_and_archive_rejects_zip_slip(
    tmp_path: Path,
) -> None:
    storage = LocalSnapshotArchiveStorage(tmp_path, 10 * 1024 * 1024)
    with pytest.raises(SnapshotFailure):
        storage.resolve("../outside.zip")
    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../manifest.json", json.dumps({}))
    with pytest.raises(SnapshotFailure) as error:
        SnapshotArchiveFormat().verify(
            unsafe,
            expected_snapshot_id=str(uuid.uuid4()),
            expected_fingerprint="a" * 64,
            expected_item_count=0,
        )
    assert error.value.code == "snapshot_archive_path_unsafe"


def test_corrupted_and_wrong_identity_archives_are_rejected(tmp_path: Path) -> None:
    snapshot, items = _archive_payload("opis")
    path = tmp_path / "snapshot.zip"
    SnapshotArchiveFormat().write(
        path,
        snapshot=snapshot,
        items=items,
        item_count=1,
    )
    with pytest.raises(SnapshotFailure) as wrong:
        SnapshotArchiveFormat().verify(
            path,
            expected_snapshot_id=str(uuid.uuid4()),
            expected_fingerprint="a" * 64,
            expected_item_count=1,
        )
    assert wrong.value.code == "snapshot_archive_identity_mismatch"
    path.write_bytes(path.read_bytes()[:50])
    with pytest.raises(SnapshotFailure) as corrupt:
        SnapshotArchiveFormat().verify(
            path,
            expected_snapshot_id=str(snapshot["id"]),
            expected_fingerprint="a" * 64,
            expected_item_count=1,
        )
    assert corrupt.value.code == "snapshot_archive_invalid"
