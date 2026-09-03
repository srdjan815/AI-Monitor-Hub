"""One-time, non-destructive migration of supplier secrets to encrypted storage."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet


def encrypt_store(source: Path, destination: Path, key: str) -> None:
    if source.resolve() == destination.resolve():
        raise ValueError("Izvor i odredište moraju biti različiti fajlovi")
    if destination.exists():
        raise FileExistsError("Odredišni fajl već postoji; neće biti prepisan")
    records = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(records, dict):
        raise ValueError("Izvorni secret store mora sadržati JSON objekat")
    cipher = Fernet(key.encode("ascii"))
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(cipher.encrypt(payload))
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Šifruje postojeći supplier secret JSON bez izmene izvora."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    key = os.environ.get("SUPPLIER_SECRETS_KEY", "").strip()
    if not key:
        raise SystemExit("SUPPLIER_SECRETS_KEY nije podešen")
    encrypt_store(args.source, args.destination, key)
    print(f"Kreiran je šifrovani store: {args.destination}")
    print("Izvorni fajl nije izmenjen niti obrisan.")


if __name__ == "__main__":
    main()
