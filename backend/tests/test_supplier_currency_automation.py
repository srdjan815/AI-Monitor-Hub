from __future__ import annotations

import socket
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.suppliers.currency_rate_http import (
    CurrencyRateFetchError,
    _validate_url,
)
from app.modules.suppliers.currency_rate_parser import (
    CurrencyRateParseError,
    parse_rate,
)
from app.modules.suppliers.currency_schemas import CurrencySettingWrite


@pytest.mark.parametrize(
    ("content", "method", "expression", "separator", "expected"),
    [
        (
            b'{"data":{"rate":"117.35"}}',
            "JSON_PATH",
            "$.data.rate",
            ".",
            Decimal("117.35"),
        ),
        (
            b'<span id="kurs">117,35</span>',
            "CSS_SELECTOR",
            "span#kurs",
            ",",
            Decimal("117.35"),
        ),
        (b"<root><rate>117.35</rate></root>", "XPATH", "rate", ".", Decimal("117.35")),
        (b"Kurs: 117,35 RSD", "REGEX", r"Kurs:\s*([\d,]+)", ",", Decimal("117.35")),
    ],
)
def test_parse_supported_source_formats(
    content, method, expression, separator, expected
) -> None:
    assert parse_rate(content, method, expression, separator).value == expected


def test_parser_rejects_invalid_or_overprecise_rate() -> None:
    with pytest.raises(CurrencyRateParseError):
        parse_rate(b'{"rate":"0"}', "JSON_PATH", "$.rate", ".")
    with pytest.raises(CurrencyRateParseError):
        parse_rate(b'{"rate":"1.123456789"}', "JSON_PATH", "$.rate", ".")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/rate",
        "https://user:pass@example.com/rate",
        "https://example.com:8443/rate",
    ],
)
async def test_secure_fetch_rejects_unsafe_url_shape(url: str) -> None:
    with pytest.raises(CurrencyRateFetchError):
        await _validate_url(url)


@pytest.mark.asyncio
async def test_secure_fetch_rejects_private_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )
    with pytest.raises(CurrencyRateFetchError):
        await _validate_url("https://rates.example.test/value")


def test_currency_mode_contract() -> None:
    with pytest.raises(ValidationError):
        CurrencySettingWrite(currency_code="EUR", rate_mode="FIXED")
    with pytest.raises(ValidationError):
        CurrencySettingWrite(
            currency_code="EUR",
            rate_mode="AUTOMATIC",
            automatic_source_url="https://example.com",
        )
    value = CurrencySettingWrite(
        currency_code="EUR",
        rate_mode="AUTOMATIC",
        automatic_source_url="https://example.com/rate",
        extraction_method="JSON_PATH",
        extraction_expression="$.rate",
    )
    assert value.currency_code == "EUR"
