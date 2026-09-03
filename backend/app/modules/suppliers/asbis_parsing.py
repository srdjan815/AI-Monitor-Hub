from __future__ import annotations

import zipfile
from collections import Counter
from html.parser import HTMLParser
from io import BytesIO
from pathlib import PurePath
from urllib.parse import urlsplit
from xml.etree import ElementTree

from app.modules.suppliers.acquisition_contracts import AcquisitionFailure

CODE_NAMES = {
    "productcode",
    "product_code",
    "code",
    "sku",
    "partnumber",
    "part_number",
    "vendorpartno",
    "productid",
    "wic",
    "asbis_product_code",
}


def html_from_zip(content: bytes, maximum_bytes: int) -> bytes:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            candidates = [
                item
                for item in archive.infolist()
                if not item.is_dir()
                and PurePath(item.filename).suffix.casefold() in {".html", ".htm"}
            ]
            if not candidates:
                raise ValueError("html")
            item = max(candidates, key=lambda entry: entry.file_size)
            if item.file_size > maximum_bytes or (
                item.compress_size > 0 and item.file_size > item.compress_size * 200
            ):
                raise AcquisitionFailure(
                    "acquisition_artifact_too_large",
                    "ASBIS HTML u prilogu prelazi dozvoljenu veličinu",
                )
            return archive.read(item)
    except AcquisitionFailure:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise AcquisitionFailure(
            "acquisition_asbis_zip_invalid",
            "ASBIS prilog nije ispravan ZIP sa HTML cenovnikom",
        ) from exc


def xml_records(content: bytes, feed: str) -> list[dict[str, object]]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise AcquisitionFailure(
            f"acquisition_asbis_{feed}_xml_invalid",
            f"ASBIS {feed} odgovor nije ispravan XML",
        ) from exc
    expected_tag = "Product" if feed == "catalog" else "PRICE"
    candidates = [
        item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == expected_tag
    ]
    if not candidates:
        candidates = [
            item
            for item in root.iter()
            if len(item) >= 2 and all(len(child) == 0 for child in item)
        ]
    if not candidates:
        raise AcquisitionFailure(
            f"acquisition_asbis_{feed}_empty",
            f"ASBIS {feed} odgovor ne sadrži artikle",
        )
    tag = Counter(item.tag for item in candidates).most_common(1)[0][0]
    return [_xml_record(item, feed) for item in candidates if item.tag == tag]


def _xml_record(item: ElementTree.Element, feed: str) -> dict[str, object]:
    record: dict[str, object] = {
        child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
        for child in item
        if len(child) == 0
    }
    if feed != "catalog":
        return record
    attributes: dict[str, str] = {}
    image_urls: list[str] = []
    for child in item:
        name = child.tag.rsplit("}", 1)[-1]
        if name == "AttrList":
            for element in child:
                attribute_name = (element.attrib.get("Name") or "").strip()
                attribute_value = (element.attrib.get("Value") or "").strip()
                if attribute_name:
                    attributes[attribute_name] = attribute_value
                    record[f"ATTR_{attribute_name}"] = attribute_value
        elif name == "Images":
            image_urls.extend(
                value for element in child if (value := (element.text or "").strip())
            )
    primary_image = str(record.get("Image", "")).strip()
    if primary_image:
        record["PRIMARY_IMAGE_URL"] = primary_image
    if attributes:
        record["ATTRIBUTES"] = attributes
    if image_urls:
        unique_images = list(dict.fromkeys(image_urls))
        record["IMAGE_URLS"] = unique_images
        for position, image_url in enumerate(unique_images, start=1):
            record[f"IMAGE_URL_{position}"] = image_url
    return record


def product_code(row: dict[str, object]) -> str:
    for key, value in row.items():
        if key.casefold().replace("-", "_") in CODE_NAMES and str(value).strip():
            return str(value).strip()
    return ""


def normalize_product_code(value: str) -> str:
    return "".join(value.split()).casefold()


class ActionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, object]] = []
        self.row: dict[str, object] | None = None
        self.cell = -1
        self.anchor = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "tr" and "tddiv" in (values.get("class") or "").split():
            self.row, self.cell = {}, -1
        elif self.row is not None and tag == "td":
            self.cell += 1
        elif self.row is not None and tag == "a" and self.cell == 0:
            self.anchor = True
        elif (
            self.row is not None
            and tag == "input"
            and (values.get("name") or "").startswith("PRICE_LST_")
        ):
            self.row["PROMOTION_PRICE"] = values.get("value") or ""
        elif self.row is not None and tag == "img" and self.cell == 1:
            filename = PurePath(urlsplit(values.get("src") or "").path).name
            marker = (
                PurePath(filename).stem.strip().upper()
                if filename.casefold().endswith(".gif")
                else ""
            )
            if marker:
                notes = self.row.setdefault("NOTES_LIST", [])
                if isinstance(notes, list) and marker not in notes:
                    notes.append(marker)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.anchor = False
        elif tag == "tr" and self.row is not None:
            notes = self.row.pop("NOTES_LIST", [])
            if isinstance(notes, list) and notes:
                self.row["NOTES"] = ", ".join(str(note) for note in notes)
            if self.row.get("ASBIS_PRODUCT_CODE") and self.row.get("PROMOTION_PRICE"):
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value or self.row is None:
            return
        if self.anchor:
            self.row["ASBIS_PRODUCT_CODE"] = value
        fields = {
            1: "PROMOTION_DESCRIPTION",
            2: "PROMOTION_CONDITION",
            3: "PROMOTION_WARRANTY",
            4: "PROMOTION_WAREHOUSE",
            5: "PROMOTION_STOCK",
            6: "PROMOTION_RETAIL_PRICE",
        }
        if self.cell in fields:
            key = fields[self.cell]
            self.row[key] = f"{self.row.get(key, '')} {value}".strip()


def action_records(content: bytes) -> list[dict[str, object]]:
    decoded = ""
    for encoding in ("utf-8", "windows-1250", "latin-1"):
        try:
            decoded = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    parser = ActionParser()
    parser.feed(decoded)
    return parser.rows


__all__ = [
    "action_records",
    "html_from_zip",
    "normalize_product_code",
    "product_code",
    "xml_records",
]
