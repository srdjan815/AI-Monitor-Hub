from __future__ import annotations

import uuid

import pytest

from app.modules.suppliers.delta_models import SupplierDeltaItem
from app.modules.suppliers.downstream_publication_policy import (
    DownstreamBlockReason,
    DownstreamPolicyViolation,
    publication_decision,
    require_publishable,
)


def candidate(
    *,
    summary: dict[str, object],
    flags: list[str] | None = None,
    current: bool = True,
) -> SupplierDeltaItem:
    return SupplierDeltaItem(
        id=uuid.uuid4(),
        delta_run_id=uuid.uuid4(),
        change_type="MODIFIED",
        matching_key_type="PRODUCT_CODE",
        matching_key_value="SKU-1",
        current_snapshot_item_id=uuid.uuid4() if current else None,
        change_summary=summary,
        anomaly_flags=flags or [],
    )


def test_explicit_safe_item_is_publishable() -> None:
    item = candidate(
        summary={"downstream_blocked": False, "requires_manual_approval": False}
    )
    decision = publication_decision(item)
    assert decision.allowed is True
    assert decision.reasons == ()


@pytest.mark.parametrize(
    ("summary", "flags", "reason"),
    [
        ({}, [], DownstreamBlockReason.POLICY_METADATA_MISSING),
        (
            {"downstream_blocked": True, "requires_manual_approval": False},
            [],
            DownstreamBlockReason.EXPLICITLY_BLOCKED,
        ),
        (
            {"downstream_blocked": False, "requires_manual_approval": True},
            [],
            DownstreamBlockReason.MANUAL_APPROVAL_REQUIRED,
        ),
        (
            {"downstream_blocked": False, "requires_manual_approval": False},
            ["DOWNSTREAM_ITEM_BLOCKED"],
            DownstreamBlockReason.BLOCKING_ANOMALY,
        ),
    ],
)
def test_every_unsafe_or_incomplete_state_is_blocked(
    summary: dict[str, object],
    flags: list[str],
    reason: DownstreamBlockReason,
) -> None:
    decision = publication_decision(candidate(summary=summary, flags=flags))
    assert decision.allowed is False
    assert reason in decision.reasons


def test_outgoing_batch_is_checked_before_any_publisher_can_continue() -> None:
    safe = candidate(
        summary={"downstream_blocked": False, "requires_manual_approval": False}
    )
    unsafe = candidate(summary={})
    with pytest.raises(DownstreamPolicyViolation) as failure:
        require_publishable([safe, unsafe])
    assert [row.delta_item_id for row in failure.value.decisions] == [unsafe.id]


def test_item_without_current_snapshot_value_can_never_be_published() -> None:
    item = candidate(
        summary={"downstream_blocked": False, "requires_manual_approval": False},
        current=False,
    )
    assert (
        DownstreamBlockReason.CURRENT_ITEM_MISSING in publication_decision(item).reasons
    )
