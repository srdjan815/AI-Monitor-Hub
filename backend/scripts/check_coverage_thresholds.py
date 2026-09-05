from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _percent(covered: int, total: int) -> float:
    return 100.0 if total == 0 else covered * 100.0 / total


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} mora sadržati JSON objekat")
    return payload


def _threshold(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} mora biti broj")
    result = float(value)
    if not 0.0 <= result <= 100.0:
        raise ValueError(f"{label} mora biti između 0 i 100")
    return result


def _summary_counts(summary: dict[str, Any], label: str) -> tuple[int, int, int, int]:
    keys = ("covered_lines", "num_statements", "covered_branches", "num_branches")
    values: list[int] = []
    for key in keys:
        value = summary.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{label}.{key} mora biti nenegativan ceo broj")
        values.append(value)
    covered_lines, statements, covered_branches, branches = values
    if covered_lines > statements or covered_branches > branches:
        raise ValueError(f"{label} sadrži nemoguće coverage brojeve")
    return covered_lines, statements, covered_branches, branches


def _check_pair(
    label: str,
    covered_lines: int,
    statements: int,
    covered_branches: int,
    branches: int,
    policy: dict[str, Any],
) -> list[str]:
    statement_percent = _percent(covered_lines, statements)
    branch_percent = _percent(covered_branches, branches)
    statement_floor = _threshold(
        policy.get("minimum_statement_percent"),
        f"{label}.minimum_statement_percent",
    )
    branch_floor = _threshold(
        policy.get("minimum_branch_percent"),
        f"{label}.minimum_branch_percent",
    )
    print(
        f"{label}: naredbe {statement_percent:.2f}% (minimum {statement_floor:.2f}%), "
        f"grane {branch_percent:.2f}% (minimum {branch_floor:.2f}%)"
    )
    failures: list[str] = []
    if statement_percent + 1e-9 < statement_floor:
        failures.append(f"{label}: pokrivenost naredbi je ispod minimuma")
    if branch_percent + 1e-9 < branch_floor:
        failures.append(f"{label}: pokrivenost grana je ispod minimuma")
    return failures


def evaluate(coverage: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    if policy.get("version") != 1:
        raise ValueError("Nepodržana verzija coverage politike")
    totals = coverage.get("totals")
    files = coverage.get("files")
    global_policy = policy.get("global")
    groups = policy.get("groups")
    if not isinstance(totals, dict) or not isinstance(files, dict):
        raise ValueError("Coverage izveštaju nedostaju totals ili files")
    if not isinstance(global_policy, dict) or not isinstance(groups, dict):
        raise ValueError("Coverage politici nedostaju global ili groups")

    failures = _check_pair(
        "globalno", *_summary_counts(totals, "totals"), global_policy
    )
    for name, raw_group in groups.items():
        if not isinstance(name, str) or not isinstance(raw_group, dict):
            raise ValueError("Svaka coverage grupa mora biti imenovani objekat")
        selected = raw_group.get("files")
        if not isinstance(selected, list) or not selected:
            raise ValueError(f"Grupa {name} mora sadržati nepraznu listu files")
        accumulated = [0, 0, 0, 0]
        for file_name in selected:
            if not isinstance(file_name, str) or file_name not in files:
                failures.append(f"{name}: nedostaje obavezni fajl {file_name!r}")
                continue
            summary = files[file_name].get("summary")
            if not isinstance(summary, dict):
                failures.append(f"{name}: fajl {file_name!r} nema summary")
                continue
            counts = _summary_counts(summary, file_name)
            accumulated = [left + right for left, right in zip(accumulated, counts)]
        if not any(accumulated):
            failures.append(f"{name}: nema merljivih coverage podataka")
            continue
        failures.extend(_check_pair(name, *accumulated, raw_group))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Proverava obavezne coverage pragove.")
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    try:
        failures = evaluate(_load_object(args.coverage), _load_object(args.policy))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"NEISPRAVNA COVERAGE PROVERA: {exc}")
        return 2
    if failures:
        for failure in failures:
            print(f"NEUSPEH: {failure}")
        return 1
    print("Coverage pragovi su ispunjeni.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
