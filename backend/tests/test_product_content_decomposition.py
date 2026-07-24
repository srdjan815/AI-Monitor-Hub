from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

from app.modules.product_content.configuration_repository import (
    ConfigurationRepository,
)
from app.modules.product_content.configuration_service import (
    ConfigurationService,
)
from app.modules.product_content.library_service import LibraryService
from app.modules.product_content.library_repository import LibraryRepository
from app.modules.product_content.prompt_service import PromptService
from app.modules.product_content.reference_service import ReferenceService
from app.modules.product_content.repositories import ContentRepository
from app.modules.product_content.revision_repository import RevisionRepository
from app.modules.product_content.revision_service import RevisionService
from app.modules.product_content.scoring_repository import ScoringRepository
from app.modules.product_content.services import (
    ConfigurationService as PublicConfigurationService,
)
from app.modules.product_content.services import (
    LibraryService as PublicLibraryService,
)
from app.modules.product_content.services import (
    PromptService as PublicPromptService,
)
from app.modules.product_content.services import (
    ReferenceService as PublicReferenceService,
)
from app.modules.product_content.services import (
    RevisionService as PublicRevisionService,
)
from app.modules.product_content.services import (
    TemplateService as PublicTemplateService,
)
from app.modules.product_content.template_service import TemplateService

CONTENT_ROOT = (
    Path(__file__).resolve().parents[1] / "app" / "modules" / "product_content"
)
REPOSITORY_FILES = (
    "repository_support.py",
    "configuration_repository.py",
    "revision_repository.py",
    "library_repository.py",
    "scoring_repository.py",
)
SERVICE_FILES = (
    "service_support.py",
    "configuration_service.py",
    "revision_service.py",
    "reference_service.py",
    "library_service.py",
    "template_service.py",
    "prompt_service.py",
)


def test_content_repository_facade_preserves_domain_surface() -> None:
    expected = {
        "content_search",
        "content_history_page",
        "languages",
        "content_types",
        "references",
        "revision_entities",
        "library_items",
        "library_history_page",
        "templates",
        "score_history",
        "scoring_policies",
        "prompt_history_page",
        "global_search",
    }
    assert all(hasattr(ContentRepository, name) for name in expected)


def test_content_repository_uses_one_shared_session() -> None:
    session = MagicMock()
    repository = ContentRepository(session)
    assert repository.session is session


def test_content_service_exports_preserve_public_identities() -> None:
    assert PublicConfigurationService is ConfigurationService
    assert PublicRevisionService is RevisionService
    assert PublicReferenceService is ReferenceService
    assert PublicLibraryService is LibraryService
    assert PublicTemplateService is TemplateService
    assert PublicPromptService is PromptService


def test_content_repository_responsibilities_are_disjoint() -> None:
    assert hasattr(ConfigurationRepository, "languages")
    assert not hasattr(ConfigurationRepository, "content_search")
    assert hasattr(RevisionRepository, "content_search")
    assert not hasattr(RevisionRepository, "library_items")
    assert hasattr(LibraryRepository, "library_items")
    assert not hasattr(LibraryRepository, "score_history")
    assert hasattr(ScoringRepository, "score_history")
    assert not hasattr(ScoringRepository, "content_history")


def test_content_repositories_stay_transaction_neutral_and_cohesive() -> None:
    for name in REPOSITORY_FILES:
        path = CONTENT_ROOT / name
        source = path.read_text(encoding="utf-8")
        assert len(source.splitlines()) <= 350, name
        tree = ast.parse(source, filename=str(path))
        forbidden = [
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"commit", "rollback"}
        ]
        assert forbidden == [], name


def test_content_service_files_remain_cohesive() -> None:
    for name in SERVICE_FILES:
        path = CONTENT_ROOT / name
        source = path.read_text(encoding="utf-8")
        assert len(source.splitlines()) <= 350, name
        ast.parse(source, filename=str(path))
