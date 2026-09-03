from __future__ import annotations

import imaplib
import re
import ssl
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser

from app.modules.suppliers.acquisition_contracts import AcquisitionFailure


def latest_asbis_attachment(
    config: dict[str, object], username: str, password: str, maximum_bytes: int
) -> tuple[str, bytes]:
    context = ssl.create_default_context()
    if bool(config.get("imap_allow_legacy_dh", False)):
        context.set_ciphers("DEFAULT:@SECLEVEL=1")
    try:
        client = imaplib.IMAP4_SSL(
            str(config["imap_host"]),
            int(str(config.get("imap_port", 993))),
            ssl_context=context,
        )
    except ssl.SSLError as exc:
        raise AcquisitionFailure(
            "acquisition_asbis_imap_tls_failed",
            "ASBIS IMAP TLS veza nije uspostavljena; proverite sertifikat i TLS kompatibilnost mail servera",
        ) from exc
    except (OSError, TypeError, ValueError) as exc:
        raise AcquisitionFailure(
            "acquisition_asbis_imap_unavailable",
            "ASBIS IMAP server nije dostupan na podešenoj adresi i portu",
        ) from exc
    try:
        with client:
            try:
                client.login(username, password)
            except imaplib.IMAP4.error as exc:
                raise AcquisitionFailure(
                    "acquisition_asbis_imap_authentication_failed",
                    "ASBIS IMAP prijava nije uspela; proverite korisničko ime i lozinku",
                ) from exc
            status, _ = client.select(
                str(config.get("imap_folder", "INBOX")), readonly=True
            )
            if status != "OK":
                raise AcquisitionFailure(
                    "acquisition_asbis_imap_folder_failed",
                    "ASBIS IMAP prijava je uspela, ali podešeni folder nije dostupan",
                )
            for message_id in _newest_message_ids(client, _search(client, config)):
                attachment = _attachment(client, message_id, config, maximum_bytes)
                if attachment is not None:
                    return attachment
    except AcquisitionFailure:
        raise
    except (imaplib.IMAP4.error, OSError, TypeError, ValueError) as exc:
        raise AcquisitionFailure(
            "acquisition_asbis_imap_operation_failed",
            "ASBIS IMAP veza i prijava su uspele, ali čitanje sandučeta nije uspelo",
        ) from exc
    raise AcquisitionFailure(
        "acquisition_asbis_attachment_missing",
        "Nije pronađen odgovarajući ASBIS ZIP prilog",
    )


def _search(client: imaplib.IMAP4_SSL, config: dict[str, object]) -> list[str]:
    hours = int(str(config.get("imap_received_within_hours", 720)))
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%d-%b-%Y")
    status, data = client.search(
        None,
        "SINCE",
        since,
        "SUBJECT",
        f'"{config.get("imap_subject_filter", "ASBIS")}"',
    )
    if status != "OK" or not data:
        raise ValueError("search")
    return [value.decode("ascii") for value in data[0].split()]


def _newest_message_ids(
    client: imaplib.IMAP4_SSL, message_ids: list[str]
) -> list[str]:
    """Order candidates by server receipt time, never by mailbox listing order."""
    ranked: list[tuple[bool, datetime, int, str]] = []
    for message_id in message_ids:
        received_at = _internal_date(client, message_id)
        try:
            numeric_id = int(message_id)
        except ValueError:
            numeric_id = -1
        ranked.append(
            (
                received_at is not None,
                received_at or datetime.min.replace(tzinfo=timezone.utc),
                numeric_id,
                message_id,
            )
        )
    ranked.sort(reverse=True)
    return [item[3] for item in ranked]


def _internal_date(
    client: imaplib.IMAP4_SSL, message_id: str
) -> datetime | None:
    status, parts = client.fetch(message_id, "(INTERNALDATE)")
    if status != "OK" or not parts:
        return None
    for part in parts:
        raw = part if isinstance(part, bytes) else str(part).encode()
        match = re.search(rb'INTERNALDATE "([^"]+)"', raw)
        if match is None:
            continue
        try:
            return datetime.strptime(
                match.group(1).decode("ascii"), "%d-%b-%Y %H:%M:%S %z"
            ).astimezone(timezone.utc)
        except (UnicodeDecodeError, ValueError):
            continue
    return None


def _attachment(
    client: imaplib.IMAP4_SSL,
    message_id: str,
    config: dict[str, object],
    maximum_bytes: int,
) -> tuple[str, bytes] | None:
    status, sizes = client.fetch(message_id, "(RFC822.SIZE)")
    if status != "OK" or not sizes:
        return None
    size = _message_size(sizes)
    if size is not None and size > maximum_bytes * 2:
        return None
    status, parts = client.fetch(message_id, "(RFC822)")
    if status != "OK":
        return None
    raw = next((part[1] for part in parts if isinstance(part, tuple)), None)
    if not isinstance(raw, bytes) or len(raw) > maximum_bytes * 2:
        return None
    message = BytesParser(policy=policy.default).parsebytes(raw)
    sender = str(config.get("imap_sender_filter") or "").strip().casefold()
    if sender and sender not in str(message.get("From", "")).casefold():
        return None
    prefix = str(
        config.get("imap_attachment_prefix", "HTML, PO actions, in mail body")
    ).casefold()
    for part in message.iter_attachments():
        name = part.get_filename() or ""
        if not (
            name.casefold().startswith(prefix) and name.casefold().endswith(".zip")
        ):
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue
        if len(payload) > maximum_bytes:
            raise AcquisitionFailure(
                "acquisition_artifact_too_large",
                "ASBIS email prilog prelazi dozvoljenu veličinu",
            )
        return name, payload
    return None


def _message_size(parts: Sequence[object]) -> int | None:
    for part in parts:
        text = part.decode(errors="ignore") if isinstance(part, bytes) else str(part)
        marker = "RFC822.SIZE "
        if marker in text:
            value = text.split(marker, 1)[1].split(")", 1)[0].strip()
            if value.isdigit():
                return int(value)
    return None


__all__ = ["latest_asbis_attachment"]
