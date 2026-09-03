from __future__ import annotations


def anomaly_signals(
    *,
    previous_total: int,
    current_total: int,
    added: int,
    removed: int,
    modified: int,
    schema_changed: bool,
    mapping_changed: bool,
    minimum_items: int = 10,
    high_removal_ratio: float = 0.5,
    high_addition_ratio: float = 0.5,
    unusual_modified_ratio: float = 0.8,
) -> list[dict[str, object]]:
    signals: list[dict[str, object]] = []
    if schema_changed:
        signals.append({"code": "SCHEMA_VERSION_CHANGED"})
    if mapping_changed:
        signals.append({"code": "MAPPING_VERSION_CHANGED"})
    if previous_total >= minimum_items and removed / previous_total >= high_removal_ratio:
        signals.append({"code": "HIGH_REMOVAL_RATIO", "ratio": removed / previous_total})
    if current_total >= minimum_items and added / current_total >= high_addition_ratio:
        signals.append({"code": "HIGH_ADDITION_RATIO", "ratio": added / current_total})
    if previous_total >= minimum_items and modified / previous_total >= unusual_modified_ratio:
        signals.append({"code": "UNUSUAL_FIELD_CHANGE_VOLUME", "ratio": modified / previous_total})
    return signals


__all__ = ["anomaly_signals"]
