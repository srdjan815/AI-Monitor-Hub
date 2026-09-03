from __future__ import annotations

from app.modules.suppliers.incident_models import SupplierIncidentRule


def select_rule(
    rules: list[SupplierIncidentRule], supplier_id: object, source_id: object
) -> SupplierIncidentRule | None:
    enabled = [rule for rule in rules if rule.is_active]
    ranked = sorted(
        enabled,
        key=lambda rule: (
            0
            if rule.source_connection_id == source_id
            else 1
            if rule.supplier_id == supplier_id and rule.source_connection_id is None
            else 2
            if rule.supplier_id is None and rule.source_connection_id is None
            else 3,
            rule.rule_code,
        ),
    )
    return (
        ranked[0]
        if ranked
        and (
            ranked[0].source_connection_id in {None, source_id}
            and ranked[0].supplier_id in {None, supplier_id}
        )
        else None
    )


def rule_allows(
    rule: SupplierIncidentRule,
    context: dict[str, object],
) -> bool:
    signal = context.get("signal")
    values = signal if isinstance(signal, dict) else context
    checks = (
        ("minimum_count", ("count", "rejected", "total")),
        ("minimum_ratio", ("ratio",)),
        ("minimum_percentage", ("percentage",)),
    )
    for threshold_name, candidate_names in checks:
        threshold = rule.threshold_configuration.get(threshold_name)
        if threshold is None:
            continue
        actual = next(
            (
                values.get(name)
                for name in candidate_names
                if values.get(name) is not None
            ),
            None,
        )
        try:
            if actual is None or float(str(actual)) < float(str(threshold)):
                return False
        except (TypeError, ValueError):
            return False
    return True


__all__ = ["rule_allows", "select_rule"]
