from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.check_coverage_thresholds import evaluate, main


def _coverage(branches: int = 90) -> dict[str, Any]:
    summary = {
        "covered_lines": 97,
        "num_statements": 100,
        "covered_branches": branches,
        "num_branches": 100,
    }
    return {"totals": summary, "files": {"critical.py": {"summary": summary}}}


def _policy() -> dict[str, Any]:
    return {
        "version": 1,
        "global": {
            "minimum_statement_percent": 79,
            "minimum_branch_percent": 52,
        },
        "groups": {
            "critical": {
                "minimum_statement_percent": 97,
                "minimum_branch_percent": 90,
                "files": ["critical.py"],
            }
        },
    }


def test_evaluate_accepts_independent_statement_and_branch_floors() -> None:
    assert evaluate(_coverage(), _policy()) == []


def test_evaluate_rejects_branch_regression_even_when_statements_pass() -> None:
    failures = evaluate(_coverage(branches=89), _policy())

    assert failures == ["critical: pokrivenost grana je ispod minimuma"]


def test_evaluate_fails_closed_when_critical_file_is_missing() -> None:
    coverage = _coverage()
    coverage["files"] = {}

    failures = evaluate(coverage, _policy())

    assert any("nedostaje obavezni fajl" in failure for failure in failures)


def test_main_returns_configuration_error_for_malformed_report(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coverage_path = tmp_path / "coverage.json"
    policy_path = tmp_path / "policy.json"
    coverage_path.write_text("[]", encoding="utf-8")
    policy_path.write_text(json.dumps(_policy()), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_coverage_thresholds",
            "--coverage",
            str(coverage_path),
            "--policy",
            str(policy_path),
        ],
    )

    assert main() == 2


def test_repository_policy_floors_require_deliberate_review() -> None:
    policy_path = Path(__file__).parents[1] / "coverage-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))

    assert policy["global"] == {
        "minimum_statement_percent": 79.0,
        "minimum_branch_percent": 52.0,
    }
    assert (
        policy["groups"]["critical_supplier_decisions"]["minimum_branch_percent"]
        == 90.0
    )
