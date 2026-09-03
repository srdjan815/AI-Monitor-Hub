from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mypy_clean_baseline() -> None:
    baseline = json.loads((ROOT / "mypy-baseline.json").read_text())
    result = subprocess.run(
        ["mypy", "app"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert baseline["maximum_errors"] == 0
    assert baseline["maximum_files_with_errors"] == 0
    assert (
        f"Success: no issues found in {baseline['checked_source_files']} source files"
        in output
    )
