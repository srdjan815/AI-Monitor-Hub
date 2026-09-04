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
) -> CurrencySettingRead:
    return CurrencySettingRead(
        id=setting.id,
        supplier_id=setting.supplier_id,
        supplier_name=supplier_name,
        currency_code=setting.currency_code,
        currency_source=setting.currency_source,
        rate_mode=setting.rate_mode,
        automatic_source_url=setting.automatic_source_url,
        max_rate_age_hours=setting.max_rate_age_hours,
        current_rate=rate.rate_to_rsd if rate else None,
        current_rate_effective_at=rate.effective_at if rate else None,
        rate_status=status,
        version=setting.version,
    )


__all__ = ["currency_setting_read"]
