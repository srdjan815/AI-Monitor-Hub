from __future__ import annotations

import asyncio
import os
import uuid
from types import MethodType

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.modules.catalog.models import Category, Product
from app.modules.product_content.models import (
    ContentChangeEvent,
    ContentLibraryItem,
    ContentLibraryRevision,
    ContentScoringPolicy,
    ContentScoreHistory,
    ContentType,
    ContentTypePromptVersion,
    ContentTemplate,
    ContentTemplateCondition,
    ContentTemplateItem,
    Language,
    ProductContent,
    ProductSEO,
)
from app.modules.product_content.schemas import (
    ContentWrite,
    PreviewRequest,
    PromptWrite,
    SEOWrite,
)
from app.modules.product_content.query_services import PreviewService, ScoringService
from app.modules.product_content.services import (
    PromptService,
    ReferenceService,
    RevisionService,
    TemplateService,
)

DATABASE_URL = os.getenv(
    "PRODUCT_CONTENT_INTEGRATION_DATABASE_URL",
    settings.database_url,
)


def factory() -> tuple:
    engine = create_async_engine(DATABASE_URL, pool_size=10)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def seed(session: AsyncSession) -> tuple[Product, Language, ContentType]:
    suffix = uuid.uuid4().hex
    category = Category(name=f"Integration {suffix}", code=f"i_{suffix}")
    language = await session.scalar(select(Language).where(Language.code == "sr"))
    assert language is not None
    content_type = ContentType(
        name=f"Integration {suffix}",
        slug=f"integration-{suffix}",
    )
    session.add_all([category, language, content_type])
    await session.flush()
    product = Product(
        category_id=category.id,
        name=f"Integration {suffix}",
        code=f"integration-{suffix}",
    )
    session.add(product)
    await session.commit()
    return product, language, content_type


@pytest.mark.asyncio
async def test_postgres_catalog_constraints_indexes_timezone_and_sequence() -> None:
    engine, sessions = factory()
    async with sessions() as session:
        indexes = set(
            (
                await session.execute(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname='public' AND indexname LIKE "
                        "'uq_%current%'"
                    )
                )
            ).scalars()
        )
        assert {
            "uq_product_contents_current_key",
            "uq_product_seo_current_key",
            "uq_product_landing_current_key",
            "uq_content_library_current_language",
        } <= indexes
        constraints = set(
            (
                await session.execute(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE connamespace='public'::regnamespace"
                    )
                )
            ).scalars()
        )
        assert any(name.endswith("score_range") for name in constraints)
        assert any(name.endswith("schedule_order") for name in constraints)
        assert (await session.scalar(text("SHOW TIMEZONE"))).upper() in {
            "UTC",
            "ETC/UTC",
        }

        product, _language, _content_type = await seed(session)
        policy = ContentScoringPolicy(name=f"Policy {uuid.uuid4().hex}")
        session.add(policy)
        await session.flush()
        session.add(
            ContentScoreHistory(
                product_id=product.id,
                policy_id=policy.id,
                score_type="CONTENT",
                score=101,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_seo_revision_has_one_current_and_stable_conflict() -> None:
    engine, sessions = factory()
    for iteration in range(10):
        async with sessions() as session:
            product, language, _content_type = await seed(session)
            created = await ReferenceService(session).create_seo(
                product.id,
                SEOWrite(
                    language_id=language.id,
                    seo_title="Concurrent original",
                    seo_description="Concurrent original description",
                    slug=f"concurrent-{uuid.uuid4().hex}",
                ),
            )
            created_id = created.id
            key = created.seo_key
        start = asyncio.Event()

        async def revise(title: str) -> object:
            async with sessions() as session:
                await start.wait()
                try:
                    return await ReferenceService(session).revise_seo(
                        created_id,
                        SEOWrite(
                            language_id=language.id,
                            seo_title=f"{title} {iteration}",
                            seo_description=f"{title} description",
                            slug=f"revision-{uuid.uuid4().hex}",
                        ),
                    )
                except HTTPException as exc:
                    return exc

        first = asyncio.create_task(revise("Concurrent A"))
        second = asyncio.create_task(revise("Concurrent B"))
        start.set()
        outcomes = await asyncio.gather(first, second)
        assert sum(not isinstance(item, HTTPException) for item in outcomes) == 1
        assert [
            item.status_code for item in outcomes if isinstance(item, HTTPException)
        ] == [409]
        async with sessions() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ProductSEO).where(ProductSEO.seo_key == key)
                    )
                ).all()
            )
            assert len(rows) == 2
            assert sum(row.is_current for row in rows) == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_prompt_versions_leave_one_active() -> None:
    engine, sessions = factory()
    for iteration in range(10):
        async with sessions() as session:
            _product, _language, content_type = await seed(session)
            type_id = content_type.id
        start = asyncio.Event()

        async def create_prompt(label: str) -> object:
            async with sessions() as session:
                await start.wait()
                try:
                    return await PromptService(session).create(
                        type_id,
                        PromptWrite(prompt=f"{label}-{iteration}"),
                    )
                except HTTPException as exc:
                    return exc

        first = asyncio.create_task(create_prompt("A"))
        second = asyncio.create_task(create_prompt("B"))
        start.set()
        outcomes = await asyncio.gather(first, second)
        assert all(not isinstance(item, HTTPException) for item in outcomes)
        async with sessions() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ContentTypePromptVersion).where(
                            ContentTypePromptVersion.content_type_id == type_id
                        )
                    )
                ).all()
            )
            assert len(rows) == 2
            assert sorted(row.version for row in rows) == [1, 2]
            assert sum(row.is_active for row in rows) == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_failure_after_revision_before_event_rolls_back_everything() -> None:
    engine, sessions = factory()
    async with sessions() as session:
        product, language, content_type = await seed(session)
        service = RevisionService(session)
        created = await service.create_content(
            product.id,
            ContentWrite(
                language_id=language.id,
                content_type_id=content_type.id,
                content="Original",
            ),
        )
        key = created.content_key
        original_add = service.repository.add

        async def failing_add(repository, entity):
            if isinstance(entity, ContentChangeEvent):
                raise RuntimeError("injected event failure")
            return await original_add(entity)

        service.repository.add = MethodType(failing_add, service.repository)
        with pytest.raises(RuntimeError, match="injected event failure"):
            await service.revise_content(
                created.id,
                ContentWrite(
                    language_id=language.id,
                    content_type_id=content_type.id,
                    content="Must roll back",
                ),
            )

    async with sessions() as verification:
        rows = list(
            (
                await verification.scalars(
                    select(ProductContent).where(ProductContent.content_key == key)
                )
            ).all()
        )
        assert len(rows) == 1
        assert rows[0].is_current is True
        assert rows[0].content == "Original"
    await engine.dispose()


@pytest.mark.asyncio
async def test_representative_preview_and_score_query_counts_are_bounded() -> None:
    engine, sessions = factory()
    async with sessions() as session:
        product, language, _content_type = await seed(session)
        template = ContentTemplate(
            name=f"Performance {uuid.uuid4().hex}",
            slug=f"performance-{uuid.uuid4().hex}",
        )
        session.add(template)
        await session.flush()
        for order in range(20):
            item = ContentLibraryItem(
                name=f"Block {uuid.uuid4().hex}",
                slug=f"block-{uuid.uuid4().hex}",
                item_kind="BLOCK",
            )
            session.add(item)
            await session.flush()
            session.add(
                ContentLibraryRevision(
                    library_item_id=item.id,
                    language_id=language.id,
                    revision=1,
                    content="{{ProductName}}",
                )
            )
            template_item = ContentTemplateItem(
                template_id=template.id,
                library_item_id=item.id,
                sort_order=order,
            )
            session.add(template_item)
            await session.flush()
            session.add(
                ContentTemplateCondition(
                    template_item_id=template_item.id,
                    sort_order=0,
                    boolean_operator="AND",
                    source="ProductName",
                    comparator="EXISTS",
                )
            )
        await session.commit()
        template_id = template.id
        product_id = product.id
        language_id = language.id

    count = 0

    def count_query(*_args) -> None:
        nonlocal count
        count += 1

    event.listen(engine.sync_engine, "before_cursor_execute", count_query)
    async with sessions() as session:
        preview = await PreviewService(session).render(
            product_id,
            template_id,
            PreviewRequest(language_id=language_id),
        )
    preview_queries = count
    count = 0
    async with sessions() as session:
        await ScoringService(session).content_score(product_id)
    score_queries = count
    event.remove(engine.sync_engine, "before_cursor_execute", count_query)

    assert len(preview["blocks"]) == 20
    assert preview_queries <= 6
    assert score_queries <= 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_template_clone_failure_leaves_no_partial_clone() -> None:
    engine, sessions = factory()
    clone_name = f"Injected clone {uuid.uuid4().hex}"
    async with sessions() as session:
        _product, language, _content_type = await seed(session)
        template = ContentTemplate(
            name=f"Source {uuid.uuid4().hex}",
            slug=f"source-{uuid.uuid4().hex}",
        )
        session.add(template)
        await session.flush()
        for order in range(2):
            library = ContentLibraryItem(
                name=f"Clone block {uuid.uuid4().hex}",
                slug=f"clone-block-{uuid.uuid4().hex}",
                item_kind="BLOCK",
            )
            session.add(library)
            await session.flush()
            session.add(
                ContentLibraryRevision(
                    library_item_id=library.id,
                    language_id=language.id,
                    revision=1,
                    content="Clone",
                )
            )
            session.add(
                ContentTemplateItem(
                    template_id=template.id,
                    library_item_id=library.id,
                    sort_order=order,
                )
            )
        await session.commit()
        template_id = template.id

    async with sessions() as session:
        service = TemplateService(session)
        original_add = service.repository.add
        item_count = 0

        async def failing_add(repository, entity):
            nonlocal item_count
            if isinstance(entity, ContentTemplateItem):
                item_count += 1
                if item_count == 2:
                    raise RuntimeError("injected clone failure")
            return await original_add(entity)

        service.repository.add = MethodType(failing_add, service.repository)
        with pytest.raises(RuntimeError, match="injected clone failure"):
            await service.clone(template_id, clone_name)

    async with sessions() as verification:
        assert (
            await verification.scalar(
                select(ContentTemplate).where(ContentTemplate.name == clone_name)
            )
            is None
        )
    await engine.dispose()
