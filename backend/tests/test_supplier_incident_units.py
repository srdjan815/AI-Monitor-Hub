from __future__ import annotations

import uuid

from app.modules.suppliers.incident_models import SupplierIncidentRule
from app.modules.suppliers.incident_rules import rule_allows, select_rule
from app.modules.suppliers.incident_safety import incident_fingerprint, sanitize_context, sanitize_text


def _rule(code: str, supplier: uuid.UUID | None, source: uuid.UUID | None) -> SupplierIncidentRule:
    return SupplierIncidentRule(
        rule_code=code, name=code, source_domain="DELTA",
        incident_type="HIGH_REMOVAL_RATIO", signal_code="HIGH_REMOVAL_RATIO",
        enabled=True, minimum_severity="INFO", resulting_severity="HIGH",
        default_priority="P2", supplier_id=supplier, source_connection_id=source,
        threshold_configuration={}, auto_reopen=True,
        suppression_compatible=True, is_active=True,
    )


def test_rule_precedence_is_source_then_supplier_then_global() -> None:
    supplier, source = uuid.uuid4(), uuid.uuid4()
    global_rule = _rule("GLOBAL", None, None)
    supplier_rule = _rule("SUPPLIER", supplier, None)
    source_rule = _rule("SOURCE", supplier, source)
    assert select_rule([global_rule, supplier_rule, source_rule], supplier, source) is source_rule
    assert select_rule([global_rule, supplier_rule], supplier, source) is supplier_rule
    assert select_rule([global_rule], supplier, source) is global_rule
    source_rule.enabled = False
    assert select_rule([global_rule, source_rule], supplier, source) is source_rule


def test_fingerprint_is_deterministic_and_excludes_workflow_state() -> None:
    payload = {"supplier": "s", "type": "x", "entity": "e"}
    assert incident_fingerprint(payload) == incident_fingerprint(dict(reversed(list(payload.items()))))


def test_rule_thresholds_are_deterministic() -> None:
    rule = _rule("THRESHOLD", None, None)
    rule.threshold_configuration = {"minimum_ratio": 0.5}
    assert rule_allows(rule, {"signal": {"ratio": 0.8}})
    assert not rule_allows(rule, {"signal": {"ratio": 0.2}})


def test_safe_context_redacts_secrets_and_bounds_long_text() -> None:
    long_text = "Unicode <b>opis</b>\n" * 1000
    safe = sanitize_context({
        "authorization": "Bearer secret",
        "nested": {"token": "abc", "description": long_text},
        "message": "token=abc",
    })
    rendered = str(safe)
    assert "secret" not in rendered and "abc" not in rendered
    assert long_text not in rendered and "hash" in rendered and "length" in rendered
    assert sanitize_text("<script>alert(1)</script>", 100) == "&lt;script&gt;alert(1)&lt;/script&gt;"
