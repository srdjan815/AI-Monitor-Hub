from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.modules.suppliers.acquisition_models import SupplierAcquisitionRun
from app.modules.suppliers.api_repository import SupplierApiRepository
from app.modules.suppliers.api_schemas import SupplierProcessStatus
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.source_secrets import source_secret_provider
from app.modules.suppliers.source_validation_service import (
    SupplierSourceValidationService,
)


class SupplierProcessOverviewService:
    def __init__(self, repository: SupplierApiRepository) -> None:
        self.repository = repository
        self.source_validator = SupplierSourceValidationService()

    async def rows(self) -> list[SupplierProcessStatus]:
        data = await self.repository.supplier_process_rows()
        sources: dict[uuid.UUID, SupplierSource] = {}
        for source_record in data["sources"]:
            sources.setdefault(source_record.supplier_id, source_record)
        schemas = {
            profile.source_connection_id: profile for profile in data["schemas"]
        }
        mappings = {
            profile.schema_profile_id: profile for profile in data["mappings"]
        }
        runs: dict[uuid.UUID, list[SupplierAcquisitionRun]] = {}
        for run in data["runs"]:
            runs.setdefault(run.source_connection_id, []).append(run)
        now = datetime.now(UTC)
        result: list[SupplierProcessStatus] = []
        for supplier in data["suppliers"]:
            source = sources.get(supplier.id)
            if source is None:
                result.append(self._unconfigured(supplier.id, supplier.company_name))
                continue
            schema = schemas.get(source.id)
            mapping = mappings.get(schema.id) if schema else None
            source_runs = runs.get(source.id, [])
            successful = [
                run
                for run in source_runs
                if run.status in {"SUCCEEDED", "PARTIALLY_SUCCEEDED"}
            ]
            latest = source_runs[0] if source_runs else None
            latest_success = successful[0] if successful else None
            previous_success = successful[1] if len(successful) > 1 else None
            source_format = source.configuration.get("expected_content_type")
            if not isinstance(source_format, str):
                source_format = source.source_type
            connection = self._connection(source)
            result.append(
                SupplierProcessStatus(
                    supplier_id=supplier.id,
                    supplier_name=supplier.company_name,
                    source_id=source.id,
                    source_name=source.name,
                    source_format=source_format,
                    connection_status=connection,
                    schema_status="Spremno" if schema else "Nije podešeno",
                    mapping_status="Spremno" if mapping else "Nije podešeno",
                    acquisition_status=self._acquisition(
                        bool(schema), bool(mapping), latest, latest_success
                    ),
                    last_success_at=latest_success.completed_at if latest_success else None,
                    article_count=(
                        latest_success.accepted_record_count if latest_success else None
                    ),
                    content_changed=(
                        latest_success.checksum != previous_success.checksum
                        if latest_success and previous_success
                        else None
                    ),
                    warning=self._warning(
                        connection,
                        bool(schema),
                        bool(mapping),
                        latest,
                        latest_success,
                        previous_success,
                        now,
                    ),
                )
            )
        return result

    @staticmethod
    def _unconfigured(
        supplier_id: uuid.UUID, supplier_name: str
    ) -> SupplierProcessStatus:
        return SupplierProcessStatus(
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            source_id=None,
            source_name=None,
            source_format=None,
            connection_status="Nije podešeno",
            schema_status="Nije podešeno",
            mapping_status="Nije podešeno",
            acquisition_status="Nije spremno",
            last_success_at=None,
            article_count=None,
            content_changed=None,
            warning="Aktivan dobavljač nema konekciju sa cenovnikom.",
        )

    def _connection(self, source: SupplierSource) -> str:
        requires_secret = self.source_validator.requires_secret(
            source.source_type,
            source.configuration,
        )
        if requires_secret and not source_secret_provider.available(
            source.secret_reference
        ):
            return "Nedostaju pristupni podaci"
        if source.status == "ACTIVE" and source.last_validation_status == "VALID":
            return "Radi"
        if source.last_validation_status == "INVALID":
            return "Ne radi"
        return "Potrebna provera"

    @staticmethod
    def _acquisition(
        has_schema: bool,
        has_mapping: bool,
        latest: SupplierAcquisitionRun | None,
        latest_success: SupplierAcquisitionRun | None,
    ) -> str:
        if not has_schema or not has_mapping:
            return "Nije spremno"
        if latest and latest.status == "FAILED":
            return "Ne radi"
        return "Radi" if latest_success else "Potrebna provera"

    @staticmethod
    def _warning(
        connection_status: str,
        has_schema: bool,
        has_mapping: bool,
        latest: SupplierAcquisitionRun | None,
        latest_success: SupplierAcquisitionRun | None,
        previous_success: SupplierAcquisitionRun | None,
        now: datetime,
    ) -> str | None:
        if connection_status != "Radi":
            return "Cenovnik nije dostupan zbog problema sa pristupom dobavljaču."
        if not has_schema:
            return "Cenovnik je dostupan, ali Schema još nije podešena."
        if not has_mapping:
            return "Cenovnik je dostupan, ali Mapping još nije podešen."
        if latest and latest.status == "FAILED":
            return "Cenovnik je dostupan, ali obrada nije uspešno završena."
        warning: str | None = None
        if latest_success and latest_success.completed_at:
            if now - latest_success.completed_at > timedelta(
                hours=settings.supplier_warning_hours
            ):
                warning = "Cenovnik nije osvežen u očekivanom vremenu."
        if (
            latest_success
            and previous_success
            and previous_success.accepted_record_count > 0
            and latest_success.accepted_record_count
            < previous_success.accepted_record_count
            * (1 - settings.supplier_article_drop_ratio)
        ):
            warning = "Broj artikala je naglo opao u odnosu na prethodno preuzimanje."
        return warning


__all__ = ["SupplierProcessOverviewService"]
