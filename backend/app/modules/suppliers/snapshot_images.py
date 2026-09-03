from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import settings

IMAGE_ATTRIBUTES = (
    "image_url",
    "image_urls",
    "primary_image_url",
    "gallery_images",
    "additional_images",
    "product_images",
)


def extract_image_links(mapped: dict[str, object]) -> list[dict[str, object]]:
    links: list[dict[str, object]] = []
    seen: set[str] = set()
    for attribute in IMAGE_ATTRIBUTES:
        if attribute not in mapped:
            continue
        for position, candidate in enumerate(_values(mapped[attribute])):
            normalized = _normalize(candidate, attribute, position)
            if normalized is None:
                continue
            url = str(normalized["url"])
            if url in seen:
                continue
            seen.add(url)
            links.append(normalized)
    return links


def _values(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return [value]


def _normalize(
    value: object,
    attribute: str,
    position: int,
) -> dict[str, object] | None:
    role: str | None = None
    supplier_position: int | None = None
    if isinstance(value, dict):
        raw_url = value.get("url")
        role_value = value.get("role")
        position_value = value.get("position")
        role = str(role_value)[:100] if role_value is not None else None
        if isinstance(position_value, int):
            supplier_position = position_value
    else:
        raw_url = value
    if not isinstance(raw_url, str):
        return None
    url = raw_url.strip()
    parsed = urlparse(url)
    if (
        not url
        or len(url) > settings.snapshot_image_url_max_length
        or parsed.scheme.lower() not in {"http", "https"}
        or not parsed.netloc
    ):
        return None
    result: dict[str, object] = {
        "url": url,
        "position": supplier_position if supplier_position is not None else position,
        "source_attribute": attribute,
        "original_supplier_value": raw_url,
    }
    if role:
        result["role"] = role
    elif attribute == "primary_image_url":
        result["role"] = "primary"
    return result


__all__ = ["IMAGE_ATTRIBUTES", "extract_image_links"]
