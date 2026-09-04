from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

from sqlalchemy import ColumnElement, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_actor_id
from app.modules.suppliers.currency_automation_service import next_daily_check
from app.modules.suppliers.currency_contracts import SnapshotCurrencyPlan
from app.modules.suppliers.currency_snapshot_policy import build_snapshot_currency_plan
from app.modules.suppliers.currency_models import (
    MonitorCurrencySetting,
    SupplierCurrencyEvent,
    SupplierCurrencySetting,
    SupplierExchangeRate,
)
from app.modules.suppliers.currency_presenters import currency_setting_read
from app.modules.suppliers.currency_rate_policy import require_trusted_automatic_rate
from app.modules.suppliers.currency_schemas import (
    CurrencyEventRead,
    CurrencyEventList,
    CurrencySettingList,
    CurrencySettingRead,
    CurrencySettingWrite,
    ExchangeRateCreate,
)
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.models import Supplier


class SupplierCurrencyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def monitor(self) -> MonitorCurrencySetting:
        value = await self.session.scalar(select(MonitorCurrencySetting))
        if value is None:
            supplier_error(
                500, "monitor_currency_missing", "Monitor valuta nije inicijalizovana"
            )
        return value

    async def active_setting(
        self, supplier_id: uuid.UUID, *, lock: bool = False
    ) -> SupplierCurrencySetting | None:
        query = select(SupplierCurrencySetting).where(
            SupplierCurrencySetting.supplier_id == supplier_id,
            SupplierCurrencySetting.is_active.is_(True),
        )
        if lock:
            query = query.with_for_update()
        return cast(SupplierCurrencySetting | None, await self.session.scalar(query))

    async def latest_rate(
        self, setting_id: uuid.UUID, at: datetime | None = None
    ) -> SupplierExchangeRate | None:
        query = select(SupplierExchangeRate).where(
            SupplierExchangeRate.currency_setting_id == setting_id,
            SupplierExchangeRate.status == "VERIFIED",
        )
        if at is not None:
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

    async def list_settings(
        self, *, supplier_id: uuid.UUID | None = None
    ) -> CurrencySettingList:
        filters: list[ColumnElement[bool]] = [
            SupplierCurrencySetting.is_active.is_(True)
        ]
        if supplier_id:
            filters.append(SupplierCurrencySetting.supplier_id == supplier_id)
        rows = (
            await self.session.execute(
                select(SupplierCurrencySetting, Supplier.company_name)
                .join(Supplier)
                .where(*filters)
                .order_by(Supplier.company_name, SupplierCurrencySetting.id)
            )
        ).all()
        items: list[CurrencySettingRead] = []
        now = datetime.now(UTC)
        for setting, name in rows:
            rate = await self.latest_rate(setting.id, now)
            status = "MISSING"
            if rate:
                status = (
                    "CURRENT"
                    if setting.currency_code == "RSD"
                    or now - rate.effective_at
                    <= timedelta(hours=setting.max_rate_age_hours)
                    else "STALE"
                )
            items.append(currency_setting_read(setting, name, rate, status))
        return CurrencySettingList(items=items, total=len(items))

    async def upsert(
        self, supplier_id: uuid.UUID, payload: CurrencySettingWrite
    ) -> CurrencySettingRead:
        supplier = await self.session.scalar(
            select(Supplier).where(
                Supplier.id == supplier_id, Supplier.is_active.is_(True)
            )
        )
        if supplier is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        setting = await self.active_setting(supplier_id, lock=True)
        if setting and (
            payload.expected_version is None
            or payload.expected_version != setting.version
        ):
            supplier_error(
                409,
                "currency_setting_stale",
                "Podešavanje je u međuvremenu promenjeno; osvežite stranicu",
            )
        actor = current_actor_id() or "system"
        if setting is None:
            setting = SupplierCurrencySetting(
                supplier_id=supplier_id,
                currency_code=payload.currency_code,
                currency_source=payload.currency_source,
                rate_mode=payload.rate_mode,
                automatic_source_url=(
                    str(payload.automatic_source_url)
                    if payload.automatic_source_url
                    else None
                ),
                extraction_method=payload.extraction_method,
                extraction_expression=payload.extraction_expression,
                decimal_separator=payload.decimal_separator,
                daily_check_time=payload.daily_check_time,
                max_rate_age_hours=payload.max_rate_age_hours,
            )
            self.session.add(setting)
            await self.session.flush()
            action = "SETTING_CREATED"
        else:
            setting.currency_code = payload.currency_code
            setting.currency_source = payload.currency_source
            setting.rate_mode = payload.rate_mode
            setting.automatic_source_url = (
                str(payload.automatic_source_url)
                if payload.automatic_source_url
                else None
            )
            setting.max_rate_age_hours = payload.max_rate_age_hours
            setting.extraction_method = payload.extraction_method
            setting.extraction_expression = payload.extraction_expression
            setting.decimal_separator = payload.decimal_separator
            setting.daily_check_time = payload.daily_check_time
            setting.version += 1
            action = "SETTING_UPDATED"
        setting.next_check_at = (
            next_daily_check(payload.daily_check_time)
            if payload.rate_mode == "AUTOMATIC"
            else None
        )
        rate = await self.latest_rate(setting.id)
        if payload.currency_code == "RSD" and (
            rate is None or rate.rate_to_rsd != Decimal("1")
        ):
            rate = SupplierExchangeRate(
                currency_setting_id=setting.id,
                rate_to_rsd=Decimal("1"),
                effective_at=datetime.now(UTC),
                status="VERIFIED",
                source_type="FIXED",
                note="Fiksni Monitor obračun RSD = 1",
                created_by=actor,
            )
            self.session.add(rate)
            await self.session.flush()
        self.session.add(
            SupplierCurrencyEvent(
                supplier_id=supplier_id,
                currency_setting_id=setting.id,
                exchange_rate_id=rate.id if rate else None,
                action=action,
                actor_id=actor,
                details=json.dumps(payload.model_dump(mode="json"), ensure_ascii=False),
            )
        )
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            supplier_error(
                409,
                "currency_setting_conflict",
                "Dobavljač već ima aktivno podešavanje valute",
            )
        await self.session.refresh(setting)
        rate = await self.latest_rate(setting.id)
        return currency_setting_read(
            setting, supplier.company_name, rate, "CURRENT" if rate else "MISSING"
        )

    async def add_rate(
        self, supplier_id: uuid.UUID, payload: ExchangeRateCreate
    ) -> SupplierExchangeRate:
        setting = await self.active_setting(supplier_id, lock=True)
        if setting is None:
            supplier_error(
                409, "currency_setting_missing", "Prvo podesite valutu dobavljača"
            )
        if setting.currency_code == "RSD":
            supplier_error(409, "rsd_rate_immutable", "Kurs RSD je uvek 1")
        if payload.source_type != setting.rate_mode:
            supplier_error(
                409,
                "rate_source_mismatch",
                "Način unosa kursa ne odgovara podešavanju dobavljača",
            )
        require_trusted_automatic_rate(payload)
        if payload.effective_at > datetime.now(UTC) + timedelta(minutes=5):
            supplier_error(
                422, "rate_effective_in_future", "Kurs ne može važiti u budućnosti"
            )
        previous = await self.latest_rate(setting.id, payload.effective_at)
        if previous:
            ratio = payload.rate_to_rsd / previous.rate_to_rsd
            if ratio < Decimal("0.8") or ratio > Decimal("1.2"):
                supplier_error(
                    409,
                    "exchange_rate_change_suspicious",
                    "Promena kursa veća od 20% zahteva zasebnu proveru",
                )
        rate = SupplierExchangeRate(
            currency_setting_id=setting.id,
            rate_to_rsd=payload.rate_to_rsd,
            effective_at=payload.effective_at,
            status="VERIFIED",
            source_type=payload.source_type,
            evidence_checksum=payload.evidence_checksum,
            note=payload.note,
            created_by=current_actor_id() or "system",
        )
        self.session.add(rate)
        await self.session.flush()
        self.session.add(
            SupplierCurrencyEvent(
                supplier_id=supplier_id,
                currency_setting_id=setting.id,
                exchange_rate_id=rate.id,
                action="RATE_ADDED",
                actor_id=current_actor_id() or "system",
                details=payload.note,
            )
        )
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            supplier_error(
                409,
                "exchange_rate_duplicate",
                "Kurs već postoji za izabrano vreme važenja",
            )
        await self.session.refresh(rate)
        return rate

    async def rates(
        self, supplier_id: uuid.UUID, limit: int = 100
    ) -> list[SupplierExchangeRate]:
        setting = await self.active_setting(supplier_id)
        if setting is None:
            return []
        return list(
            (
                await self.session.scalars(
                    select(SupplierExchangeRate)
                    .where(SupplierExchangeRate.currency_setting_id == setting.id)
                    .order_by(
                        SupplierExchangeRate.effective_at.desc(),
                        SupplierExchangeRate.id.desc(),
                    )
                    .limit(limit)
                )
            ).all()
        )

    async def events(
        self, supplier_id: uuid.UUID, limit: int = 100
    ) -> CurrencyEventList:
        rows = list(
            (
                await self.session.scalars(
                    select(SupplierCurrencyEvent)
                    .where(SupplierCurrencyEvent.supplier_id == supplier_id)
                    .order_by(
                        SupplierCurrencyEvent.created_at.desc(),
                        SupplierCurrencyEvent.id.desc(),
                    )
                    .limit(limit)
                )
            ).all()
        )
        return CurrencyEventList(
            items=[CurrencyEventRead.model_validate(row) for row in rows],
            total=len(rows),
        )

    async def snapshot_plan(
        self, supplier_id: uuid.UUID, records: Sequence[object], at: datetime
    ) -> SnapshotCurrencyPlan | None:
        return await build_snapshot_currency_plan(self, supplier_id, records, at)
