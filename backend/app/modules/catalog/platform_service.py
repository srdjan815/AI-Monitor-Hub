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
from app.modules.catalog.platform_service_support import _PlatformServiceSupport


__all__ = ["AttributePlatformService"]


class AttributePlatformService(
    AttributeFamilyService,
    AttributeTemplateService,
    AttributeFormulaService,
    AttributeDependencyService,
    AttributePromptService,
    AttributeUsageService,
    AttributeValueMutationService,
):
    """Backward-compatible facade over cohesive platform responsibilities."""

    def __init__(self, session: AsyncSession) -> None:
        _PlatformServiceSupport.__init__(self, session)
