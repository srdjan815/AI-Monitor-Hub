from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import cast

import regex
from defusedxml import ElementTree  # type: ignore[import-untyped]


class CurrencyRateParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedRate:
    value: Decimal
    excerpt: str
    method_used: str


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not self.hidden_depth and value:
            self.parts.append(value)


class _SimpleSelectorParser(HTMLParser):
    def __init__(self, selector: str) -> None:
        super().__init__(convert_charrefs=True)
        self.selector = selector
        self.depth = 0
        self.capture_depth: int | None = None
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        values = dict(attrs)
        if self.capture_depth is None and _matches(tag, values, self.selector):
            self.capture_depth = self.depth

    def handle_endtag(self, tag: str) -> None:
        if self.capture_depth == self.depth:
            self.capture_depth = None
        self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.capture_depth is not None:
            self.parts.append(data)


def _matches(tag: str, attrs: dict[str, str | None], selector: str) -> bool:
    if any(token in selector for token in (" ", ">", "[", ":", ",")):
        raise CurrencyRateParseError("Podržan je jedan jednostavan CSS selektor")
    wanted_tag = selector
    wanted_id = None
    wanted_class = None
    if "#" in selector:
        wanted_tag, wanted_id = selector.split("#", 1)
    elif "." in selector:
        wanted_tag, wanted_class = selector.split(".", 1)
    if wanted_tag and tag.lower() != wanted_tag.lower():
        return False
    if wanted_id and attrs.get("id") != wanted_id:
        return False
    classes = (attrs.get("class") or "").split()
    return not wanted_class or wanted_class in classes


def _extract(content: str, method: str, expression: str) -> str:
    try:
        if method == "JSON_PATH":
            value: object = json.loads(content)
            path = expression.removeprefix("$").lstrip(".")
            for part in path.split(".") if path else []:
                if isinstance(value, list) and part.isdigit():
                    value = value[int(part)]
                elif isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    raise CurrencyRateParseError("JSON putanja nije pronađena")
            return str(value)
        if method == "CSS_SELECTOR":
            parser = _SimpleSelectorParser(expression)
            parser.feed(content)
            if not parser.parts:
                raise CurrencyRateParseError("CSS selektor nije pronađen")
            return " ".join(parser.parts)
        if method == "XPATH":
            if ".." in expression or expression.startswith("/"):
                raise CurrencyRateParseError("XPath mora biti relativan")
            node = ElementTree.fromstring(content).find(expression)
            if node is None:
                raise CurrencyRateParseError("XPath nije pronađen")
            return " ".join(node.itertext())
        if method == "REGEX":
            match = regex.search(expression, content, timeout=0.05)
            if match is None:
                raise CurrencyRateParseError("Obrazac nije pronađen")
            return match.group(1) if match.lastindex else match.group(0)
        if method == "TEXT_LABEL":
            text_parser = _VisibleTextParser()
            text_parser.feed(content)
            label = " ".join(expression.split()).rstrip(":").casefold()
            candidates: list[str] = []
            for index, part in enumerate(text_parser.parts):
                normalized = part.rstrip(":").casefold()
                if normalized == label and index + 1 < len(text_parser.parts):
                    candidates.append(f"{part}: {text_parser.parts[index + 1]}")
                elif normalized.startswith(f"{label}:"):
                    candidates.append(part)
            if len(candidates) != 1:
                raise CurrencyRateParseError(
                    "Tekstualna oznaka mora biti pronađena tačno jednom"
                )
            return candidates[0]
    except (
        json.JSONDecodeError,
        ElementTree.ParseError,
        regex.error,
        TimeoutError,
    ) as exc:
        raise CurrencyRateParseError(
            "Odgovor izvora nije moguće bezbedno obraditi"
        ) from exc
    raise CurrencyRateParseError("Nepoznat način pronalaženja kursa")


def parse_rate(
    content: bytes,
    method: str,
    expression: str,
    separator: str,
    fallback_method: str | None = None,
    fallback_expression: str | None = None,
) -> ParsedRate:
    text = content.decode("utf-8", errors="replace")
    method_used = method
    try:
        raw = " ".join(_extract(text, method, expression).split())
    except CurrencyRateParseError:
        if not fallback_method or not fallback_expression:
            raise
        raw = " ".join(_extract(text, fallback_method, fallback_expression).split())
        method_used = fallback_method
    match = regex.search(r"[-+]?\d(?:[\d.,\s]*\d)?", raw, timeout=0.05)
    if match is None:
        raise CurrencyRateParseError("Pronađena vrednost ne sadrži broj")
    number = match.group(0).replace(" ", "")
    thousands = "," if separator == "." else "."
    normalized = number.replace(thousands, "").replace(separator, ".")
    try:
        value = Decimal(normalized)
    except InvalidOperation as exc:
        raise CurrencyRateParseError("Kurs nije ispravan decimalni broj") from exc
    if not value.is_finite() or value <= 0 or value.adjusted() > 11:
        raise CurrencyRateParseError("Kurs mora biti pozitivan i u dozvoljenom opsegu")
    exponent = cast(int, value.as_tuple().exponent)
    if max(0, -exponent) > 8:
        raise CurrencyRateParseError("Kurs može imati najviše osam decimala")
    return ParsedRate(value=value, excerpt=raw[:1000], method_used=method_used)


__all__ = ["CurrencyRateParseError", "ParsedRate", "parse_rate"]
