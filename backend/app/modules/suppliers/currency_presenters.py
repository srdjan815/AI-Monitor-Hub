from __future__ import annotations

from app.modules.suppliers.currency_models import (
    SupplierCurrencySetting,
    SupplierExchangeRate,
)
from app.modules.suppliers.currency_schemas import CurrencySettingRead


def currency_setting_read(
    setting: SupplierCurrencySetting,
    supplier_name: str,
    rate: SupplierExchangeRate | None,
    status: str,
    source_name: str | None = None,
    portal_supplier_code: str | None = None,
) -> CurrencySettingRead:
    return CurrencySettingRead(
        id=setting.id,
        supplier_id=setting.supplier_id,
        supplier_name=supplier_name,
        source_connection_id=setting.source_connection_id,
        source_name=source_name,
        portal_supplier_code=portal_supplier_code,
        currency_code=setting.currency_code,
        currency_source=setting.currency_source,
        rate_mode=setting.rate_mode,
        automatic_source_url=setting.automatic_source_url,
        extraction_method=setting.extraction_method,
        extraction_expression=setting.extraction_expression,
        fallback_extraction_method=setting.fallback_extraction_method,
        fallback_extraction_expression=setting.fallback_extraction_expression,
        decimal_separator=setting.decimal_separator,
        daily_check_time=setting.daily_check_time,
        next_check_at=setting.next_check_at,
        last_check_at=setting.last_check_at,
        last_check_status=setting.last_check_status,
        last_check_message=setting.last_check_message,
        max_rate_age_hours=setting.max_rate_age_hours,
        current_rate=rate.rate_to_rsd if rate else None,
        current_rate_effective_at=rate.effective_at if rate else None,
        rate_status=status,
        version=setting.version,
    )


__all__ = ["currency_setting_read"]
