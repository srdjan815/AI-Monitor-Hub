from __future__ import annotations

import ast
import inspect
import textwrap
from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.attribute_dependency_service import (
    AttributeDependencyService,
)
from app.modules.catalog.attribute_family_service import AttributeFamilyService
from app.modules.catalog.attribute_formula_service import AttributeFormulaService
from app.modules.catalog.attribute_prompt_service import AttributePromptService
from app.modules.catalog.attribute_template_service import (
    AttributeTemplateService,
)
from app.modules.catalog.attribute_usage_service import AttributeUsageService
from app.modules.catalog.attribute_value_mutation_service import (
    AttributeValueMutationService,
)
from app.modules.catalog.platform_service import AttributePlatformService
from app.modules.catalog.platform_service_support import _PlatformServiceSupport


RESPONSIBILITIES = {
    AttributeFamilyService: {
        "create_family",
        "update_family",
        "list_families",
        "add_family_item",
        "assign_family_category",
        "assign_family_template",
        "remove_family_category",
        "remove_family_template",
        "deactivate_family_item",
        "family_usage",
    },
    AttributeTemplateService: {
        "create_template",
        "update_template",
        "list_templates",
        "add_template_item",
        "deactivate_template_item",
        "template_export",
        "import_template",
        "clone_template",
        "assign_template",
        "unassign_template",
    },
    AttributeFormulaService: {
        "create_formula",
        "list_formulas",
        "update_formula",
        "preview_formula",
    },
    AttributeDependencyService: {
        "create_dependency",
        "list_dependencies",
        "deactivate_dependency",
        "validate_dependencies",
    },
    AttributePromptService: {
        "create_prompt",
        "list_prompt_versions",
        "activate_prompt",
        "prompt_diff",
    },
    AttributeUsageService: {"usage"},
    AttributeValueMutationService: {
        "recalculate_product",
        "lock_value",
        "bulk_update",
    },
}


def test_compatibility_facade_retains_complete_public_surface() -> None:
    expected = set().union(*RESPONSIBILITIES.values())
    actual = {
        name
        for name, value in inspect.getmembers(
            AttributePlatformService,
            inspect.iscoroutinefunction,
        )
        if not name.startswith("_")
    }

    assert len(expected) == 36
    assert actual == expected
    for service, methods in RESPONSIBILITIES.items():
        assert issubclass(AttributePlatformService, service)
        for method in methods:
            assert getattr(AttributePlatformService, method) is getattr(
                service,
                method,
            )


def test_responsibility_services_share_one_transaction_support() -> None:
    assert AttributePlatformService._commit is _PlatformServiceSupport._commit
    assert AttributePlatformService._required is _PlatformServiceSupport._required
    assert {
        name
        for name, value in AttributePlatformService.__dict__.items()
        if inspect.iscoroutinefunction(value)
    } == set()


def test_facade_initializes_one_shared_session_boundary() -> None:
    session = MagicMock(spec=AsyncSession)

    service = AttributePlatformService(session)

    assert service.session is session
    assert service.repository.session is session
    assert service.attributes.session is session


def test_responsibility_methods_do_not_hide_local_imports() -> None:
    for service in RESPONSIBILITIES:
        tree = ast.parse(textwrap.dedent(inspect.getsource(service)))
        for method in (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            local_imports = [
                node
                for node in ast.walk(method)
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ]
            assert local_imports == [], f"{service.__name__}.{method.name}"
