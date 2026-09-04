from __future__ import annotations

from app.core.security import current_principal
from app.modules.suppliers.currency_schemas import ExchangeRateCreate
from app.modules.suppliers.errors import supplier_error


def require_trusted_automatic_rate(payload: ExchangeRateCreate) -> None:
    if payload.source_type != "AUTOMATIC":
        return
    principal = current_principal()
    if principal is None or "internal_service" not in principal.roles:
        supplier_error(
            403,
            "automatic_rate_service_only",
            "Automatski kurs može upisati samo interni servis",
        )
    if payload.evidence_checksum is None:
        supplier_error(
            422,
            "automatic_rate_evidence_required",
            "Automatski kurs zahteva kontrolni zbir izvornog odgovora",
        )


__all__ = ["require_trusted_automatic_rate"]
