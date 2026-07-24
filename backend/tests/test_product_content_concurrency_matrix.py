from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.modules.catalog.models import Category, Product
from app.modules.product_content.constants import LibraryItemKind
from app.modules.product_content.library_service import LibraryService
from app.modules.product_content.models import (
    ContentLibraryItem,
    ContentScoreHistory,
    ContentTemplate,
    ContentTemplateItem,
    ContentType,
    LandingPage,
    Language,
    ProductContent,
    ProductLibraryReference,
    ProductSEO,
)
from app.modules.product_content.query_services import ScoringService
from app.modules.product_content.reference_service import ReferenceService
from app.modules.product_content.revision_service import RevisionService
from app.modules.product_content.schemas import (
    ContentWrite,
    LandingWrite,
    LibraryWrite,
    ScoringPolicyWrite,
    SEOWrite,
    TemplateItemWrite,
    TemplateUpdate,
    TemplateWrite,
)
from app.modules.product_content.template_service import TemplateService


DATABASE_URL = os.getenv(
    "PRODUCT_CONTENT_INTEGRATION_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@db:5432/ai_content_integration",
)


def session_factory() -> tuple:
    engine = create_async_engine(DATABASE_URL, pool_size=10)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def seed(session: AsyncSession) -> tuple[Product, Language, ContentType]:
    suffix = uuid.uuid4().hex
    category = Category(
        name=f"Content race {suffix}",
        code=f"content_race_{suffix}",
    )
    language = Language(
        code=f"z-{suffix[:12]}",
        name=f"Content race {suffix}",
        native_name=f"Content race {suffix}",
    )
    content_type = ContentType(
        name=f"Content race {suffix}",
        slug=f"content-race-{suffix}",
    )
    session.add_all([category, language, content_type])
    await session.flush()
    product = Product(
        category_id=category.id,
        name=f"Content race {suffix}",
        code=f"content-race-{suffix}",
    )
    session.add(product)
    await session.commit()
    return product, language, content_type


async def run_race(
    first,
    second,
) -> tuple[object, object]:
    start = asyncio.Event()

    async def invoke(operation):
        await start.wait()
        try:
            return await operation()
        except HTTPException as exc:
            return exc

    first_task = asyncio.create_task(invoke(first))
    second_task = asyncio.create_task(invoke(second))
    start.set()
    return await asyncio.gather(first_task, second_task)


def assert_single_conflict(outcomes: tuple[object, object]) -> None:
    assert sum(not isinstance(item, HTTPException) for item in outcomes) == 1
    assert [
        item.status_code for item in outcomes if isinstance(item, HTTPException)
    ] == [409]


@pytest.mark.asyncio
async def test_content_revision_rollback_and_rollback_rollback_races() -> None:
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            async with sessions() as session:
                product, language, content_type = await seed(session)
                created = await RevisionService(session).create_content(
                    product.id,
                    ContentWrite(
                        language_id=language.id,
                        content_type_id=content_type.id,
                        content=f"Original {iteration}",
                    ),
                )
                content_key = created.content_key
                created_id = created.id

            async def revise(label: str) -> object:
                async with sessions() as session:
                    return await RevisionService(session).revise_content(
                        created_id,
                        ContentWrite(
                            language_id=language.id,
                            content_type_id=content_type.id,
                            content=f"Concurrent {label} {iteration}",
                        ),
                    )

            outcomes = await run_race(
                lambda: revise("A"),
                lambda: revise("B"),
            )
            assert_single_conflict(outcomes)
            async with sessions() as session:
                rows = list(
                    (
                        await session.scalars(
                            select(ProductContent).where(
                                ProductContent.content_key == content_key
                            )
                        )
                    ).all()
                )
                assert len(rows) == 2
                assert sum(row.is_current for row in rows) == 1
                current = next(row for row in rows if row.is_current)
                current_id = current.id

            async def revise_current() -> object:
                async with sessions() as session:
                    return await RevisionService(session).revise_content(
                        current_id,
                        ContentWrite(
                            language_id=language.id,
                            content_type_id=content_type.id,
                            content=f"Third revision {iteration}",
                        ),
                    )

            async def rollback_first() -> object:
                async with sessions() as session:
                    return await RevisionService(session).rollback(
                        content_key,
                        1,
                        "race",
                    )

            outcomes = await run_race(revise_current, rollback_first)
            assert_single_conflict(outcomes)
            async with sessions() as session:
                rows = list(
                    (
                        await session.scalars(
                            select(ProductContent).where(
                                ProductContent.content_key == content_key
                            )
                        )
                    ).all()
                )
                assert len(rows) == 3
                assert sum(row.is_current for row in rows) == 1
                current = next(row for row in rows if row.is_current)
                current_id = current.id

            async def rollback_again() -> object:
                async with sessions() as session:
                    return await RevisionService(session).rollback(
                        content_key,
                        1,
                        "race",
                    )

            outcomes = await run_race(rollback_again, rollback_again)
            assert_single_conflict(outcomes)
            async with sessions() as session:
                rows = list(
                    (
                        await session.scalars(
                            select(ProductContent).where(
                                ProductContent.content_key == content_key
                            )
                        )
                    ).all()
                )
                assert len(rows) == 4
                assert sum(row.is_current for row in rows) == 1
                assert next(row for row in rows if row.is_current).id != current_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_landing_revision_and_seo_revision_deactivation_races() -> None:
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            async with sessions() as session:
                product, language, _content_type = await seed(session)
                landing = await ReferenceService(session).create_landing(
                    product.id,
                    LandingWrite(
                        language_id=language.id,
                        title=f"Landing {iteration}",
                        slug=f"landing-{iteration}-{uuid.uuid4().hex}",
                        body="Original landing",
                    ),
                )
                landing_id = landing.id
                landing_key = landing.landing_key

            async def revise_landing(label: str) -> object:
                async with sessions() as session:
                    return await ReferenceService(session).revise_landing(
                        landing_id,
                        LandingWrite(
                            language_id=language.id,
                            title=f"Landing {label} {iteration}",
                            slug=f"landing-{label}-{uuid.uuid4().hex}",
                            body=f"Landing body {label}",
                        ),
                    )

            outcomes = await run_race(
                lambda: revise_landing("A"),
                lambda: revise_landing("B"),
            )
            assert_single_conflict(outcomes)
            async with sessions() as session:
                landing_rows = list(
                    (
                        await session.scalars(
                            select(LandingPage).where(
                                LandingPage.landing_key == landing_key
                            )
                        )
                    ).all()
                )
                assert len(landing_rows) == 2
                assert sum(row.is_current for row in landing_rows) == 1

                seo = await ReferenceService(session).create_seo(
                    product.id,
                    SEOWrite(
                        language_id=language.id,
                        seo_title=f"SEO {iteration}",
                        seo_description="SEO deactivation race description",
                        slug=f"seo-deactivate-{uuid.uuid4().hex}",
                    ),
                )
                seo_id = seo.id
                seo_key = seo.seo_key

            async def revise_seo() -> object:
                async with sessions() as session:
                    return await ReferenceService(session).revise_seo(
                        seo_id,
                        SEOWrite(
                            language_id=language.id,
                            seo_title=f"SEO revised {iteration}",
                            seo_description="SEO revised deactivation description",
                            slug=f"seo-revised-{uuid.uuid4().hex}",
                        ),
                    )

            async def deactivate_seo() -> object:
                async with sessions() as session:
                    return await ReferenceService(session).deactivate_revision(
                        "seo",
                        seo_id,
                    )

            outcomes = await run_race(revise_seo, deactivate_seo)
            assert all(
                not isinstance(item, HTTPException) or item.status_code == 409
                for item in outcomes
            )
            async with sessions() as session:
                seo_rows = list(
                    (
                        await session.scalars(
                            select(ProductSEO).where(ProductSEO.seo_key == seo_key)
                        )
                    ).all()
                )
                assert sum(row.is_current for row in seo_rows) <= 1
                assert len(seo_rows) in {1, 2}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_template_reorder_clone_modification_and_library_deactivation_races() -> (
    None
):
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            async with sessions() as session:
                product, language, _content_type = await seed(session)
                library = await LibraryService(session).create(
                    LibraryWrite(
                        name=f"Race library {iteration} {uuid.uuid4().hex}",
                        item_kind=LibraryItemKind.BLOCK,
                        language_id=language.id,
                        content="Reusable content",
                    )
                )
                template = await TemplateService(session).create(
                    TemplateWrite(
                        name=f"Race template {iteration} {uuid.uuid4().hex}",
                        description="before",
                    )
                )
                item = await TemplateService(session).add_item(
                    template.id,
                    TemplateItemWrite(
                        library_item_id=library.id,
                        sort_order=0,
                    ),
                )
                product_id = product.id
                library_id = library.id
                template_id = template.id
                item_id = item.id

            async def reorder(order: int) -> object:
                async with sessions() as session:
                    return await TemplateService(session).update_item(
                        item_id,
                        TemplateItemWrite(
                            library_item_id=library_id,
                            sort_order=order,
                        ),
                    )

            outcomes = await run_race(
                lambda: reorder(10),
                lambda: reorder(20),
            )
            assert all(not isinstance(item, HTTPException) for item in outcomes)
            async with sessions() as session:
                current_item = await session.get(ContentTemplateItem, item_id)
                assert current_item is not None
                assert current_item.sort_order in {10, 20}

            clone_name = f"Clone race {iteration} {uuid.uuid4().hex}"

            async def clone() -> object:
                async with sessions() as session:
                    return await TemplateService(session).clone(
                        template_id,
                        clone_name,
                    )

            async def modify() -> object:
                async with sessions() as session:
                    return await TemplateService(session).update(
                        template_id,
                        TemplateUpdate(description="after"),
                    )

            outcomes = await run_race(clone, modify)
            assert all(not isinstance(item, HTTPException) for item in outcomes)
            clone_entity = next(
                item
                for item in outcomes
                if isinstance(item, ContentTemplate) and item.id != template_id
            )
            async with sessions() as session:
                source = await session.get(ContentTemplate, template_id)
                assert source is not None
                assert source.description == "after"
                clone_items = await session.scalar(
                    select(func.count())
                    .select_from(ContentTemplateItem)
                    .where(ContentTemplateItem.template_id == clone_entity.id)
                )
                assert clone_items == 1

            async def assign_library() -> object:
                async with sessions() as session:
                    return await LibraryService(session).assign(
                        product_id,
                        library_id,
                        iteration,
                    )

            async def deactivate_library() -> object:
                async with sessions() as session:
                    return await LibraryService(session).deactivate(library_id)

            outcomes = await run_race(assign_library, deactivate_library)
            assert all(
                not isinstance(item, HTTPException) or item.status_code == 409
                for item in outcomes
            )
            async with sessions() as session:
                current_library = await session.get(ContentLibraryItem, library_id)
                assert current_library is not None
                assert current_library.is_active is False
                references = await session.scalar(
                    select(func.count())
                    .select_from(ProductLibraryReference)
                    .where(
                        ProductLibraryReference.product_id == product_id,
                        ProductLibraryReference.library_item_id == library_id,
                    )
                )
                assert references in {0, 1}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_scoring_history_race_records_each_completed_calculation_once() -> None:
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            async with sessions() as session:
                product, _language, _content_type = await seed(session)
                policy = await ScoringService(session).create_policy(
                    ScoringPolicyWrite(
                        name=f"Race policy {iteration} {uuid.uuid4().hex}"
                    )
                )
                product_id = product.id
                policy_id = policy.id

            async def calculate() -> object:
                async with sessions() as session:
                    return await ScoringService(session).weighted_score(
                        product_id,
                        policy_id,
                    )

            outcomes = await run_race(calculate, calculate)
            assert all(not isinstance(item, HTTPException) for item in outcomes)
            async with sessions() as session:
                history_count = await session.scalar(
                    select(func.count())
                    .select_from(ContentScoreHistory)
                    .where(
                        ContentScoreHistory.product_id == product_id,
                        ContentScoreHistory.policy_id == policy_id,
                    )
                )
                assert history_count == 2
    finally:
        await engine.dispose()
