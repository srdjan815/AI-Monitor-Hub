from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, time
from decimal import Decimal
from typing import cast
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.currency_models import (
    SupplierCurrencyEvent,
    SupplierCurrencySetting,
    SupplierExchangeRate,
)
from app.modules.suppliers.currency_rate_http import (
    CurrencyRateFetchError,
    fetch_rate_document,
)
from app.modules.suppliers.currency_rate_parser import (
    CurrencyRateParseError,
    parse_rate,
)
from app.modules.suppliers.currency_schemas import (
    CurrencySourceTestRead,
    CurrencySourceTestRequest,
)
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.models import Supplier, SupplierSource


class CurrencyPreflightError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True)
class CurrencyPreflightResult:
    status: str
    rate: SupplierExchangeRate | None


def next_daily_check(check_time: time, after: datetime | None = None) -> datetime:
    current = (after or datetime.now(UTC)).astimezone(ZoneInfo("Europe/Belgrade"))
    candidate = current.replace(
        hour=check_time.hour, minute=check_time.minute, second=0, microsecond=0
    )
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC)


class SupplierCurrencyAutomationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _setting(
        self, supplier_id: uuid.UUID, lock: bool = False
    ) -> SupplierCurrencySetting | None:
        query = select(SupplierCurrencySetting).where(
            SupplierCurrencySetting.supplier_id == supplier_id,
            SupplierCurrencySetting.is_active.is_(True),
        )
        if lock:
            query = query.with_for_update()
        return cast(SupplierCurrencySetting | None, await self.session.scalar(query))

    async def _latest(
        self, setting_id: uuid.UUID, at: datetime | None = None
    ) -> SupplierExchangeRate | None:
        query = select(SupplierExchangeRate).where(
            SupplierExchangeRate.currency_setting_id == setting_id,
            SupplierExchangeRate.status == "VERIFIED",
        )
        if at:
            query = query.where(SupplierExchangeRate.effective_at <= at)
        return cast(
            SupplierExchangeRate | None,
            await self.session.scalar(
                query.order_by(
                    SupplierExchangeRate.effective_at.desc(),
                    SupplierExchangeRate.id.desc(),
                ).limit(1)
            ),
        )

    async def test_source(
        self, supplier_id: uuid.UUID, payload: CurrencySourceTestRequest
    ) -> CurrencySourceTestRead:
        if await self.session.get(Supplier, supplier_id) is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        try:
            source = await self._source(supplier_id, payload.source_connection_id)
            document = await fetch_rate_document(
                self._resolved_url(str(payload.source_url), source)
            )
            parsed = parse_rate(
                document.content,
                payload.extraction_method,
                payload.extraction_expression,
                payload.decimal_separator,
            )
        except (
            CurrencyPreflightError,
            CurrencyRateFetchError,
            CurrencyRateParseError,
        ) as exc:
            supplier_error(422, "currency_source_test_failed", str(exc))
        setting = await self._setting(supplier_id)
        previous = await self._latest(setting.id) if setting else None
        difference = (
            None
            if not previous
            else (
                (parsed.value - previous.rate_to_rsd) / previous.rate_to_rsd * 100
            ).quantize(Decimal("0.01"))
        )
        return CurrencySourceTestRead(
            rate_to_rsd=parsed.value,
            fetched_at=datetime.now(UTC),
            source_excerpt=parsed.excerpt,
            evidence_checksum=document.checksum,
            content_type=document.content_type,
            previous_rate=previous.rate_to_rsd if previous else None,
            difference_percent=difference,
        )

    async def _source(
        self, supplier_id: uuid.UUID, source_id: uuid.UUID
    ) -> SupplierSource:
        source = await self.session.scalar(
            select(SupplierSource).where(
                SupplierSource.id == source_id,
                SupplierSource.supplier_id == supplier_id,
                SupplierSource.is_active.is_(True),
                SupplierSource.status == "ACTIVE",
            )
        )
        if source is None:
            raise CurrencyPreflightError(
                "KONFIGURACIJA_KURSA_NEISPRAVNA",
                "Konekcija kursa nije aktivna ili ne pripada dobavljaču",
            )
        return source

    @staticmethod
    def _resolved_url(url: str, source: SupplierSource) -> str:
        placeholder = "{supplier_code}"
        encoded_placeholder = "%7Bsupplier_code%7D"
        if placeholder not in url and encoded_placeholder.lower() not in url.lower():
            return url
        if not source.portal_supplier_code:
            raise CurrencyPreflightError(
                "KONFIGURACIJA_KURSA_NEISPRAVNA",
                "Konekcija nema podešenu partnersku šifru dobavljača",
            )
        encoded = quote(source.portal_supplier_code, safe="")
        return (
            url.replace(placeholder, encoded)
            .replace(encoded_placeholder, encoded)
            .replace(encoded_placeholder.lower(), encoded)
        )

    async def refresh(
        self, supplier_id: uuid.UUID, source_id: uuid.UUID | None = None
    ) -> SupplierExchangeRate:
        setting = await self._setting(supplier_id, lock=True)
        if not setting or setting.rate_mode != "AUTOMATIC":
            raise ValueError("Automatsko podešavanje valute nije aktivno")
        if not setting.automatic_source_url or not setting.extraction_expression:
            raise ValueError("Automatski izvor nije kompletno podešen")
        if setting.source_connection_id is None:
            raise CurrencyPreflightError(
                "KONFIGURACIJA_KURSA_NEISPRAVNA",
                "Automatski kurs nema povezanu konekciju cenovnika",
            )
        if source_id is not None and setting.source_connection_id != source_id:
            raise CurrencyPreflightError(
                "KONFIGURACIJA_KURSA_NEISPRAVNA",
                "Kurs je povezan sa drugom konekcijom cenovnika",
            )
        source = await self._source(supplier_id, setting.source_connection_id)
        checked_at = datetime.now(UTC)
        try:
            document = await fetch_rate_document(
                self._resolved_url(setting.automatic_source_url, source)
            )
            parsed = parse_rate(
                document.content,
                setting.extraction_method,
                setting.extraction_expression,
                setting.decimal_separator,
            )
            previous = await self._latest(setting.id, checked_at)
            if previous and not Decimal(
                "0.8"
            ) <= parsed.value / previous.rate_to_rsd <= Decimal("1.2"):
                raise ValueError("Promena kursa veća od 20% zahteva ručnu proveru")
            rate = SupplierExchangeRate(
                currency_setting_id=setting.id,
                rate_to_rsd=parsed.value,
                effective_at=checked_at,
                status="VERIFIED",
                source_type="AUTOMATIC",
                evidence_checksum=document.checksum,
                source_excerpt=parsed.excerpt,
                source_content_type=document.content_type,
                note=f"Automatski preuzeto sa {setting.automatic_source_url}",
                created_by="currency-scheduler",
            )
            self.session.add(rate)
            await self.session.flush()
            setting.last_check_status = "SUCCESS"
            setting.last_check_message = "Kurs je uspešno osvežen"
            event = SupplierCurrencyEvent(
                supplier_id=supplier_id,
                currency_setting_id=setting.id,
                exchange_rate_id=rate.id,
                action="AUTOMATIC_RATE_ADDED",
                actor_id="currency-scheduler",
                details=document.checksum,
            )
        except Exception as exc:
            setting.last_check_status = "FAILED"
            setting.last_check_message = str(exc)[:500]
            event = SupplierCurrencyEvent(
                supplier_id=supplier_id,
                currency_setting_id=setting.id,
                action="AUTOMATIC_RATE_FAILED",
                actor_id="currency-scheduler",
                details=str(exc)[:2000],
            )
            self.session.add(event)
            setting.last_check_at = checked_at
            setting.next_check_at = next_daily_check(
                setting.daily_check_time, checked_at
            )
            await self.session.commit()
            raise
        self.session.add(event)
        setting.last_check_at = checked_at
        setting.next_check_at = next_daily_check(setting.daily_check_time, checked_at)
        setting.version += 1
        await self.session.commit()
        await self.session.refresh(rate)
        return rate

    async def preflight(self, source: SupplierSource) -> CurrencyPreflightResult:
        setting = await self._setting(source.supplier_id)
        if setting is None or setting.currency_code == "RSD":
            rate = await self._latest(setting.id) if setting else None
            return CurrencyPreflightResult("KURS_NIJE_POTREBAN", rate)
        if setting.source_connection_id != source.id:
            raise CurrencyPreflightError(
                "KONFIGURACIJA_KURSA_NEISPRAVNA",
                "Podešavanje kursa nije vezano za ovu konekciju cenovnika",
            )
        if setting.rate_mode == "AUTOMATIC":
            try:
                rate = await self.refresh(source.supplier_id, source.id)
            except CurrencyPreflightError:
                raise
            except (CurrencyRateFetchError, CurrencyRateParseError) as exc:
                raise CurrencyPreflightError(
                    "IZVOR_KURSA_NEDOSTUPAN", str(exc)
                ) from exc
            except ValueError as exc:
                code = (
                    "KURS_SUMNJIVA_PROMENA"
                    if "20%" in str(exc)
                    else "KONFIGURACIJA_KURSA_NEISPRAVNA"
                )
                raise CurrencyPreflightError(code, str(exc)) from exc
            return CurrencyPreflightResult("KURS_PREUZET", rate)
        rate = await self._latest(setting.id)
        if rate is None:
            raise CurrencyPreflightError("KURS_NEDOSTAJE", "Nema unetog kursa")
        if datetime.now(UTC) - rate.effective_at > timedelta(
            hours=setting.max_rate_age_hours
        ):
            raise CurrencyPreflightError("KURS_ZASTAREO", "Kurs je zastareo")
        return CurrencyPreflightResult("KURS_POSLEDNJI_VAŽEĆI", rate)


__all__ = [
    "CurrencyPreflightError",
    "CurrencyPreflightResult",
    "SupplierCurrencyAutomationService",
    "next_daily_check",
]
