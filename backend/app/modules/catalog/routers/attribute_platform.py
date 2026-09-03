from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_DB_INTEGER, MAX_LEGACY_OFFSET, MAX_SEARCH_CHARS
from app.db.session import get_db
from app.modules.catalog.platform_models import (
    AttributeDependency,
    AttributeFamily,
    AttributeFormula,
    AttributePromptVersion,
    AttributeTemplate,
)
from app.modules.catalog.platform_service import AttributePlatformService
from app.modules.catalog.schemas.attribute_platform import (
    DependencyCreate,
    DependencyRead,
    EnterpriseBulkWrite,
    FamilyItemCreate,
    FamilyRead,
    FormulaCreate,
    FormulaPreview,
    FormulaRead,
    FormulaUpdate,
    LockRequest,
    NamedEntityCreate,
    NamedEntityUpdate,
    PromptVersionCreate,
    PromptVersionRead,
    TemplateCreate,
    TemplateImport,
    TemplateItemCreate,
    TemplateRead,
    TemplateUpdate,
)

router = APIRouter(prefix="/catalog", tags=["attribute-platform"])


@router.post(
    "/attribute-families",
    response_model=FamilyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_family(
    payload: NamedEntityCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributeFamily:
    return await AttributePlatformService(session).create_family(payload)


@router.get("/attribute-families", response_model=list[FamilyRead])
async def list_families(
    active_only: bool = True,
    search: str | None = Query(default=None, max_length=MAX_SEARCH_CHARS),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[AttributeFamily]:
    return await AttributePlatformService(session).list_families(
        active_only=active_only, search=search, offset=offset, limit=limit
    )


@router.get("/attribute-families/{family_id:uuid}", response_model=FamilyRead)
async def get_family(
    family_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> AttributeFamily:
    return await AttributePlatformService(session)._required(
        AttributeFamily, family_id, "Family"
    )


@router.patch("/attribute-families/{family_id:uuid}", response_model=FamilyRead)
async def update_family(
    family_id: uuid.UUID,
    payload: NamedEntityUpdate,
    session: AsyncSession = Depends(get_db),
) -> AttributeFamily:
    return await AttributePlatformService(session).update_family(family_id, payload)


@router.delete(
    "/attribute-families/{family_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_family(
    family_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> Response:
    await AttributePlatformService(session).update_family(
        family_id, NamedEntityUpdate(is_active=False)
    )
    return Response(status_code=204)


@router.post(
    "/attribute-families/{family_id:uuid}/items",
    status_code=status.HTTP_201_CREATED,
)
async def add_family_item(
    family_id: uuid.UUID,
    payload: FamilyItemCreate,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    item = await AttributePlatformService(session).add_family_item(
        family_id, payload.attribute_definition_id, payload.sort_order
    )
    return {"id": item.id, "family_id": item.family_id}


@router.delete("/attribute-family-items/{item_id:uuid}", status_code=204)
async def deactivate_family_item(
    item_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> Response:
    await AttributePlatformService(session).deactivate_family_item(item_id)
    return Response(status_code=204)


@router.post(
    "/attribute-families/{family_id:uuid}/categories/{category_id:uuid}",
    status_code=status.HTTP_201_CREATED,
)
async def assign_family_category(
    family_id: uuid.UUID,
    category_id: uuid.UUID,
    sort_order: int = Query(default=0, ge=0, le=MAX_DB_INTEGER),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    item = await AttributePlatformService(session).assign_family_category(
        family_id, category_id, sort_order
    )
    return {"id": item.id, "category_id": item.category_id}


@router.delete(
    "/attribute-families/{family_id:uuid}/categories/{category_id:uuid}",
    status_code=204,
)
async def remove_family_category(
    family_id: uuid.UUID,
    category_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await AttributePlatformService(session).remove_family_category(
        family_id, category_id
    )
    return Response(status_code=204)


@router.post(
    "/attribute-families/{family_id:uuid}/templates/{template_id:uuid}",
    status_code=201,
)
async def assign_family_template(
    family_id: uuid.UUID,
    template_id: uuid.UUID,
    sort_order: int = Query(default=0, ge=0, le=MAX_DB_INTEGER),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    assignment = await AttributePlatformService(session).assign_family_template(
        family_id, template_id, sort_order
    )
    return {"id": assignment.id}


@router.delete(
    "/attribute-families/{family_id:uuid}/templates/{template_id:uuid}",
    status_code=204,
)
async def remove_family_template(
    family_id: uuid.UUID,
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await AttributePlatformService(session).remove_family_template(
        family_id, template_id
    )
    return Response(status_code=204)


@router.get("/attribute-families/{family_id:uuid}/usage")
async def family_usage(
    family_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> dict[str, int]:
    return await AttributePlatformService(session).family_usage(family_id)


@router.post(
    "/attribute-templates",
    response_model=TemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    payload: TemplateCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributeTemplate:
    return await AttributePlatformService(session).create_template(payload)


@router.get("/attribute-templates", response_model=list[TemplateRead])
async def list_templates(
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[AttributeTemplate]:
    return await AttributePlatformService(session).list_templates(
        active_only, offset, limit
    )


@router.get("/attribute-templates/{template_id:uuid}", response_model=TemplateRead)
async def get_template(
    template_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> AttributeTemplate:
    return await AttributePlatformService(session)._required(
        AttributeTemplate, template_id, "Template"
    )


@router.patch("/attribute-templates/{template_id:uuid}", response_model=TemplateRead)
async def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    session: AsyncSession = Depends(get_db),
) -> AttributeTemplate:
    return await AttributePlatformService(session).update_template(template_id, payload)


@router.delete(
    "/attribute-templates/{template_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_template(
    template_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> Response:
    await AttributePlatformService(session).update_template(
        template_id, TemplateUpdate(is_active=False)
    )
    return Response(status_code=204)


@router.post("/attribute-templates/{template_id:uuid}/items", status_code=201)
async def add_template_item(
    template_id: uuid.UUID,
    payload: TemplateItemCreate,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    item = await AttributePlatformService(session).add_template_item(
        template_id, payload
    )
    return {"id": item.id, "attribute_definition_id": item.attribute_definition_id}


@router.delete("/attribute-template-items/{item_id:uuid}", status_code=204)
async def deactivate_template_item(
    item_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> Response:
    await AttributePlatformService(session).deactivate_template_item(item_id)
    return Response(status_code=204)


@router.get("/attribute-templates/{template_id:uuid}/export")
async def export_template(
    template_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await AttributePlatformService(session).template_export(template_id)


@router.post("/attribute-templates/import", response_model=TemplateRead)
async def import_template(
    payload: TemplateImport,
    session: AsyncSession = Depends(get_db),
) -> AttributeTemplate:
    return await AttributePlatformService(session).import_template(payload)


@router.post(
    "/attribute-templates/{template_id:uuid}/clone",
    response_model=TemplateRead,
)
async def clone_template(
    template_id: uuid.UUID,
    name: str = Query(min_length=1, max_length=255),
    slug: str = Query(min_length=1, max_length=255),
    session: AsyncSession = Depends(get_db),
) -> AttributeTemplate:
    return await AttributePlatformService(session).clone_template(
        template_id, name, slug
    )


@router.post("/attribute-templates/{template_id:uuid}/assign/{category_id:uuid}")
async def assign_template(
    template_id: uuid.UUID,
    category_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    return await AttributePlatformService(session).assign_template(
        template_id, category_id
    )


@router.delete(
    "/attribute-templates/{template_id:uuid}/assign/{category_id:uuid}",
    status_code=204,
)
async def unassign_template(
    template_id: uuid.UUID,
    category_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await AttributePlatformService(session).unassign_template(template_id, category_id)
    return Response(status_code=204)


@router.post("/attribute-formulas", response_model=FormulaRead, status_code=201)
async def create_formula(
    payload: FormulaCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributeFormula:
    return await AttributePlatformService(session).create_formula(payload)


@router.get("/attribute-formulas", response_model=list[FormulaRead])
async def list_formulas(
    kind: str | None = Query(default=None, max_length=32),
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[AttributeFormula]:
    return await AttributePlatformService(session).list_formulas(
        kind=kind,
        active_only=active_only,
        offset=offset,
        limit=limit,
    )


@router.patch("/attribute-formulas/{formula_id:uuid}", response_model=FormulaRead)
async def update_formula(
    formula_id: uuid.UUID,
    payload: FormulaUpdate,
    session: AsyncSession = Depends(get_db),
) -> AttributeFormula:
    return await AttributePlatformService(session).update_formula(formula_id, payload)


@router.delete("/attribute-formulas/{formula_id:uuid}", status_code=204)
async def deactivate_formula(
    formula_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> Response:
    await AttributePlatformService(session).update_formula(
        formula_id, FormulaUpdate(is_active=False)
    )
    return Response(status_code=204)


@router.post("/attribute-formulas/{formula_id:uuid}/preview")
async def preview_formula(
    formula_id: uuid.UUID,
    payload: FormulaPreview,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await AttributePlatformService(session).preview_formula(formula_id, payload)


@router.post("/products/{product_id:uuid}/attributes/recalculate")
async def recalculate_product(
    product_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> dict[str, int]:
    rows = await AttributePlatformService(session).recalculate_product(product_id)
    return {"values_recalculated": len(rows)}


@router.post("/attribute-dependencies", response_model=DependencyRead, status_code=201)
async def create_dependency(
    payload: DependencyCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributeDependency:
    return await AttributePlatformService(session).create_dependency(payload)


@router.get("/attribute-dependencies", response_model=list[DependencyRead])
async def list_dependencies(
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[AttributeDependency]:
    return await AttributePlatformService(session).list_dependencies(
        active_only=active_only,
        offset=offset,
        limit=limit,
    )


@router.delete("/attribute-dependencies/{dependency_id:uuid}", status_code=204)
async def deactivate_dependency(
    dependency_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> Response:
    await AttributePlatformService(session).deactivate_dependency(dependency_id)
    return Response(status_code=204)


@router.get("/products/{product_id:uuid}/attributes/dependencies/validate")
async def validate_dependencies(
    product_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    errors = await AttributePlatformService(session).validate_dependencies(product_id)
    return {"valid": not errors, "errors": errors}


@router.post("/products/{product_id:uuid}/attributes/{attribute_id:uuid}/lock")
async def lock_value(
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    payload: LockRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    value = await AttributePlatformService(session).lock_value(
        product_id, attribute_id, payload, True
    )
    return {"id": value.id, "is_locked": value.is_locked}


@router.post("/products/{product_id:uuid}/attributes/{attribute_id:uuid}/unlock")
async def unlock_value(
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    payload: LockRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    value = await AttributePlatformService(session).lock_value(
        product_id, attribute_id, payload, False
    )
    return {"id": value.id, "is_locked": value.is_locked}


@router.get("/attribute-definitions/{attribute_id:uuid}/usage")
async def attribute_usage(
    attribute_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> dict[str, int]:
    return await AttributePlatformService(session).usage(attribute_id)


@router.post(
    "/attribute-definitions/{attribute_id:uuid}/prompt-versions",
    response_model=PromptVersionRead,
    status_code=201,
)
async def create_prompt_version(
    attribute_id: uuid.UUID,
    payload: PromptVersionCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributePromptVersion:
    return await AttributePlatformService(session).create_prompt(attribute_id, payload)


@router.get(
    "/attribute-definitions/{attribute_id:uuid}/prompt-versions",
    response_model=list[PromptVersionRead],
)
async def list_prompt_versions(
    attribute_id: uuid.UUID,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[AttributePromptVersion]:
    return await AttributePlatformService(session).list_prompt_versions(
        attribute_id,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/attribute-prompt-versions/{prompt_id:uuid}/activate",
    response_model=PromptVersionRead,
)
async def activate_prompt(
    prompt_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> AttributePromptVersion:
    return await AttributePlatformService(session).activate_prompt(prompt_id)


@router.get("/attribute-prompt-versions/{left_id:uuid}/diff/{right_id:uuid}")
async def prompt_diff(
    left_id: uuid.UUID,
    right_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    return await AttributePlatformService(session).prompt_diff(left_id, right_id)


@router.post("/attribute-bulk/preview")
async def bulk_preview(
    payload: EnterpriseBulkWrite,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await AttributePlatformService(session).bulk_update(payload, preview=True)


@router.post("/attribute-bulk/commit")
async def bulk_commit(
    payload: EnterpriseBulkWrite,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await AttributePlatformService(session).bulk_update(payload, preview=False)


@router.get(
    "/attribute-admin/{page}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def platform_admin_page(page: str) -> str:
    allowed = {
        "families",
        "templates",
        "formulas",
        "derived",
        "dependencies",
        "prompts",
        "usage",
        "bulk",
        "locked",
    }
    if page not in allowed:
        return "<h1>Unknown Product Attribute administration page</h1>"
    return f"""<!doctype html><html><head><title>{page.title()}</title>
<style>body{{font:15px system-ui;margin:2rem}}code{{background:#eee;padding:.2rem}}</style>
</head><body><a href="/api/v1/catalog/attribute-admin">← Dashboard</a>
<h1>{page.title()} Administration</h1>
<p>This page uses the canonical Product Attribute Platform API.</p>
<div id="result">Use Swagger or the API-backed controls from the dashboard.</div>
<script>fetch('/api/v1/catalog/attribute-dashboard').then(r=>r.json())
.then(x=>document.querySelector('#result').innerText=JSON.stringify(x,null,2))</script>
</body></html>"""
