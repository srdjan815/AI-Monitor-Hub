from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import os
import re
import subprocess
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


CLASSIFICATION_OUTPUT = PurePosixPath("docs/audits/final-git-file-classification.csv")
SECRET_REPORT_OUTPUT = PurePosixPath("docs/security/secret-scan-report.md")
OUTPUT_PATHS = frozenset({CLASSIFICATION_OUTPUT, SECRET_REPORT_OUTPUT})
CSV_COLUMNS = (
    "path",
    "current Git state",
    "classification",
    "canonical owner",
    "referenced by",
    "include in Git yes/no",
    "reason",
    "secret scan result",
    "duplicate check",
    "intended commit group",
)
CLASSIFICATIONS = frozenset("ABCDEFGHIJKL")
TEXT_SAMPLE_BYTES = 8_192

GENERATED_VERSIONED_PATHS = frozenset(
    {
        PurePosixPath("backend/mypy-baseline.json"),
        PurePosixPath("docs/audits/api-operation-matrix.json"),
        PurePosixPath("docs/audits/openapi-normalized.json"),
        PurePosixPath("docs/audits/request-boundary-inventory.json"),
        *OUTPUT_PATHS,
    }
)
GENERATED_UNVERSIONED_NAMES = frozenset(
    {
        ".coverage",
        "coverage.json",
        "coverage.xml",
        "junit.xml",
    }
)
TEMPORARY_SUFFIXES = frozenset(
    {
        ".7z",
        ".bak",
        ".log",
        ".orig",
        ".pid",
        ".prof",
        ".pyc",
        ".sqlite",
        ".sqlite3",
        ".tar",
        ".tmp",
        ".zip",
    }
)
BACKUP_SUFFIXES = frozenset({".bak", ".copy", ".old", ".orig"})
SYNTHETIC_SIGNALS = (
    "change-me",
    "development-only",
    "dummy",
    "example",
    "fake",
    "invalid",
    "local-development",
    "must-never-be-logged",
    "not-a-real",
    "placeholder",
    "pytest",
    "redacted",
    "synthetic",
    "test-only",
)
SYNTHETIC_VALUES = frozenset(
    {
        "changeme",
        "nondefault",
        "password",
        "postgres",
        "test",
        "test-password",
        "test-secret",
    }
)


@dataclass(frozen=True)
class SecretRule:
    name: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    rule: str
    disposition: str
    fingerprint: str


@dataclass(frozen=True)
class ScanResult:
    findings: tuple[SecretFinding, ...]
    binary_paths: frozenset[str]
    unreadable_paths: frozenset[str]


@dataclass(frozen=True)
class DuplicateResult:
    descriptions: dict[str, str]
    proven_obsolete: frozenset[str]


SECRET_RULES = (
    SecretRule(
        "private-key",
        re.compile(
            r"(?P<value>-{5}BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?"
            r"PRIVATE KEY-{5})"
        ),
    ),
    SecretRule(
        "certificate",
        re.compile(r"(?P<value>-{5}BEGIN CERTIFICATE-{5})"),
    ),
    SecretRule(
        "github-token",
        re.compile(r"(?P<value>\bgh[pousr]_[A-Za-z0-9]{20,}\b)"),
    ),
    SecretRule(
        "openai-token",
        re.compile(r"(?P<value>\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b)"),
    ),
    SecretRule(
        "slack-token",
        re.compile(r"(?P<value>\bxox[baprs]-[A-Za-z0-9-]{16,}\b)"),
    ),
    SecretRule(
        "aws-access-key",
        re.compile(r"(?P<value>\b(?:AKIA|ASIA)[A-Z0-9]{16}\b)"),
    ),
    SecretRule(
        "google-api-key",
        re.compile(r"(?P<value>\bAIza[0-9A-Za-z_-]{30,}\b)"),
    ),
    SecretRule(
        "bearer-token",
        re.compile(r"(?i)\bBearer\s+(?P<value>[A-Za-z0-9._~-]{16,})"),
    ),
    SecretRule(
        "credential-url",
        re.compile(
            r"(?i)(?:[a-z][a-z0-9+.-]*://)"
            r"(?P<value>[^/\s:@]+:[^/\s@]+)@"
        ),
    ),
    SecretRule(
        "literal-credential",
        re.compile(
            r"""(?ix)
            \b(?:api[_-]?key|auth[_-]?secret|client[_-]?secret|
                docker[_-]?password|hmac[_-]?(?:key|secret)|
                pass(?:word|wd)|session[_-]?(?:cookie|secret))\b
            \s*(?::\s*[^=\n]+)?\s*(?:=|:)\s*
            ["']?(?P<value>[^"'\s,;}#]{4,})
            """
        ),
    ),
    SecretRule(
        "docker-auth",
        re.compile(
            r"""(?ix)
            \b(?:DOCKER_AUTH_CONFIG|docker[_-]?auth)\b
            \s*(?:=|:)\s*["']?(?P<value>[^"'\s,;}#]{8,})
            """
        ),
    ),
    SecretRule(
        "absolute-windows-path",
        re.compile(
            r"""(?ix)
            (?<![A-Za-z0-9])
            (?P<value>[A-Za-z]:[\\/](?![\\/])[^<>"|?*\r\n]+)
            """
        ),
    ),
    SecretRule(
        "absolute-user-path",
        re.compile(
            r"""(?x)
            (?<![A-Za-z0-9])
            (?P<value>/(?:home|Users)/[^/\s"'<>`]+(?:/[^\s"'<>`]*)?)
            """
        ),
    ),
)


def _run_git(repo_root: Path, arguments: Sequence[str]) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *arguments],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(arguments)} failed: {message}")
    return result.stdout


def _decode_git_path(raw_path: bytes) -> PurePosixPath:
    decoded = raw_path.decode("utf-8", errors="surrogateescape").replace("\\", "/")
    path = PurePosixPath(decoded)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"unsafe path returned by Git: {decoded!r}")
    return path


def _git_path_set(repo_root: Path, arguments: Sequence[str]) -> set[PurePosixPath]:
    payload = _run_git(repo_root, [*arguments, "-z"])
    if payload and not payload.endswith(b"\0"):
        raise RuntimeError("Git returned a malformed non-NUL-terminated path list")
    return {_decode_git_path(raw_path) for raw_path in payload.split(b"\0") if raw_path}


def collect_git_paths(
    repo_root: Path,
) -> tuple[set[PurePosixPath], set[PurePosixPath]]:
    tracked = _git_path_set(repo_root, ["ls-files"])
    untracked = _git_path_set(
        repo_root,
        ["ls-files", "--others", "--exclude-standard"],
    )
    return tracked, untracked


def _git_states(
    repo_root: Path,
    tracked: set[PurePosixPath],
    untracked: set[PurePosixPath],
) -> dict[PurePosixPath, str]:
    unstaged = _git_path_set(repo_root, ["diff", "--name-only"])
    staged = _git_path_set(repo_root, ["diff", "--cached", "--name-only"])
    states: dict[PurePosixPath, str] = {}
    for path in sorted(tracked | untracked | set(OUTPUT_PATHS), key=str):
        if path in untracked or path not in tracked:
            states[path] = "untracked"
            continue
        is_staged = path in staged
        is_unstaged = path in unstaged
        exists = _filesystem_path(repo_root, path).exists()
        if not exists:
            suffix = "staged" if is_staged else "unstaged"
            states[path] = f"tracked: deleted ({suffix})"
        elif is_staged and is_unstaged:
            states[path] = "tracked: staged and unstaged changes"
        elif is_staged:
            states[path] = "tracked: staged changes"
        elif is_unstaged:
            states[path] = "tracked: unstaged changes"
        else:
            states[path] = "tracked: clean"
    return states


def _filesystem_path(repo_root: Path, path: PurePosixPath) -> Path:
    candidate = repo_root.joinpath(*path.parts)
    if os.path.commonpath((repo_root.resolve(), candidate.resolve())) != str(
        repo_root.resolve()
    ):
        raise ValueError(f"path escapes repository root: {path}")
    return candidate


def _read_repository_file(
    repo_root: Path,
    path: PurePosixPath,
) -> tuple[bytes | None, str | None]:
    candidate = _filesystem_path(repo_root, path)
    if candidate.is_symlink():
        return None, "symbolic-link"
    try:
        if not candidate.is_file():
            return None, "missing"
        return candidate.read_bytes(), None
    except OSError:
        return None, "unreadable"


def _is_explicitly_synthetic(
    path: PurePosixPath,
    value: str,
    context: str,
) -> bool:
    normalized_value = value.strip("\"'").casefold()
    normalized_context = context.casefold()
    if normalized_value in SYNTHETIC_VALUES:
        return True
    value_segments = {
        segment for segment in re.split(r"[^a-z0-9-]+", normalized_value) if segment
    }
    if value_segments & SYNTHETIC_VALUES:
        return True
    if any(signal in normalized_value for signal in SYNTHETIC_SIGNALS):
        return True
    if any(signal in normalized_context for signal in SYNTHETIC_SIGNALS):
        return True
    return path.name.endswith(".example") and (
        normalized_value.startswith("<") or normalized_value.endswith(">")
    )


def _scan_text(
    path: PurePosixPath,
    text: str,
) -> list[SecretFinding]:
    lines = text.splitlines()
    findings: list[SecretFinding] = []
    seen: set[tuple[int, str, str]] = set()
    for line_index, line in enumerate(lines):
        for rule in SECRET_RULES:
            for match in rule.pattern.finditer(line):
                value = match.group("value")
                fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
                identity = (line_index + 1, rule.name, fingerprint)
                if identity in seen:
                    continue
                seen.add(identity)
                disposition = (
                    "SYNTHETIC_TEST_LITERAL"
                    if _is_explicitly_synthetic(path, value, line)
                    else "REVIEW_REQUIRED"
                )
                findings.append(
                    SecretFinding(
                        path=path.as_posix(),
                        line=line_index + 1,
                        rule=rule.name,
                        disposition=disposition,
                        fingerprint=f"sha256:{fingerprint}",
                    )
                )
    return findings


def _scan_env_entries(path: PurePosixPath, text: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        _, value = stripped.split("=", 1)
        value = value.strip()
        if not value:
            continue
        fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
        findings.append(
            SecretFinding(
                path=path.as_posix(),
                line=line_number,
                rule="env-file-entry",
                disposition="REVIEW_REQUIRED",
                fingerprint=f"sha256:{fingerprint}",
            )
        )
    return findings


def scan_repository_files(
    repo_root: Path,
    paths: Iterable[PurePosixPath],
) -> ScanResult:
    findings: list[SecretFinding] = []
    binary_paths: set[str] = set()
    unreadable_paths: set[str] = set()
    for path in sorted(set(paths), key=str):
        if path in OUTPUT_PATHS:
            continue
        payload, error = _read_repository_file(repo_root, path)
        if error is not None:
            unreadable_paths.add(path.as_posix())
            continue
        assert payload is not None
        if b"\0" in payload[:TEXT_SAMPLE_BYTES]:
            binary_paths.add(path.as_posix())
            continue
        text = payload.decode("utf-8", errors="replace")
        findings.extend(_scan_text(path, text))
        if _is_sensitive_env(path):
            findings.extend(_scan_env_entries(path, text))
    return ScanResult(
        findings=tuple(
            sorted(
                findings,
                key=lambda item: (
                    item.path,
                    item.line,
                    item.rule,
                    item.fingerprint,
                ),
            )
        ),
        binary_paths=frozenset(binary_paths),
        unreadable_paths=frozenset(unreadable_paths),
    )


def _file_digests(
    repo_root: Path,
    paths: Iterable[PurePosixPath],
) -> tuple[dict[str, str], dict[str, int]]:
    digests: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for path in sorted(set(paths), key=str):
        normalized = path.as_posix()
        if path in OUTPUT_PATHS:
            continue
        payload, error = _read_repository_file(repo_root, path)
        if error is not None or payload is None:
            continue
        digests[normalized] = hashlib.sha256(payload).hexdigest()
        sizes[normalized] = len(payload)
    return digests, sizes


def _is_backup_name(path: PurePosixPath) -> bool:
    lowered = path.name.casefold()
    return path.suffix.casefold() in BACKUP_SUFFIXES or any(
        marker in lowered for marker in (".backup.", " copy", "_copy.")
    )


def analyze_duplicates(
    repo_root: Path,
    paths: Iterable[PurePosixPath],
) -> DuplicateResult:
    path_set = set(paths)
    digests, sizes = _file_digests(repo_root, path_set)
    by_digest: dict[str, list[str]] = defaultdict(list)
    for normalized_path, digest_value in digests.items():
        by_digest[digest_value].append(normalized_path)

    descriptions: dict[str, str] = {}
    proven_obsolete: set[str] = set()
    for path in sorted(path_set, key=str):
        normalized = path.as_posix()
        if path in OUTPUT_PATHS:
            descriptions[normalized] = "GENERATED_OUTPUT_SELF_REFERENCE"
            continue
        digest = digests.get(normalized)
        if digest is None:
            descriptions[normalized] = "NOT_HASHED_MISSING_OR_NONREGULAR"
            continue
        peers = sorted(by_digest[digest])
        if sizes[normalized] == 0 and path.name == "__init__.py":
            descriptions[normalized] = "INTENTIONAL_EMPTY_PACKAGE_MARKER"
            continue
        if len(peers) == 1:
            descriptions[normalized] = f"UNIQUE sha256:{digest[:16]}"
            continue
        non_backup_peers = [
            peer for peer in peers if not _is_backup_name(PurePosixPath(peer))
        ]
        if _is_backup_name(path) and non_backup_peers:
            canonical = non_backup_peers[0]
            descriptions[normalized] = f"PROVEN_OBSOLETE_DUPLICATE of {canonical}"
            proven_obsolete.add(normalized)
            continue
        if sizes[normalized] == 0:
            descriptions[normalized] = "EMPTY_FILE_WITH_DISTINCT_DECLARED_ROLE"
            continue
        peer_list = "; ".join(peer for peer in peers if peer != normalized)
        descriptions[normalized] = f"IDENTICAL_CONTENT_REVIEW peers: {peer_list}"
    return DuplicateResult(
        descriptions=descriptions,
        proven_obsolete=frozenset(proven_obsolete),
    )


def _python_module(path: PurePosixPath) -> str | None:
    if len(path.parts) < 3 or path.parts[0] != "backend" or path.suffix != ".py":
        return None
    relative = list(path.parts[1:])
    relative[-1] = path.stem
    if relative[-1] == "__init__":
        relative.pop()
    return ".".join(relative)


def _resolve_relative_import(
    module: str,
    is_package: bool,
    node: ast.ImportFrom,
) -> str:
    package_parts = module.split(".") if is_package else module.split(".")[:-1]
    drop_count = max(0, node.level - 1)
    if drop_count:
        package_parts = package_parts[:-drop_count]
    if node.module:
        package_parts.extend(node.module.split("."))
    return ".".join(package_parts)


def _imported_modules(
    tree: ast.AST,
    module: str,
    is_package: bool,
) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative_import(module, is_package, node)
                if node.level
                else node.module or ""
            )
            if base:
                imports.add(base)
                imports.update(
                    f"{base}.{alias.name}" for alias in node.names if alias.name != "*"
                )
    return imports


def _nearest_known_module(
    imported: str,
    module_paths: dict[str, PurePosixPath],
) -> PurePosixPath | None:
    parts = imported.split(".")
    while parts:
        candidate = ".".join(parts)
        if candidate in module_paths:
            return module_paths[candidate]
        parts.pop()
    return None


def build_reference_index(
    repo_root: Path,
    paths: Iterable[PurePosixPath],
) -> dict[str, set[str]]:
    path_set = set(paths)
    module_paths = {
        module: path
        for path in path_set
        if (module := _python_module(path)) is not None
    }
    references: dict[str, set[str]] = defaultdict(set)
    for source_path in sorted(path_set, key=str):
        module = _python_module(source_path)
        if module is None:
            continue
        payload, error = _read_repository_file(repo_root, source_path)
        if error is not None or payload is None:
            continue
        try:
            tree = ast.parse(payload.decode("utf-8"), filename=source_path.as_posix())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for imported in _imported_modules(
            tree,
            module,
            source_path.name == "__init__.py",
        ):
            target = _nearest_known_module(imported, module_paths)
            if target is not None and target != source_path:
                references[target.as_posix()].add(source_path.as_posix())
    _add_migration_references(repo_root, path_set, references)
    return references


def _string_assignment(tree: ast.AST, name: str) -> str | None:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == name for target in targets
        ):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return None


def _add_migration_references(
    repo_root: Path,
    paths: set[PurePosixPath],
    references: dict[str, set[str]],
) -> None:
    revisions: dict[str, PurePosixPath] = {}
    migration_trees: list[tuple[PurePosixPath, ast.AST]] = []
    for path in sorted(paths, key=str):
        if not _is_migration(path):
            continue
        payload, error = _read_repository_file(repo_root, path)
        if error is not None or payload is None:
            continue
        try:
            migration_tree = ast.parse(
                payload.decode("utf-8"),
                filename=path.as_posix(),
            )
        except (SyntaxError, UnicodeDecodeError):
            continue
        revision = _string_assignment(migration_tree, "revision")
        if revision:
            revisions[revision] = path
        migration_trees.append((path, migration_tree))
    for child_path, child_tree in migration_trees:
        down_revision = _string_assignment(child_tree, "down_revision")
        parent_path = revisions.get(down_revision or "")
        if parent_path is not None:
            references[parent_path.as_posix()].add(child_path.as_posix())


def _is_migration(path: PurePosixPath) -> bool:
    return (
        len(path.parts) >= 4
        and path.parts[:3] == ("backend", "alembic", "versions")
        and path.suffix == ".py"
    )


def _is_configuration(path: PurePosixPath) -> bool:
    if path.parts and path.parts[0] == ".vscode":
        return True
    if path.name in {
        ".dockerignore",
        ".editorconfig",
        ".env.example",
        ".gitattributes",
        ".gitignore",
        ".python-version",
        "Dockerfile",
    }:
        return True
    if path.name.startswith("docker-compose") and path.suffix in {".yml", ".yaml"}:
        return True
    if path.as_posix() in {
        "backend/alembic.ini",
        "backend/alembic/README",
        "backend/alembic/env.py",
        "backend/alembic/script.py.mako",
        "backend/pyproject.toml",
        "backend/requirements.lock",
    }:
        return True
    return False


def _is_documentation(path: PurePosixPath) -> bool:
    return (path.parts and path.parts[0] == "docs") or path.suffix.casefold() in {
        ".md",
        ".rst",
    }


def _is_generated_unversioned(path: PurePosixPath) -> bool:
    normalized = path.as_posix().casefold()
    return (
        path.name.casefold() in GENERATED_UNVERSIONED_NAMES
        or "/htmlcov/" in f"/{normalized}/"
        or "/benchmark-results/" in f"/{normalized}/"
    )


def _is_temporary(path: PurePosixPath) -> bool:
    normalized = path.as_posix().casefold()
    return (
        path.suffix.casefold() in TEMPORARY_SUFFIXES
        or "__pycache__" in path.parts
        or normalized.startswith(("tmp/", "temp/", "checkpoints/"))
    )


def _secret_result_for_path(path: PurePosixPath, scan: ScanResult) -> str:
    normalized = path.as_posix()
    if path in OUTPUT_PATHS:
        return "CLEAN_GENERATED_FROM_REDACTED_DATA"
    if normalized in scan.unreadable_paths:
        return "NOT_SCANNED_MISSING_UNREADABLE_OR_NONREGULAR"
    if normalized in scan.binary_paths:
        return "NO_TEXT_SCAN_BINARY"
    findings = [finding for finding in scan.findings if finding.path == normalized]
    if not findings:
        return "CLEAN"
    rules = ",".join(sorted({finding.rule for finding in findings}))
    if any(finding.disposition == "REVIEW_REQUIRED" for finding in findings):
        return f"REVIEW_REQUIRED:{rules}"
    return f"SYNTHETIC_TEST_LITERAL_ONLY:{rules}"


def _classification(
    path: PurePosixPath,
    *,
    exists: bool,
    secret_result: str,
    duplicate_result: DuplicateResult,
) -> tuple[str, bool, str]:
    exceptional = _exception_classification(
        path,
        exists=exists,
        secret_result=secret_result,
        duplicate_result=duplicate_result,
    )
    if exceptional is not None:
        return exceptional
    return _canonical_classification(path)


def _exception_classification(
    path: PurePosixPath,
    *,
    exists: bool,
    secret_result: str,
    duplicate_result: DuplicateResult,
) -> tuple[str, bool, str] | None:
    normalized = path.as_posix()
    if path in GENERATED_VERSIONED_PATHS:
        return "G", True, "deterministically generated release or contract artifact"
    if secret_result.startswith("REVIEW_REQUIRED") or _is_sensitive_env(path):
        return "J", False, "sensitive content requires removal or explicit review"
    if normalized in duplicate_result.proven_obsolete:
        return "K", False, "byte-identical backup copy with a canonical peer"
    if not exists:
        return "L", False, "tracked or enumerated path is missing or nonregular"
    if _is_generated_unversioned(path):
        return "H", False, "reproducible local tool output"
    if _is_temporary(path):
        return "I", False, "local temporary or cache artifact"
    return None


def _canonical_classification(path: PurePosixPath) -> tuple[str, bool, str]:
    if _is_migration(path):
        return "B", True, "canonical Alembic revision"
    if len(path.parts) >= 2 and path.parts[:2] == ("backend", "tests"):
        return "C", True, "collected pytest source"
    if len(path.parts) >= 2 and path.parts[:2] == ("backend", "scripts"):
        return "D", True, "maintained benchmark or release script"
    if len(path.parts) >= 2 and path.parts[:2] == ("backend", "app"):
        return "A", True, "production application source"
    if _is_configuration(path):
        return "E", True, "required repository, build, or development configuration"
    if _is_documentation(path):
        return (
            "F",
            True,
            "maintained architecture, security, or operations documentation",
        )
    return "L", False, "no canonical owner rule; manual review is required"


def _is_sensitive_env(path: PurePosixPath) -> bool:
    name = path.name.casefold()
    return name == ".env" or (
        name.startswith(".env.")
        and not name.endswith(".example")
        and name != ".env.example"
    )


def _owner(path: PurePosixPath, classification: str) -> str:
    if path in OUTPUT_PATHS:
        return "backend/scripts/generate_release_inventory.py"
    if classification == "A":
        domain = path.parts[3] if len(path.parts) > 3 else "application"
        return f"backend application: {domain}"
    if classification == "G":
        return _generated_owner(path)
    owners = {
        "B": "Alembic migration graph",
        "C": "pytest regression suite",
        "D": "release and performance engineering",
        "E": "repository and build configuration",
        "F": "project documentation",
        "H": "local reproducible tooling",
        "I": "local developer workspace",
        "J": "secret owner; not repository-owned",
        "K": "canonical duplicate peer",
        "L": "manual repository review",
    }
    return owners[classification]


def _generated_owner(path: PurePosixPath) -> str:
    if path == PurePosixPath("backend/mypy-baseline.json"):
        return "static typing verification procedure"
    return "backend/scripts/generate_contract_reports.py"


def _default_reference(path: PurePosixPath, classification: str) -> str:
    if path in OUTPUT_PATHS:
        return "release procedure and final release review"
    defaults = {
        "A": "Python package discovery and Docker application image",
        "B": "backend/alembic/env.py and Alembic revision chain",
        "C": "pytest automatic discovery",
        "D": "developer and release procedures",
        "E": "Git, Docker, Python, or VS Code tooling",
        "F": "developer, operator, and architecture review",
        "G": "contract or release verification gate",
        "H": "local generator only",
        "I": "local process only",
        "J": "local secret/configuration consumer only",
        "K": "no canonical reference; duplicate only",
        "L": "no verified reference",
    }
    return defaults[classification]


def _references(
    path: PurePosixPath,
    classification: str,
    reference_index: dict[str, set[str]],
) -> str:
    explicit = sorted(reference_index.get(path.as_posix(), set()))
    if explicit:
        return "; ".join(explicit)
    return _default_reference(path, classification)


def _commit_group(path: PurePosixPath, classification: str) -> str:
    normalized = path.as_posix()
    if classification in {"H", "I", "J", "K", "L"}:
        return "not-staged"
    direct_groups = {
        "B": "06-alembic-migrations",
        "C": "07-tests",
        "E": "09-build-and-cross-platform-environment",
        "F": "10-documentation-and-release-evidence",
        "G": "10-documentation-and-release-evidence",
    }
    if classification == "D" or path in {
        PurePosixPath("docs/audits/api-operation-matrix.json"),
        PurePosixPath("docs/audits/openapi-normalized.json"),
        PurePosixPath("docs/audits/request-boundary-inventory.json"),
    }:
        return "08-benchmarks-and-contract-generators"
    if normalized == "backend/mypy-baseline.json":
        return "09-build-and-cross-platform-environment"
    if classification in direct_groups:
        return direct_groups[classification]
    module_groups = (
        ("backend/app/modules/catalog/", "02-catalog-and-product-attributes"),
        ("backend/app/modules/inventory/", "03-inventory"),
        ("backend/app/modules/product_content/", "04-product-content"),
        ("backend/app/modules/execution/", "05-execution"),
    )
    for prefix, group in module_groups:
        if normalized.startswith(prefix):
            return group
    return "01-core-security-pagination-and-observability"


def build_inventory_rows(repo_root: Path) -> tuple[list[dict[str, str]], ScanResult]:
    tracked, untracked = collect_git_paths(repo_root)
    paths = tracked | untracked | set(OUTPUT_PATHS)
    states = _git_states(repo_root, tracked, untracked)
    scan = scan_repository_files(repo_root, paths)
    duplicates = analyze_duplicates(repo_root, paths)
    references = build_reference_index(repo_root, paths)
    rows: list[dict[str, str]] = []
    for path in sorted(paths, key=str):
        candidate = _filesystem_path(repo_root, path)
        exists = candidate.is_file() and not candidate.is_symlink()
        if path in OUTPUT_PATHS:
            exists = True
        secret_result = _secret_result_for_path(path, scan)
        classification, include, reason = _classification(
            path,
            exists=exists,
            secret_result=secret_result,
            duplicate_result=duplicates,
        )
        rows.append(
            {
                "path": path.as_posix(),
                "current Git state": states[path],
                "classification": classification,
                "canonical owner": _owner(path, classification),
                "referenced by": _references(path, classification, references),
                "include in Git yes/no": "yes" if include else "no",
                "reason": reason,
                "secret scan result": secret_result,
                "duplicate check": duplicates.descriptions[path.as_posix()],
                "intended commit group": _commit_group(path, classification),
            }
        )
    validate_inventory(rows, {path.as_posix() for path in paths})
    return rows, scan


def validate_inventory(
    rows: Sequence[dict[str, str]],
    expected_paths: set[str],
) -> None:
    actual_paths = [row.get("path", "") for row in rows]
    if len(actual_paths) != len(set(actual_paths)):
        raise ValueError("inventory contains duplicate path rows")
    if set(actual_paths) != expected_paths:
        missing = sorted(expected_paths - set(actual_paths))
        unexpected = sorted(set(actual_paths) - expected_paths)
        raise ValueError(
            f"inventory path mismatch; missing={missing!r}; unexpected={unexpected!r}"
        )
    for row in rows:
        missing_columns = [column for column in CSV_COLUMNS if not row.get(column, "")]
        if missing_columns:
            raise ValueError(
                f"inventory row {row.get('path')!r} has blank fields: "
                f"{missing_columns!r}"
            )
        if row["classification"] not in CLASSIFICATIONS:
            raise ValueError(
                f"invalid classification for {row['path']}: {row['classification']!r}"
            )
        if row["include in Git yes/no"] not in {"yes", "no"}:
            raise ValueError(f"invalid Git inclusion decision for {row['path']}")


def _csv_bytes(rows: Sequence[dict[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=CSV_COLUMNS,
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _secret_report_bytes(scan: ScanResult, path_count: int) -> bytes:
    review_count = sum(
        finding.disposition == "REVIEW_REQUIRED" for finding in scan.findings
    )
    synthetic_count = len(scan.findings) - review_count
    verdict = "PASS" if review_count == 0 and not scan.unreadable_paths else "FAIL"
    lines = [
        "# Deterministic secret and sensitive-data scan",
        "",
        "This report is generated by "
        "`backend/scripts/generate_release_inventory.py`. It contains only "
        "rule names and truncated SHA-256 fingerprints; matched values and "
        "source lines are deliberately omitted.",
        "",
        f"- Verdict: **{verdict}**",
        f"- Git-visible paths assessed: {path_count}",
        f"- Review-required findings: {review_count}",
        f"- Explicitly synthetic test/example findings: {synthetic_count}",
        f"- Binary files (text scan not applicable): {len(scan.binary_paths)}",
        f"- Missing, unreadable, or nonregular paths: {len(scan.unreadable_paths)}",
        "- Scope: union of tracked paths and untracked nonignored paths, plus "
        "the two generated release reports.",
        "- Detection: private keys, certificates, strong provider token "
        "prefixes, bearer credentials, credential-bearing URLs, literal "
        "password/secret assignments, Docker credentials, `.env` files, and "
        "absolute machine paths.",
        "",
        "## Redacted findings",
        "",
        "| Path | Line | Rule | Disposition | Redacted fingerprint |",
        "|---|---:|---|---|---|",
    ]
    if scan.findings:
        lines.extend(
            "| `{}` | {} | {} | {} | `{}` |".format(
                finding.path.replace("|", "\\|"),
                finding.line,
                finding.rule,
                finding.disposition,
                finding.fingerprint,
            )
            for finding in scan.findings
        )
    else:
        lines.append("| _none_ | - | - | - | - |")
    if scan.binary_paths:
        lines.extend(
            [
                "",
                "## Binary paths",
                "",
                *[f"- `{path}`" for path in sorted(scan.binary_paths)],
            ]
        )
    if scan.unreadable_paths:
        lines.extend(
            [
                "",
                "## Paths requiring manual access review",
                "",
                *[f"- `{path}`" for path in sorted(scan.unreadable_paths)],
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A `SYNTHETIC_TEST_LITERAL` disposition requires an explicit marker "
            "such as `synthetic`, `test-only`, `not-a-real`, `placeholder`, or "
            "a known local-development value. A path under `tests/` alone does "
            "not suppress a finding. Any `REVIEW_REQUIRED` finding blocks "
            "automatic Git inclusion.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def generate_release_inventory(repo_root: Path) -> list[dict[str, str]]:
    resolved_root = repo_root.resolve()
    reported_root = _run_git(resolved_root, ["rev-parse", "--show-toplevel"])
    git_root = Path(reported_root.decode("utf-8").strip()).resolve()
    if git_root != resolved_root:
        raise ValueError(
            f"repository root must be {git_root}; received {resolved_root}"
        )
    rows, scan = build_inventory_rows(resolved_root)
    classification_path = _filesystem_path(resolved_root, CLASSIFICATION_OUTPUT)
    secret_report_path = _filesystem_path(resolved_root, SECRET_REPORT_OUTPUT)
    classification_path.parent.mkdir(parents=True, exist_ok=True)
    secret_report_path.parent.mkdir(parents=True, exist_ok=True)
    secret_report_path.write_bytes(_secret_report_bytes(scan, len(rows)))
    classification_path.write_bytes(_csv_bytes(rows))
    return rows


def _parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify every tracked and untracked nonignored repository path "
            "and generate a redacted deterministic secret scan."
        )
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
        help="Git repository root (default: current working directory)",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parse_args(arguments)
    rows = generate_release_inventory(args.repository_root)
    included = sum(row["include in Git yes/no"] == "yes" for row in rows)
    blocked = len(rows) - included
    print(
        f"release inventory generated: {len(rows)} paths, "
        f"{included} include, {blocked} excluded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
