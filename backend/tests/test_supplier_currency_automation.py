from __future__ import annotations

import socket
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.modules.suppliers.currency_automation_service import (
    CurrencyPreflightError,
    SupplierCurrencyAutomationService,
)
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


def test_text_label_selects_exact_business_rate() -> None:
    content = b"""
        <section><span>Kurs odlozeno:</span><strong>123.4</strong></section>
        <section><span>Kurs avans:</span><strong>118.7</strong></section>
    """
    parsed = parse_rate(content, "TEXT_LABEL", "Kurs avans", ".")
    assert parsed.value == Decimal("118.7")
    assert parsed.method_used == "TEXT_LABEL"


def test_text_label_rejects_ambiguous_matches() -> None:
    content = b"<p>Kurs avans: 118.7</p><p>Kurs avans: 119.0</p>"
    with pytest.raises(CurrencyRateParseError, match="tačno jednom"):
        parse_rate(content, "TEXT_LABEL", "Kurs avans", ".")


def test_parser_uses_configured_fallback_only_after_primary_failure() -> None:
    parsed = parse_rate(
        b"<span>Kurs avans:</span><b>118.7</b>",
        "CSS_SELECTOR",
        "span#missing",
        ".",
        "TEXT_LABEL",
        "Kurs avans",
    )
    assert parsed.value == Decimal("118.7")
    assert parsed.method_used == "TEXT_LABEL"


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
        source_connection_id=uuid.uuid4(),
        currency_code="EUR",
        rate_mode="AUTOMATIC",
        automatic_source_url="https://example.com/rate",
        extraction_method="JSON_PATH",
        extraction_expression="$.rate",
    )
    assert value.currency_code == "EUR"


def test_portal_supplier_code_is_safely_inserted() -> None:
    source = SimpleNamespace(portal_supplier_code="PARTNER/42")
    resolved = SupplierCurrencyAutomationService._resolved_url(
        "https://example.com/rate?partner=%7Bsupplier_code%7D", source
    )
    assert resolved.endswith("partner=PARTNER%2F42")


@pytest.mark.asyncio
async def test_pipeline_preflight_rejects_wrong_source() -> None:
    service = SupplierCurrencyAutomationService(AsyncMock())
    service._setting = AsyncMock(
        return_value=SimpleNamespace(
            currency_code="EUR",
            source_connection_id=uuid.uuid4(),
            rate_mode="MANUAL",
        )
    )
    source = SimpleNamespace(id=uuid.uuid4(), supplier_id=uuid.uuid4())
    with pytest.raises(CurrencyPreflightError) as captured:
        await service.preflight(source)
    assert captured.value.code == "KONFIGURACIJA_KURSA_NEISPRAVNA"


@pytest.mark.asyncio
async def test_pipeline_preflight_rejects_stale_manual_rate() -> None:
    source_id = uuid.uuid4()
    service = SupplierCurrencyAutomationService(AsyncMock())
    service._setting = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            currency_code="EUR",
            source_connection_id=source_id,
            rate_mode="MANUAL",
            max_rate_age_hours=24,
        )
    )
    service._latest = AsyncMock(
        return_value=SimpleNamespace(
            effective_at=datetime.now(UTC) - timedelta(hours=25)
        )
    )
    source = SimpleNamespace(id=source_id, supplier_id=uuid.uuid4())
    with pytest.raises(CurrencyPreflightError) as captured:
        await service.preflight(source)
    assert captured.value.code == "KURS_ZASTAREO"
