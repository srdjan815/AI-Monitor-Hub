from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence


class DownstreamBlockReason(StrEnum):
    POLICY_METADATA_MISSING = "POLICY_METADATA_MISSING"
    EXPLICITLY_BLOCKED = "EXPLICITLY_BLOCKED"
    MANUAL_APPROVAL_REQUIRED = "MANUAL_APPROVAL_REQUIRED"
    BLOCKING_ANOMALY = "BLOCKING_ANOMALY"
    CURRENT_ITEM_MISSING = "CURRENT_ITEM_MISSING"


class DownstreamPolicyViolation(RuntimeError):
    def __init__(self, decisions: Sequence[DownstreamDecision]) -> None:
        self.decisions = tuple(decisions)
        blocked_ids = ",".join(str(item.delta_item_id) for item in decisions[:10])
        super().__init__(f"DOWNSTREAM_PUBLICATION_BLOCKED:{blocked_ids}")


class DeltaPublicationCandidate(Protocol):
    id: uuid.UUID
    current_snapshot_item_id: uuid.UUID | None
    change_summary: dict[str, object]
    anomaly_flags: list[str]


@dataclass(frozen=True, slots=True)
class DownstreamDecision:
    delta_item_id: uuid.UUID
    allowed: bool
    reasons: tuple[DownstreamBlockReason, ...]


def publication_decision(candidate: DeltaPublicationCandidate) -> DownstreamDecision:
    """Return the fail-closed decision consumed by every future publisher.

    Both booleans are deliberately required. Older rows and new producer code
    which forgot to classify the item are unsafe by default and cannot leave
    the system.
    """

    summary = candidate.change_summary
    blocked = summary.get("downstream_blocked")
    approval = summary.get("requires_manual_approval")
    reasons: list[DownstreamBlockReason] = []

    if not isinstance(blocked, bool) or not isinstance(approval, bool):
        reasons.append(DownstreamBlockReason.POLICY_METADATA_MISSING)
    if blocked is True:
        reasons.append(DownstreamBlockReason.EXPLICITLY_BLOCKED)
    if approval is True:
        reasons.append(DownstreamBlockReason.MANUAL_APPROVAL_REQUIRED)
    if "DOWNSTREAM_ITEM_BLOCKED" in candidate.anomaly_flags:
        reasons.append(DownstreamBlockReason.BLOCKING_ANOMALY)
    if candidate.current_snapshot_item_id is None:
        reasons.append(DownstreamBlockReason.CURRENT_ITEM_MISSING)

    return DownstreamDecision(
        delta_item_id=candidate.id,
        allowed=not reasons,
        reasons=tuple(reasons),
    )


def require_publishable(
    candidates: Sequence[DeltaPublicationCandidate],
) -> tuple[DownstreamDecision, ...]:
    """Validate a complete outgoing batch before the first external write."""

    decisions = tuple(publication_decision(candidate) for candidate in candidates)
    blocked = tuple(decision for decision in decisions if not decision.allowed)
    if blocked:
        raise DownstreamPolicyViolation(blocked)
    return decisions


__all__ = [
    "DownstreamBlockReason",
    "DownstreamDecision",
    "DownstreamPolicyViolation",
    "publication_decision",
    "require_publishable",
]
