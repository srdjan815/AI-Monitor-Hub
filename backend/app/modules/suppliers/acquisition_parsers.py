from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from xml.etree import ElementTree

from app.modules.suppliers.acquisition_contracts import (
    AcquisitionFailure,
    Parser,
)


class CsvParser:
    def parse(
        self,
        content: bytes,
        configuration: dict[str, object],
    ) -> list[dict[str, object]]:
        encoding = str(configuration.get("encoding", "utf-8"))
        try:
            text = content.decode(encoding)
            reader = csv.DictReader(
                io.StringIO(text, newline=""),
                delimiter=str(configuration.get("delimiter", ",")),
                quotechar=str(configuration.get("quote_character", '"')),
                strict=True,
            )
            if not reader.fieldnames or any(not name for name in reader.fieldnames):
                raise ValueError("missing header")
            rows = [dict(row) for row in reader]
            if any(None in row for row in rows):
                raise ValueError("malformed row")
            return rows
        except (LookupError, UnicodeError, csv.Error, ValueError) as exc:
            raise AcquisitionFailure(
                "acquisition_csv_malformed",
                "CSV sadržaj nije ispravan",
            ) from exc


class JsonParser:
    def parse(
        self,
        content: bytes,
        configuration: dict[str, object],
    ) -> list[dict[str, object]]:
        try:
            value = json.loads(content.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise AcquisitionFailure(
                "acquisition_json_malformed",
                "JSON sadržaj nije ispravan",
            ) from exc
        if isinstance(value, dict):
            for key in ("items", "products", "records", "data"):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    value = candidate
                    break
            else:
                value = [value]
        if not isinstance(value, list) or not all(
            isinstance(row, dict) for row in value
        ):
            raise AcquisitionFailure(
                "acquisition_json_shape_invalid",
                "JSON mora sadržati listu objekata",
            )
        return [dict(row) for row in value]


class XmlParser:
    def parse(
        self,
        content: bytes,
        configuration: dict[str, object],
    ) -> list[dict[str, object]]:
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
        item_path = str(configuration.get("item_path") or "").strip()
        tag = item_path.rstrip("/").split("/")[-1] if item_path else ""
        if not tag:
            raise AcquisitionFailure(
                "acquisition_xml_path_invalid",
                "XML item_path nije konfigurisan",
            )
        items = [
            element for element in root.iter() if self._local_name(element.tag) == tag
        ]
        return [self._record(item) for item in items]

    @classmethod
    def _record(cls, element: ElementTree.Element) -> dict[str, object]:
        record: dict[str, object] = {}
        for child in list(element):
            key = cls._local_name(child.tag)
            if list(child):
                record[key] = {
                    cls._local_name(grandchild.tag): grandchild.text or ""
                    for grandchild in list(child)
                }
            else:
                record[key] = child.text or ""
        return record

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]


class XlsxParser:
    _CELL = re.compile(r"([A-Z]+)(\d+)")

    def parse(
        self,
        content: bytes,
        configuration: dict[str, object],
    ) -> list[dict[str, object]]:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                self._safe_archive(archive)
                shared = self._shared_strings(archive)
                sheet_path = self._sheet_path(archive, configuration)
                rows = self._rows(archive.read(sheet_path), shared)
        except (
            KeyError,
            ValueError,
            zipfile.BadZipFile,
            ElementTree.ParseError,
        ) as exc:
            raise AcquisitionFailure(
                "acquisition_excel_malformed",
                "Excel sadržaj nije ispravan ili podržan",
            ) from exc
        header_row = int(str(configuration.get("header_row", 1)))
        data_start = int(str(configuration.get("data_start_row", header_row + 1)))
        headers = rows.get(header_row, [])
        if not headers or any(not str(value).strip() for value in headers):
            raise AcquisitionFailure(
                "acquisition_excel_header_invalid",
                "Excel zaglavlje nije ispravno",
            )
        result: list[dict[str, object]] = []
        for number in sorted(row for row in rows if row >= data_start):
            values = rows[number]
            result.append(
                {
                    str(header): values[index] if index < len(values) else ""
                    for index, header in enumerate(headers)
                }
            )
        return result

    @staticmethod
    def _safe_archive(archive: zipfile.ZipFile) -> None:
        if len(archive.infolist()) > 10_000:
            raise ValueError("too many entries")
        if sum(item.file_size for item in archive.infolist()) > 256 * 1024 * 1024:
            raise ValueError("expanded workbook too large")

    @staticmethod
    def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
        try:
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        except KeyError:
            return []
        return ["".join(node.itertext()) for node in root]

    @staticmethod
    def _sheet_path(
        archive: zipfile.ZipFile,
        configuration: dict[str, object],
    ) -> str:
        requested = configuration.get("sheet_name")
        if requested:
            workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            relationships = ElementTree.fromstring(
                archive.read("xl/_rels/workbook.xml.rels")
            )
            relation_map = {
                relation.attrib["Id"]: relation.attrib["Target"]
                for relation in relationships
            }
            for sheet in workbook.iter():
                if (
                    sheet.tag.endswith("sheet")
                    and sheet.attrib.get("name") == requested
                ):
                    relation_id = next(
                        value
                        for key, value in sheet.attrib.items()
                        if key.endswith("}id")
                    )
                    return f"xl/{relation_map[relation_id].lstrip('/')}"
            raise ValueError("sheet not found")
        sheets = sorted(
            name
            for name in archive.namelist()
            if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
        )
        if not sheets:
            raise ValueError("worksheet missing")
        return sheets[0]

    @classmethod
    def _rows(cls, content: bytes, shared: list[str]) -> dict[int, list[object]]:
        root = ElementTree.fromstring(content)
        rows: dict[int, list[object]] = {}
        for row in (node for node in root.iter() if node.tag.endswith("}row")):
            number = int(row.attrib["r"])
            values: list[object] = []
            for cell in (node for node in row if node.tag.endswith("}c")):
                match = cls._CELL.fullmatch(cell.attrib["r"])
                if match is None:
                    continue
                index = cls._column_index(match.group(1))
                while len(values) <= index:
                    values.append("")
                if any(child.tag.endswith("}f") for child in cell):
                    values[index] = ""
                    continue
                if cell.attrib.get("t") == "inlineStr":
                    values[index] = "".join(
                        child.text or ""
                        for child in cell.iter()
                        if child.tag.endswith("}t")
                    )
                    continue
                value = next(
                    (child.text or "" for child in cell if child.tag.endswith("}v")),
                    "",
                )
                values[index] = (
                    shared[int(value)] if cell.attrib.get("t") == "s" else value
                )
            rows[number] = values
        return rows

    @staticmethod
    def _column_index(letters: str) -> int:
        value = 0
        for letter in letters:
            value = value * 26 + ord(letter) - ord("A") + 1
        return value - 1


class ParserRegistry:
    def __init__(self) -> None:
        self.parsers: dict[str, Parser] = {
            "CSV": CsvParser(),
            "EXCEL": XlsxParser(),
            "XML": XmlParser(),
            "JSON": JsonParser(),
        }

    def resolve(
        self,
        source_type: str,
        content_type: str | None,
        filename: str | None,
        configuration: dict[str, object],
    ) -> Parser:
        kind = self._kind(source_type, content_type, filename, configuration)
        parser = self.parsers.get(kind)
        if parser is None:
            raise AcquisitionFailure(
                "acquisition_format_unsupported",
                "Format ulaznog sadržaja nije podržan",
            )
        return parser

    @staticmethod
    def _kind(
        source_type: str,
        content_type: str | None,
        filename: str | None,
        configuration: dict[str, object],
    ) -> str:
        if source_type in {"CSV", "EXCEL", "XML"}:
            return source_type
        lowered = (filename or "").lower()
        media = (content_type or "").lower()
        if lowered.endswith(".csv") or "csv" in media:
            return "CSV"
        if lowered.endswith(".xlsx") or "spreadsheet" in media:
            return "EXCEL"
        if lowered.endswith(".xml") or "xml" in media:
            return "XML"
        if (
            lowered.endswith(".json")
            or "json" in media
            or source_type in {"API", "HTTP"}
        ):
            return "JSON"
        accepted = configuration.get("accepted_file_types")
        if isinstance(accepted, list) and len(accepted) == 1:
            return str(accepted[0])
        return ""


__all__ = ["ParserRegistry"]
