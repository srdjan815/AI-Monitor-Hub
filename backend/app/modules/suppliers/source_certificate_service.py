from __future__ import annotations

import uuid
from datetime import UTC, datetime

from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.acquisition_contracts import AcquisitionFailure
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.source_probe_schemas import SourceCertificateState
from app.modules.suppliers.source_repository import SupplierSourceRepository
from app.modules.suppliers.source_secrets import source_secret_provider


class SupplierSourceCertificateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sources = SupplierSourceRepository(session)
        self.suppliers = SupplierRepository(session)

    async def write_certificate(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        content: bytes,
        password: str,
    ) -> SourceCertificateState:
        supplier = await self.suppliers.get_supplier(supplier_id)
        if supplier is None or not supplier.is_active:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        source = await self.sources.get_source(
            supplier_id, source_id, for_update=True
        )
        if source is None:
            supplier_error(404, "supplier_source_not_found", "Konekcija nije pronađena")
        if not source.is_active:
            supplier_error(
                409,
                "supplier_source_inactive",
                "Arhivirana konekcija se ne može menjati",
            )
        if source.source_type != "API" or source.configuration.get(
            "authentication_type"
        ) != "CLIENT_CERTIFICATE":
            supplier_error(
                409,
                "supplier_source_certificate_not_allowed",
                "Klijentski sertifikat nije izabran za ovu API konekciju",
            )
        certificate = self._validated_certificate(content, password)
        try:
            reference = source_secret_provider.write_certificate(content, password)
            await self.sources.update_source(
                source,
                {
                    "secret_reference": reference,
                    "last_validation_at": None,
                    "last_validation_status": None,
                    "last_validation_message": None,
                    "version": source.version + 1,
                },
            )
            await self.session.commit()
        except AcquisitionFailure as exc:
            await self.session.rollback()
            supplier_error(409, exc.code, exc.safe_message)
        except Exception:
            await self.session.rollback()
            raise
        common_names = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        common_name = common_names[0].value if common_names else None
        if isinstance(common_name, bytes):
            common_name = common_name.decode("utf-8", errors="replace")
        return SourceCertificateState(
            configured=True,
            expires_at=certificate.not_valid_after_utc,
            common_name=common_name,
        )

    @staticmethod
    def _validated_certificate(content: bytes, password: str) -> x509.Certificate:
        try:
            private_key, certificate, _chain = pkcs12.load_key_and_certificates(
                content, password.encode("utf-8")
            )
        except (TypeError, ValueError) as exc:
            supplier_error(
                422,
                "supplier_source_certificate_invalid",
                "Sertifikat ili njegova lozinka nisu ispravni",
            )
            raise AssertionError from exc
        if private_key is None or certificate is None:
            supplier_error(
                422,
                "supplier_source_certificate_private_key_missing",
                "Sertifikat ne sadrži klijentski privatni ključ",
            )
        if certificate.not_valid_after_utc <= datetime.now(UTC):
            supplier_error(
                422,
                "supplier_source_certificate_expired",
                "Klijentski sertifikat je istekao",
            )
        return certificate


__all__ = ["SupplierSourceCertificateService"]
