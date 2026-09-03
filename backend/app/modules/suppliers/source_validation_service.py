from __future__ import annotations

from pydantic import ValidationError

from app.modules.suppliers.enums import SupplierSourceType
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.source_configuration import (
    CONFIGURATION_MODELS,
    ApiSourceConfiguration,
    AuthenticationType,
)

_ALWAYS_SECRET = {
    SupplierSourceType.FTP,
    SupplierSourceType.SFTP,
    SupplierSourceType.EMAIL,
}


class SupplierSourceValidationService:
    """Strict, network-free validation of source configuration."""

    @staticmethod
    def normalize_configuration(
        source_type: SupplierSourceType | str,
        configuration: dict[str, object],
    ) -> dict[str, object]:
        type_value = (
            source_type.value
            if isinstance(source_type, SupplierSourceType)
            else source_type
        )
        model = CONFIGURATION_MODELS[type_value]
        try:
            validated = model.model_validate(configuration)
        except ValidationError as exc:
            first = exc.errors(include_url=False)[0]
            message = str(first.get("msg", "Konfiguracija nije ispravna"))
            supplier_error(
                422,
                "supplier_source_invalid_configuration",
                message,
            )
        return validated.model_dump(mode="json")

    @staticmethod
    def requires_secret(
        source_type: SupplierSourceType | str,
        configuration: dict[str, object],
    ) -> bool:
        source = SupplierSourceType(source_type)
        if source in _ALWAYS_SECRET:
            return True
        if source == SupplierSourceType.API:
            validated = ApiSourceConfiguration.model_validate(configuration)
            return validated.authentication_type != AuthenticationType.NONE
        return False

    @classmethod
    def ensure_secret_policy(
        cls,
        source_type: SupplierSourceType | str,
        configuration: dict[str, object],
        secret_reference: str | None,
    ) -> None:
        if cls.requires_secret(source_type, configuration) and not secret_reference:
            supplier_error(
                409,
                "supplier_source_missing_secret_reference",
                "Za izabranu konfiguraciju je obavezna referenca na poverljive podatke",
            )


__all__ = ["SupplierSourceValidationService"]
