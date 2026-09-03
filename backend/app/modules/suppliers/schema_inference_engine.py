from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
)
from app.modules.suppliers.acquisition_parsers import JsonParser, XlsxParser


@dataclass
class DetectedStructure:
    detected_format: str
    rows: list[dict[str, object]]
    record_count: int
    encoding: str | None = None
    delimiter: str | None = None
    header_row: int | None = None
    root_path: str | None = None
    item_path: str | None = None


class SchemaStructureDetector:
    @classmethod
    def detect(
        cls,
        payload: AcquiredPayload,
        *,
        row_limit: int | None = 100,
    ) -> DetectedStructure:
        content = payload.content
        media = (payload.content_type or "").lower()
        filename = (payload.original_filename or "").lower()
        stripped = content.lstrip()
        if "html" in media or stripped[:100].lower().startswith(
            (b"<!doctype html", b"<html")
        ):
            raise AcquisitionFailure(
                "acquisition_unexpected_html",
                "Dobavljač je vratio HTML stranicu umesto cenovnika",
            )
        if content.startswith(b"PK") or filename.endswith(".xlsx"):
            return cls._xlsx(content, row_limit=row_limit)
        if stripped.startswith(b"<") or "xml" in media or filename.endswith(".xml"):
            return cls._xml(content, row_limit=row_limit)
        if stripped.startswith((b"{", b"[")) or "json" in media:
            return cls._nonempty(
                "JSON", JsonParser().parse(content, {}), row_limit=row_limit
            )
        return cls._csv(content, row_limit=row_limit)

    @classmethod
    def _csv(
        cls, content: bytes, *, row_limit: int | None
    ) -> DetectedStructure:
        encoding, text = cls._decode(content)
        lines = text.splitlines()
        try:
            dialect = csv.Sniffer().sniff(
                "\n".join(lines[:50]),
                delimiters=",;\t|",
            )
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = max(
                ",;\t|",
                key=lambda candidate: max(
                    (line.count(candidate) for line in lines[:50]),
                    default=0,
                ),
            )
            if not any(delimiter in line for line in lines[:50]):
                raise AcquisitionFailure(
                    "schema_inference_csv_dialect",
                    "Nije moguće prepoznati CSV separator",
                )
        header_row = cls._header_row(lines, delimiter)
        reader = csv.DictReader(
            io.StringIO("\n".join(lines[header_row - 1 :])),
            delimiter=delimiter,
        )
        structure = cls._nonempty(
            "CSV", [dict(row) for row in reader], row_limit=row_limit
        )
        structure.encoding = encoding
        structure.delimiter = delimiter
        structure.header_row = header_row
        return structure

    @staticmethod
    def _decode(content: bytes) -> tuple[str, str]:
        for encoding in ("utf-8-sig", "utf-8", "cp1250"):
            try:
                return encoding, content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return "iso-8859-1", content.decode("iso-8859-1")

    @staticmethod
    def _header_row(lines: list[str], delimiter: str) -> int:
        for index, line in enumerate(lines[:20], 1):
            values = next(csv.reader([line], delimiter=delimiter), [])
            if (
                len(values) > 1
                and all(value.strip() for value in values)
                and len({value.strip().lower() for value in values}) == len(values)
            ):
                return index
        raise AcquisitionFailure(
            "schema_inference_header_missing",
            "Nije pronađen red zaglavlja",
        )

    @classmethod
    def _xlsx(
        cls, content: bytes, *, row_limit: int | None
    ) -> DetectedStructure:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                XlsxParser._safe_archive(archive)
                shared = XlsxParser._shared_strings(archive)
                zero_widths = XlsxParser._zero_padded_widths(archive)
                path = XlsxParser._sheet_path(archive, {})
                raw = XlsxParser._rows_with_formats(
                    archive.read(path), shared, zero_widths
                )
        except (
            ElementTree.ParseError,
            KeyError,
            ValueError,
            zipfile.BadZipFile,
        ) as exc:
            raise AcquisitionFailure(
                "acquisition_excel_malformed",
                "Excel sadržaj nije ispravan ili podržan",
            ) from exc
        header_row = next(
            (
                number
                for number in sorted(raw)[:20]
                if len(raw[number]) > 1
                and all(str(value).strip() for value in raw[number])
            ),
            None,
        )
        if header_row is None:
            raise AcquisitionFailure(
                "schema_inference_header_missing",
                "Nije pronađen Excel red zaglavlja",
            )
        structure = cls._nonempty(
            "EXCEL",
            XlsxParser().parse(
                content,
                {"header_row": header_row, "data_start_row": header_row + 1},
            ),
            row_limit=row_limit,
        )
        structure.header_row = header_row
        return structure

    @classmethod
    def _xml(
        cls, content: bytes, *, row_limit: int | None
    ) -> DetectedStructure:
        probe = content[:4096].upper()
        if b"<!DOCTYPE" in probe or b"<!ENTITY" in probe:
            raise AcquisitionFailure(
                "acquisition_xml_unsafe",
                "XML DTD i entiteti nisu dozvoljeni",
            )
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as exc:
            raise AcquisitionFailure(
                "acquisition_xml_malformed",
                "XML sadržaj nije ispravan",
            ) from exc
        groups: dict[str, list[ElementTree.Element]] = {}
        for element in root.iter():
            groups.setdefault(cls._local(element.tag), []).append(element)
        candidates = [
            (name, elements)
            for name, elements in groups.items()
            if len(elements) > 1 and any(list(element) for element in elements)
        ]
        if not candidates:
            raise AcquisitionFailure(
                "schema_inference_xml_items_missing",
                "Nije pronađena ponavljajuća XML stavka",
            )
        item_name, items = max(candidates, key=lambda item: len(item[1]))
        rows: list[dict[str, object]] = [
            {
                cls._local(child.tag): (
                    "".join(child.itertext()).strip()
                    if list(child)
                    else child.text or ""
                )
                for child in list(item)
            }
            for item in items
        ]
        structure = cls._nonempty("XML", rows, row_limit=row_limit)
        structure.root_path = f"/{cls._local(root.tag)}"
        structure.item_path = f"//{item_name}"
        return structure

    @staticmethod
    def _local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _nonempty(
        kind: str,
        rows: list[dict[str, object]],
        *,
        row_limit: int | None,
    ) -> DetectedStructure:
        if not rows or not any(row for row in rows):
            raise AcquisitionFailure(
                "schema_inference_no_records",
                "U cenovniku nisu pronađeni zapisi",
            )
        return DetectedStructure(
            kind,
            rows if row_limit is None else rows[:row_limit],
            len(rows),
        )


__all__ = ["DetectedStructure", "SchemaStructureDetector"]
