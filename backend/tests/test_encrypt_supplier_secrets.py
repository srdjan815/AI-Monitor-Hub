from __future__ import annotations

import json

import pytest
from cryptography.fernet import Fernet

from scripts.encrypt_supplier_secrets import encrypt_store


def test_encrypt_store_preserves_references_and_source(tmp_path) -> None:
    source = tmp_path / "supplier-secrets.json"
    destination = tmp_path / "supplier-secrets.enc"
    records = {"secret:supplier/fixed": {"portal:password": "hidden"}}
    source.write_text(json.dumps(records), encoding="utf-8")
    key = Fernet.generate_key()

    encrypt_store(source, destination, key.decode("ascii"))

    assert json.loads(source.read_text(encoding="utf-8")) == records
    assert json.loads(Fernet(key).decrypt(destination.read_bytes())) == records
    assert b"hidden" not in destination.read_bytes()


def test_encrypt_store_never_overwrites_destination(tmp_path) -> None:
    source = tmp_path / "source.json"
    destination = tmp_path / "destination.enc"
    source.write_text("{}", encoding="utf-8")
    destination.write_bytes(b"keep")

    with pytest.raises(FileExistsError):
        encrypt_store(source, destination, Fernet.generate_key().decode("ascii"))
    assert destination.read_bytes() == b"keep"
