from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import (
    MAX_CURSOR_CHARS,
)
from app.db.session import get_db
from app.modules.catalog.attribute_repository import ProductAttributeRepository
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.models import Product
from app.modules.catalog.schemas.product_attributes import (
    ChangeEventRead,
    ProductExport,
)

router = APIRouter(prefix="/catalog", tags=["product-attributes"])


@router.get("/attribute-changes", response_model=list[ChangeEventRead])
async def attribute_changes(
    cursor: int = Query(
        default=0,
        ge=0,
        le=9_223_372_036_854_775_807,
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    product_id: uuid.UUID | None = None,
    entity_type: str | None = Query(default=None, max_length=80),
    session: AsyncSession = Depends(get_db),
) -> list[Any]:
    return await ProductAttributeRepository(session).changes(
        cursor=cursor,
        limit=limit,
        product_id=product_id,
        entity_type=entity_type,
    )


@router.get(
    "/products/{product_id:uuid}/export",
    response_model=ProductExport,
    deprecated=True,
)
async def product_export(
    product_id: uuid.UUID,
    response: Response,
    limit: int = Query(default=500, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> ProductExport:
    service = ProductAttributeService(session)
    product = await service._required(Product, product_id, "Product")
    chain = await service.repository.list_category_chain(product.category_id)
    page = await service.resolved_page(
        product.category_id,
        product=product,
        include_unset=True,
        scope=None,
        group_id=None,
        family_id=None,
        template_id=None,
        limit=limit,
        cursor=cursor,
    )
    response.headers["X-Total-Count"] = str(page.total)
    response.headers["X-Snapshot-Cursor"] = str(page.snapshot_cursor)
    if page.next_cursor:
        response.headers["X-Next-Cursor"] = page.next_cursor
    return ProductExport(
        product={
            "id": product.id,
            "name": product.name,
            "code": product.code,
            "sku": product.sku,
            "ean": product.ean,
            "mpn": product.mpn,
            "brand": product.brand,
            "manufacturer": product.manufacturer,
        },
        category_path=[
            {"id": category.id, "name": category.name, "code": category.code}
            for category in chain
        ],
        attributes=page.items,
        cursor=page.snapshot_cursor,
    )


@router.get("/attribute-admin", response_class=HTMLResponse, include_in_schema=False)
async def attribute_admin() -> str:
    return """<!doctype html>
<html lang="sr"><head><meta charset="utf-8"><title>Product Attributes</title>
<style>body{font:15px system-ui;margin:2rem;max-width:1200px}nav button{margin:.2rem}
section{border:1px solid #ddd;padding:1rem;margin:1rem 0}input,select,textarea{margin:.2rem}
table{border-collapse:collapse;width:100%}td,th{padding:.4rem;border-bottom:1px solid #ddd}
.muted{color:#666}</style></head><body>
<h1>Product Attribute Administration</h1>
<p class="muted">Uses the canonical Catalog API. Access follows current application security.</p>
<nav><button onclick="loadDashboard()">Dashboard</button>
<button onclick="loadGroups()">Groups</button><button onclick="newGroup()">New group</button>
<button onclick="loadDefinitions()">Definitions</button><button onclick="newDefinition()">New definition</button>
<button onclick="loadCategory()">Category layout</button>
<button onclick="loadProduct()">Product editor</button><button onclick="loadReview()">Review queue</button></nav>
<nav><a href="/api/v1/catalog/attribute-admin/families">Families</a> ·
<a href="/api/v1/catalog/attribute-admin/templates">Templates</a> ·
<a href="/api/v1/catalog/attribute-admin/formulas">Formulas</a> ·
<a href="/api/v1/catalog/attribute-admin/derived">Derived</a> ·
<a href="/api/v1/catalog/attribute-admin/dependencies">Dependencies</a> ·
<a href="/api/v1/catalog/attribute-admin/prompts">Prompts</a> ·
<a href="/api/v1/catalog/attribute-admin/usage">Usage</a> ·
<a href="/api/v1/catalog/attribute-admin/bulk">Bulk editor</a> ·
<a href="/api/v1/catalog/attribute-admin/locked">Locked values</a></nav>
<section id="view">Loading…</section>
<script>
const api='/api/v1/catalog', view=document.querySelector('#view');
async function json(path, options){const r=await fetch(api+path,options);if(!r.ok)throw Error(await r.text());return r.json()}
async function loadDashboard(){const d=await json('/attribute-dashboard');
view.innerHTML='<h2>Dashboard</h2>'+Object.entries(d).map(([k,v])=>`<p><b>${k}</b>: ${v??'not yet calculated'}</p>`).join('')}
async function loadGroups(){const d=await json('/attribute-groups?active_only=false');
view.innerHTML='<h2>Groups</h2><table><tr><th>Order</th><th>Name</th><th>Slug</th><th>Active</th></tr>'+
d.map(x=>`<tr><td>${x.sort_order}</td><td>${x.name}</td><td>${x.slug}</td><td>${x.is_active}</td></tr>`).join('')+'</table>'}
async function newGroup(){const name=prompt('Group name');if(!name)return;await json('/attribute-groups',
{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});loadGroups()}
async function loadDefinitions(){const d=await json('/attribute-definitions?active_only=false');
view.innerHTML='<h2>Definitions</h2><input placeholder="Search" oninput="filterRows(this.value)"><table id="defs"><tr><th>Name</th><th>API</th><th>Type</th><th>Storage</th></tr>'+
d.map(x=>`<tr><td>${x.name}</td><td>${x.api_name}</td><td>${x.data_type}</td><td>${x.storage_kind}</td></tr>`).join('')+'</table>'}
async function newDefinition(){const name=prompt('Attribute name');if(!name)return;const slug=prompt('Stable API name');
await json('/attribute-definitions',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({name,slug,scope:'GLOBAL',storage_kind:'ATTRIBUTE_VALUE',data_type:'TEXT'})});loadDefinitions()}
async function loadCategory(){const id=prompt('Category UUID');if(!id)return;const d=await json(`/categories/${id}/attributes/resolved`);
view.innerHTML='<h2>Resolved category layout</h2>'+d.map(x=>`<p>${x.sort_order}. ${x.definition.name} ${x.inherited_from_category_id?'(assigned/inherited)':'(global)'}</p>`).join('')}
async function loadProduct(){const id=prompt('Product UUID');if(!id)return;const d=await json(`/products/${id}/attributes`);
view.innerHTML='<h2>Product attribute editor</h2>'+d.map(x=>`<p><b>${x.definition.name}</b>: ${x.display_value??'—'} ${x.read_only?'🔒':''}</p>`).join('')}
async function loadReview(){const d=await json('/attribute-dashboard');view.innerHTML=`<h2>Review queue</h2>
<p>Pending ${d.pending_review_values}; invalid ${d.invalid_values}; warnings ${d.warning_values};
low confidence ${d.low_confidence_values}</p><p>Use Product editor and approval APIs for decisions.</p>`}
function filterRows(q){for(const r of document.querySelectorAll('#defs tr'))r.hidden=!r.innerText.toLowerCase().includes(q.toLowerCase())}
loadDashboard();</script></body></html>"""
