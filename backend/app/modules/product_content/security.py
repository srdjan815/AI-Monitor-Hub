from __future__ import annotations

import html
import re
from typing import Any

import bleach

from app.modules.product_content.constants import ConditionComparator

VARIABLE_PATTERN = re.compile(r"\{\{([A-Za-z][A-Za-z0-9_]*)\}\}")
MALFORMED_VARIABLE_PATTERN = re.compile(r"\{\{.*?\}\}", re.DOTALL)


def sanitize_preview(source: str) -> str:
    return bleach.clean(
        source,
        tags={
            "a",
            "b",
            "blockquote",
            "br",
            "code",
            "div",
            "em",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "hr",
            "i",
            "li",
            "ol",
            "p",
            "pre",
            "span",
            "strong",
            "table",
            "tbody",
            "td",
            "th",
            "thead",
            "tr",
            "ul",
        },
        attributes={"a": ["href", "title"], "*": ["class"]},
        protocols={"http", "https", "mailto"},
        strip=True,
        strip_comments=True,
    )


def interpolate_variables(
    source: str,
    values: dict[str, Any],
    *,
    trusted_raw: bool = False,
) -> tuple[str, list[str], list[str]]:
    recognized_tokens = VARIABLE_PATTERN.findall(source)
    all_tokens = MALFORMED_VARIABLE_PATTERN.findall(source)
    malformed = sorted(
        token for token in all_tokens if VARIABLE_PATTERN.fullmatch(token) is None
    )
    unknown = sorted({name for name in recognized_tokens if name not in values})

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            return match.group(0)
        value = str(values[name])
        return value if trusted_raw else html.escape(value, quote=True)

    return VARIABLE_PATTERN.sub(replace, source), unknown, malformed


def compare_values(
    comparator: str,
    actual: Any,
    expected: str | None,
) -> bool:
    try:
        operator = ConditionComparator(comparator)
    except ValueError:
        return False
    if operator is ConditionComparator.EXISTS:
        return actual not in (None, "")
    if operator in (ConditionComparator.EQ, ConditionComparator.NE):
        equal = str(actual) == expected
        return equal if operator is ConditionComparator.EQ else not equal
    if expected is None:
        return False
    try:
        left = float(actual)
        right = float(expected)
    except (TypeError, ValueError):
        return False
    return {
        ConditionComparator.GT: left > right,
        ConditionComparator.GE: left >= right,
        ConditionComparator.LT: left < right,
        ConditionComparator.LE: left <= right,
    }[operator]
