from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.suppliers.eol_schemas import EolBatchCreate
from app.modules.suppliers.eol_service import SupplierEolService, months_before


def test_months_before_uses_calendar_months_and_clamps_month_end() -> None:
    assert months_before(datetime(2026, 9, 5, 12, tzinfo=UTC), 6) == datetime(
        2026, 3, 5, 12, tzinfo=UTC
    )
    assert months_before(datetime(2026, 3, 31, 12, tzinfo=UTC), 1) == datetime(
        2026, 2, 28, 12, tzinfo=UTC
    )


def test_months_before_crosses_year_boundary() -> None:
    assert months_before(datetime(2026, 2, 1, tzinfo=UTC), 12) == datetime(
        2025, 2, 1, tzinfo=UTC
    )


def test_candidate_uses_all_suppliers_and_marks_existing_batch() -> None:
    now = datetime(2026, 9, 5, tzinfo=UTC)
    candidate = SupplierEolService._candidate(
        {
            "identity_key": "ean:8606019540128",
            "ean": "8606019540128",
            "product_name": "Monitor",
            "last_seen_at": datetime(2026, 1, 1, tzinfo=UTC),
            "export_item_status": "PENDING",
            "export_batch_status": "PREPARED",
            "export_batch_code": "EOL-000001",
            "suppliers": [
                {
                    "supplier_id": "00000000-0000-0000-0000-000000000001",
                    "supplier_name": "EPI",
                    "product_code": "A-1",
                    "last_seen_at": datetime(2026, 1, 1, tzinfo=UTC),
                    "is_currently_offered": False,
                },
                {
                    "supplier_id": "00000000-0000-0000-0000-000000000002",
                    "supplier_name": "EWE",
                    "product_code": "B-9",
                    "last_seen_at": datetime(2025, 12, 1, tzinfo=UTC),
                    "is_currently_offered": False,
                },
            ],
        },
        now,
    )
    assert candidate.status == "MARKED_FOR_DEACTIVATION"
    assert candidate.export_eligible is False
    assert candidate.export_batch_code == "EOL-000001"
    assert len(candidate.suppliers) == 2


def test_batch_rejects_duplicate_identifiers_and_targets() -> None:
    with pytest.raises(ValidationError):
        EolBatchCreate(
            identity_keys=["ean:1", "ean:1"],
            target_systems=["WEBSITE"],
            idempotency_key="12345678",
        )
    with pytest.raises(ValidationError):
        EolBatchCreate(
            identity_keys=["ean:1"],
            target_systems=["WEBSITE", "WEBSITE"],
            idempotency_key="12345678",
        )
