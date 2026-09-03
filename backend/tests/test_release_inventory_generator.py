from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts import generate_release_inventory as inventory


_TRACKED_PATHS: dict[Path, set[str]] = {}


def _relative_files(repository: Path, target: Path) -> set[str]:
    if target.is_file():
        return {target.relative_to(repository).as_posix()}
    return {
        path.relative_to(repository).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }


def _git(repo: Path, *arguments: str) -> None:
    resolved = repo.resolve()
    if arguments[:1] == ("init",):
        _TRACKED_PATHS[resolved] = set()
        return
    assert arguments[:1] == ("add",)
    tracked = _TRACKED_PATHS.setdefault(resolved, set())
    for argument in arguments[1:]:
        tracked.update(_relative_files(resolved, resolved / argument))


def _ignored_paths(repository: Path) -> set[str]:
    ignore_file = repository / ".gitignore"
    if not ignore_file.is_file():
        return set()
    return {
        line.strip().rstrip("/")
        for line in ignore_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _fake_run_git(repository: Path, arguments: list[str]) -> bytes:
    resolved = repository.resolve()
    if arguments == ["rev-parse", "--show-toplevel"]:
        return str(resolved).encode()

    nul_terminated = arguments[-1:] == ["-z"]
    command = arguments[:-1] if nul_terminated else arguments
    tracked = _TRACKED_PATHS.setdefault(resolved, set())
    all_files = {
        path.relative_to(resolved).as_posix()
        for path in resolved.rglob("*")
        if path.is_file()
    }
    ignored = _ignored_paths(resolved)
    if command == ["ls-files"]:
        paths = tracked
    elif command == ["ls-files", "--others", "--exclude-standard"]:
        paths = {
            path
            for path in all_files - tracked
            if path not in ignored
            and not any(path.startswith(f"{item}/") for item in ignored)
        }
    elif command == ["diff", "--name-only"]:
        paths = set()
    elif command == ["diff", "--cached", "--name-only"]:
        paths = tracked
    else:
        raise AssertionError(f"unexpected fake Git command: {arguments!r}")

    separator = b"\0" if nul_terminated else b"\n"
    payload = separator.join(path.encode() for path in sorted(paths))
    return payload + separator if payload else b""


@pytest.fixture(autouse=True)
def deterministic_git_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    _TRACKED_PATHS.clear()
    monkeypatch.setattr(inventory, "_run_git", _fake_run_git)


def _write(repo: Path, relative_path: str, content: str = "") -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def release_repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "--quiet")
    _write(tmp_path, ".gitignore", ".env\ncoverage.xml\n")
    _write(tmp_path, ".env", "REAL_SECRET=not-visible-to-git-listing\n")
    _write(tmp_path, ".env.example", "AUTH_SECRET=development-only-change-me\n")
    _write(tmp_path, "backend/app/__init__.py")
    _write(tmp_path, "backend/app/main.py", "from app.core import limits\n")
    _write(tmp_path, "backend/app/core/__init__.py")
    _write(tmp_path, "backend/app/core/limits.py", "MAXIMUM = 10\n")
    _write(
        tmp_path,
        "backend/alembic/versions/abc_revision.py",
        'revision = "abc"\ndown_revision = None\n',
    )
    _write(
        tmp_path,
        "backend/tests/test_main.py",
        "from app import main\n\n\ndef test_loaded() -> None:\n"
        "    assert main is not None\n",
    )
    _write(tmp_path, "backend/scripts/benchmark.py", "print('benchmark')\n")
    _write(tmp_path, "backend/requirements.lock", "example==1.0.0\n")
    _write(tmp_path, "backend/mypy-baseline.json", '{"maximum_errors": 0}\n')
    _write(tmp_path, "docs/guide.md", "canonical guide\n")
    _write(tmp_path, "docs/guide.bak", "canonical guide\n")
    _write(tmp_path, "docs/audits/openapi-normalized.json", "{}\n")
    _write(tmp_path, "unknown.asset", "requires an owner\n")
    _write(tmp_path, "path with spaces.txt", "requires an owner too\n")
    _write(tmp_path, "junit.xml", "<testsuites />\n")
    _write(tmp_path, "local.tmp", "disposable local state\n")
    _git(
        tmp_path,
        "add",
        ".gitignore",
        ".env.example",
        "backend/app",
        "backend/alembic",
        "backend/tests",
    )
    return tmp_path


def _read_rows(repository: Path) -> list[dict[str, str]]:
    output = repository.joinpath(*inventory.CLASSIFICATION_OUTPUT.parts)
    with output.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_generator_classifies_exact_git_union_and_is_deterministic(
    release_repository: Path,
) -> None:
    first_rows = inventory.generate_release_inventory(release_repository)
    first_csv = release_repository.joinpath(
        *inventory.CLASSIFICATION_OUTPUT.parts
    ).read_bytes()
    first_report = release_repository.joinpath(
        *inventory.SECRET_REPORT_OUTPUT.parts
    ).read_bytes()

    second_rows = inventory.generate_release_inventory(release_repository)
    second_csv = release_repository.joinpath(
        *inventory.CLASSIFICATION_OUTPUT.parts
    ).read_bytes()
    second_report = release_repository.joinpath(
        *inventory.SECRET_REPORT_OUTPUT.parts
    ).read_bytes()

    assert first_rows == second_rows
    assert first_csv == second_csv
    assert first_report == second_report

    rows = _read_rows(release_repository)
    by_path = {row["path"]: row for row in rows}
    tracked, untracked = inventory.collect_git_paths(release_repository)
    expected = {
        path.as_posix() for path in tracked | untracked | set(inventory.OUTPUT_PATHS)
    }
    assert set(by_path) == expected
    assert ".env" not in by_path
    assert "coverage.xml" not in by_path
    assert "path with spaces.txt" in by_path
    assert all(all(row[column] for column in inventory.CSV_COLUMNS) for row in rows)
    assert {row["classification"] for row in rows} <= set("ABCDEFGHIJKL")

    assert by_path["backend/app/main.py"]["classification"] == "A"
    assert by_path["backend/alembic/versions/abc_revision.py"]["classification"] == "B"
    assert by_path["backend/tests/test_main.py"]["classification"] == "C"
    assert by_path["backend/scripts/benchmark.py"]["classification"] == "D"
    assert by_path["backend/requirements.lock"]["classification"] == "E"
    assert by_path["docs/guide.md"]["classification"] == "F"
    assert by_path["backend/mypy-baseline.json"]["classification"] == "G"
    assert by_path["docs/audits/openapi-normalized.json"]["classification"] == "G"
    assert by_path["docs/guide.bak"]["classification"] == "K"
    assert by_path["docs/guide.bak"]["include in Git yes/no"] == "no"
    assert by_path["junit.xml"]["classification"] == "H"
    assert by_path["local.tmp"]["classification"] == "I"
    assert by_path["unknown.asset"]["classification"] == "L"
    assert by_path["backend/app/main.py"]["referenced by"] == (
        "backend/tests/test_main.py"
    )
    for generated_path in inventory.OUTPUT_PATHS:
        assert by_path[generated_path.as_posix()]["classification"] == "G"


def test_secret_scan_is_redacted_and_requires_explicit_synthetic_marker(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init", "--quiet")
    real_token = "ghp_" + "A" * 32
    credential_url = (  # synthetic test-only fixture
        "postgresql://service:UniquePassphrase42@db/service"  # synthetic test-only
    )
    machine_path = "C:\\Users\\Alice\\private\\notes.txt"
    _write(
        tmp_path,
        "docs/sensitive.md",
        f"{real_token}\n{credential_url}\n{machine_path}\n",
    )
    _write(
        tmp_path,
        "backend/tests/test_fixture.py",
        "# synthetic test-only fixture\n"
        "TOKEN = 'Bearer not-a-real-token-value'\n"
        "KEY = '-----BEGIN PRIVATE KEY-----'  # synthetic test-only fixture\n",
    )

    rows = inventory.generate_release_inventory(tmp_path)
    by_path = {row["path"]: row for row in rows}
    sensitive = by_path["docs/sensitive.md"]
    synthetic = by_path["backend/tests/test_fixture.py"]

    assert sensitive["classification"] == "J"
    assert sensitive["include in Git yes/no"] == "no"
    assert sensitive["secret scan result"].startswith("REVIEW_REQUIRED:")
    assert synthetic["classification"] == "C"
    assert synthetic["secret scan result"].startswith("SYNTHETIC_TEST_LITERAL_ONLY:")

    report = tmp_path.joinpath(*inventory.SECRET_REPORT_OUTPUT.parts).read_text(
        encoding="utf-8"
    )
    assert "Review-required findings: 3" in report
    assert "Explicitly synthetic test/example findings: 2" in report
    assert real_token not in report
    assert credential_url not in report
    assert machine_path not in report
    assert "sha256:" in report


def test_duplicate_analysis_preserves_empty_package_markers(tmp_path: Path) -> None:
    _git(tmp_path, "init", "--quiet")
    _write(tmp_path, "backend/app/__init__.py")
    _write(tmp_path, "backend/app/core/__init__.py")
    _write(tmp_path, "docs/first.md", "same meaningful content\n")
    _write(tmp_path, "docs/second.md", "same meaningful content\n")

    rows = inventory.generate_release_inventory(tmp_path)
    by_path = {row["path"]: row for row in rows}

    for path in ("backend/app/__init__.py", "backend/app/core/__init__.py"):
        assert by_path[path]["classification"] == "A"
        assert by_path[path]["duplicate check"] == "INTENTIONAL_EMPTY_PACKAGE_MARKER"
    assert by_path["docs/first.md"]["classification"] == "F"
    assert by_path["docs/second.md"]["classification"] == "F"
    assert by_path["docs/first.md"]["duplicate check"].startswith(
        "IDENTICAL_CONTENT_REVIEW"
    )


def test_validate_inventory_rejects_duplicate_and_blank_rows() -> None:
    complete = {
        column: f"value-{index}" for index, column in enumerate(inventory.CSV_COLUMNS)
    }
    complete["path"] = "one"
    complete["classification"] = "A"
    complete["include in Git yes/no"] = "yes"

    with pytest.raises(ValueError, match="duplicate path"):
        inventory.validate_inventory([complete, complete.copy()], {"one"})

    blank = complete.copy()
    blank["reason"] = ""
    with pytest.raises(ValueError, match="blank fields"):
        inventory.validate_inventory([blank], {"one"})
