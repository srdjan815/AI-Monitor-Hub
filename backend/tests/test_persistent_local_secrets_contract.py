from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _repository_file(*parts: str) -> Path:
    path = ROOT.joinpath(*parts)
    if not path.exists():
        pytest.skip("Repository root is not mounted inside the backend container")
    return path


def test_compose_mounts_the_same_persistent_secrets_for_api_and_worker() -> None:
    compose = _repository_file("docker-compose.yml").read_text(encoding="utf-8")

    assert compose.count(".env.secrets") == 2
    assert compose.count(
        "./config/supplier-secrets.json:/app/config/supplier-secrets.json:rw"
    ) == 2
    assert compose.count("SUPPLIER_SECRETS_FILE: /app/config/supplier-secrets.json") == 2
    assert compose.count("SUPPLIER_SECRET_MODE: file") == 2
    assert compose.count("AUTH_MODE: static") == 2


def test_launcher_validates_but_never_generates_secrets() -> None:
    launcher = (
        _repository_file("launcher", "AI-Monitor-Hub-Launcher.ps1")
    ).read_text(encoding="utf-8")

    assert "Assert-SecretConfiguration" in launcher
    assert "AI_MONITOR_ADMIN_TOKEN" in launcher
    assert "ConvertFrom-Json" in launcher
    assert "Authorization = \"Bearer $token\"" in launcher
    assert "New-Guid" not in launcher
    assert "RandomNumberGenerator" not in launcher
