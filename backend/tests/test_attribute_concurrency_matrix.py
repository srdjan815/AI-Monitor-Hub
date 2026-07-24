from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.modules.catalog.attribute_models import (
    AttributeChangeEvent,
    ProductAttributeValue,
    ProductAttributeValueHistory,
)
from app.modules.catalog.attribute_orchestration import AttributeMutationCoordinator
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.enums import AttributeDataType, AttributeScope
from app.modules.catalog.models import (
    AttributeDefinition,
    Category,
    CategoryAttribute,
    Product,
)
from app.modules.catalog.platform_models import (
    AttributeFormula,
    AttributePromptVersion,
    CategoryAttributeTemplate,
)
from app.modules.catalog.platform_service import AttributePlatformService
from app.modules.catalog.schemas.attribute_platform import (
    FormulaCreate,
    FormulaUpdate,
    LockRequest,
    PromptVersionCreate,
    TemplateCreate,
    TemplateItemCreate,
)
from app.modules.catalog.schemas.product_attributes import (
    ApprovalRequest,
    BulkValueWrite,
    ProductAttributeValueWrite,
)


DATABASE_URL = os.getenv(
    "PRODUCT_CONTENT_INTEGRATION_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@db:5432/ai_content_integration",
)


def session_factory() -> tuple:
    engine = create_async_engine(DATABASE_URL, pool_size=10)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def seed(
    session: AsyncSession,
    definition_count: int,
) -> tuple[Product, Category, list[AttributeDefinition]]:
    suffix = uuid.uuid4().hex
    category = Category(
        name=f"Attribute race {suffix}",
        code=f"attribute_race_{suffix}",
    )
    session.add(category)
    await session.flush()
    product = Product(
        category_id=category.id,
        name=f"Attribute race product {suffix}",
        code=f"attribute_race_product_{suffix}",
    )
    definitions = [
        AttributeDefinition(
            name=f"Attribute race {index} {suffix}",
            code=f"attribute_race_{index}_{suffix}",
            slug=f"attribute_race_{index}_{suffix}",
            internal_name=f"attribute_race_{index}_{suffix}",
            api_name=f"attribute_race_{index}_{suffix}",
            scope=AttributeScope.GLOBAL.value,
            storage_kind="ATTRIBUTE_VALUE",
            status="ACTIVE",
            data_type=AttributeDataType.INTEGER.value,
        )
        for index in range(definition_count)
    ]
    session.add_all([product, *definitions])
    await session.commit()
    return product, category, definitions


async def race(
    first: Callable[[], Awaitable[object]],
    second: Callable[[], Awaitable[object]],
) -> tuple[object, object]:
    start = asyncio.Event()

    async def invoke(operation: Callable[[], Awaitable[object]]) -> object:
        await start.wait()
        try:
            return await operation()
        except Exception as exc:
            return exc

    first_task = asyncio.create_task(invoke(first))
    second_task = asyncio.create_task(invoke(second))
    start.set()
    results = await asyncio.gather(first_task, second_task)
    return results[0], results[1]


def assert_one_winner(outcomes: tuple[object, object]) -> None:
    assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, Exception) for outcome in outcomes) == 1


class LoadBarrier:
    def __init__(self) -> None:
        self.arrived = 0
        self.lock = asyncio.Lock()
        self.ready = asyncio.Event()

    async def wait(self) -> None:
        async with self.lock:
            self.arrived += 1
            if self.arrived == 2:
                self.ready.set()
        await self.ready.wait()


async def value_counts(
    session: AsyncSession,
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
) -> tuple[int, int, int]:
    values = int(
        await session.scalar(
            select(func.count())
            .select_from(ProductAttributeValue)
            .where(
                ProductAttributeValue.product_id == product_id,
                ProductAttributeValue.attribute_definition_id == attribute_id,
                ProductAttributeValue.is_active.is_(True),
            )
        )
        or 0
    )
    history = int(
        await session.scalar(
            select(func.count())
            .select_from(ProductAttributeValueHistory)
            .where(
                ProductAttributeValueHistory.product_id == product_id,
                ProductAttributeValueHistory.attribute_definition_id == attribute_id,
            )
        )
        or 0
    )
    events = int(
        await session.scalar(
            select(func.count())
            .select_from(AttributeChangeEvent)
            .where(
                AttributeChangeEvent.product_id == product_id,
                AttributeChangeEvent.event_metadata["attribute_id"].astext
                == str(attribute_id),
            )
        )
        or 0
    )
    return values, history, events


async def gated_single_write(
    sessions: async_sessionmaker[AsyncSession],
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    value: int,
    barrier: LoadBarrier,
) -> object:
    async with sessions() as session:
        service = ProductAttributeService(session)
        original_value = service.repository.value

        async def gated_value(*args, **kwargs):
            result = await original_value(*args, **kwargs)
            await barrier.wait()
            return result

        service.repository.value = gated_value
        return await service.write_value(
            product_id,
            attribute_id,
            ProductAttributeValueWrite(raw_value=value),
        )


async def gated_bulk_write(
    sessions: async_sessionmaker[AsyncSession],
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    barrier: LoadBarrier,
) -> object:
    async with sessions() as session:
        service = ProductAttributeService(session)
        original_value = service.repository.value

        async def gated_value(*args, **kwargs):
            result = await original_value(*args, **kwargs)
            await barrier.wait()
            return result

        service.repository.value = gated_value
        return await service.bulk_write(
            product_id,
            BulkValueWrite(
                items=[{"attribute_id": attribute_id, "raw_value": 2}],
            ),
        )


async def gated_lock(
    sessions: async_sessionmaker[AsyncSession],
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    barrier: LoadBarrier,
) -> object:
    async with sessions() as session:
        service = AttributePlatformService(session)
        original_values = service.repository.values

        async def gated_values(*args, **kwargs):
            result = await original_values(*args, **kwargs)
            await barrier.wait()
            return result

        service.repository.values = gated_values
        return await service.lock_value(
            product_id,
            attribute_id,
            LockRequest(actor="race", reason="concurrency"),
            True,
        )


async def gated_approval(
    sessions: async_sessionmaker[AsyncSession],
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    barrier: LoadBarrier,
) -> object:
    async with sessions() as session:
        service = ProductAttributeService(session)
        original_values = service.repository.values

        async def gated_values(*args, **kwargs):
            result = await original_values(*args, **kwargs)
            await barrier.wait()
            return result

        service.repository.values = gated_values
        return await service.change_approval(
            product_id,
            attribute_id,
            True,
            ApprovalRequest(actor="race"),
        )


@pytest.mark.asyncio
async def test_value_write_bulk_lock_and_approval_races_repeatably() -> None:
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            async with sessions() as session:
                product, _category, definitions = await seed(session, 4)
                product_id = product.id
                definition_ids = [definition.id for definition in definitions]

            create_barrier = LoadBarrier()
            outcomes = await race(
                lambda: gated_single_write(
                    sessions,
                    product_id,
                    definition_ids[0],
                    iteration * 2,
                    create_barrier,
                ),
                lambda: gated_single_write(
                    sessions,
                    product_id,
                    definition_ids[0],
                    iteration * 2 + 1,
                    create_barrier,
                ),
            )
            assert_one_winner(outcomes)
            async with sessions() as session:
                assert await value_counts(
                    session,
                    product_id,
                    definition_ids[0],
                ) == (1, 1, 1)

                for attribute_id in definition_ids[1:]:
                    await ProductAttributeService(session).write_value(
                        product_id,
                        attribute_id,
                        ProductAttributeValueWrite(raw_value=1),
                    )

            bulk_barrier = LoadBarrier()
            outcomes = await race(
                lambda: gated_bulk_write(
                    sessions,
                    product_id,
                    definition_ids[1],
                    bulk_barrier,
                ),
                lambda: gated_single_write(
                    sessions,
                    product_id,
                    definition_ids[1],
                    3,
                    bulk_barrier,
                ),
            )
            assert_one_winner(outcomes)

            lock_barrier = LoadBarrier()
            lock_outcomes = await race(
                lambda: gated_single_write(
                    sessions,
                    product_id,
                    definition_ids[2],
                    4,
                    lock_barrier,
                ),
                lambda: gated_lock(
                    sessions,
                    product_id,
                    definition_ids[2],
                    lock_barrier,
                ),
            )
            assert_one_winner(lock_outcomes)

            approval_barrier = LoadBarrier()
            approval_outcomes = await race(
                lambda: gated_single_write(
                    sessions,
                    product_id,
                    definition_ids[3],
                    5,
                    approval_barrier,
                ),
                lambda: gated_approval(
                    sessions,
                    product_id,
                    definition_ids[3],
                    approval_barrier,
                ),
            )
            assert_one_winner(approval_outcomes)

            async with sessions() as session:
                expected_counts = (
                    (1, 1, 1),
                    (1, 2, 2),
                    (
                        1,
                        2,
                        2 if not isinstance(lock_outcomes[0], Exception) else 1,
                    ),
                    (
                        1,
                        2,
                        (2 if not isinstance(approval_outcomes[0], Exception) else 1),
                    ),
                )
                for attribute_id, expected in zip(
                    definition_ids,
                    expected_counts,
                    strict=True,
                ):
                    actual = await value_counts(
                        session,
                        product_id,
                        attribute_id,
                    )
                    assert actual == expected
                assert await session.scalar(select(1)) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recalculation_write_formula_update_and_derived_value_races() -> None:
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            async with sessions() as session:
                product, _category, definitions = await seed(session, 2)
                source, derived = definitions
                coordinator = AttributeMutationCoordinator(session)
                await coordinator.write_value(
                    product.id,
                    source.id,
                    ProductAttributeValueWrite(raw_value=2),
                )
                formula = await AttributePlatformService(session).create_formula(
                    FormulaCreate(
                        target_attribute_id=derived.id,
                        formula_kind="DERIVED",
                        expression=f"{source.api_name} + 1",
                    )
                )
                await AttributePlatformService(session).recalculate_product(product.id)
                product_id = product.id
                source_id = source.id
                derived_id = derived.id
                formula_id = formula.id

            derived_barrier = LoadBarrier()

            async def manual_write() -> object:
                async with sessions() as session:
                    service = ProductAttributeService(session)
                    original_value = service.repository.value

                    async def gated_value(*args, **kwargs):
                        result = await original_value(*args, **kwargs)
                        await derived_barrier.wait()
                        return result

                    service.repository.value = gated_value
                    return await service.write_value(
                        product_id,
                        derived_id,
                        ProductAttributeValueWrite(raw_value=99),
                    )

            async def recalculate() -> object:
                async with sessions() as session:
                    service = AttributePlatformService(session)
                    original_value = service.attributes.repository.value

                    async def gated_value(*args, **kwargs):
                        result = await original_value(*args, **kwargs)
                        await derived_barrier.wait()
                        return result

                    service.attributes.repository.value = gated_value
                    return await service.recalculate_product(
                        product_id,
                        changed_attribute_id=source_id,
                    )

            outcomes = await race(manual_write, recalculate)
            assert_one_winner(outcomes)

            async def update_formula() -> object:
                async with sessions() as session:
                    return await AttributePlatformService(session).update_formula(
                        formula_id,
                        FormulaUpdate(
                            expression=f"{source.api_name} + 2",
                        ),
                    )

            outcomes = await race(update_formula, recalculate)
            assert all(not isinstance(outcome, Exception) for outcome in outcomes)
            async with sessions() as session:
                formula_row = await session.get(AttributeFormula, formula_id)
                assert formula_row is not None
                assert formula_row.version == 2
                value = await session.scalar(
                    select(ProductAttributeValue).where(
                        ProductAttributeValue.product_id == product_id,
                        ProductAttributeValue.attribute_definition_id == derived_id,
                        ProductAttributeValue.is_active.is_(True),
                    )
                )
                assert value is not None
                assert int(value.numeric_value) in {3, 4, 99}
                assert value.version >= 2
                assert await session.scalar(select(1)) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_prompt_activation_and_template_assignment_races() -> None:
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            async with sessions() as session:
                _product, category, definitions = await seed(session, 1)
                definition = definitions[0]
                platform = AttributePlatformService(session)
                first_prompt = await platform.create_prompt(
                    definition.id,
                    PromptVersionCreate(
                        extraction_prompt=f"first-{iteration}",
                        activate=False,
                    ),
                )
                second_prompt = await platform.create_prompt(
                    definition.id,
                    PromptVersionCreate(
                        extraction_prompt=f"second-{iteration}",
                        activate=False,
                    ),
                )
                template = await platform.create_template(
                    TemplateCreate(
                        name=f"Race template {iteration} {uuid.uuid4().hex}",
                    )
                )
                await platform.add_template_item(
                    template.id,
                    TemplateItemCreate(
                        attribute_definition_id=definition.id,
                        sort_order=1,
                    ),
                )
                prompt_ids = (first_prompt.id, second_prompt.id)
                definition_id = definition.id
                template_id = template.id
                category_id = category.id

            async def activate(prompt_id: uuid.UUID) -> object:
                async with sessions() as session:
                    return await AttributePlatformService(session).activate_prompt(
                        prompt_id
                    )

            outcomes = await race(
                lambda: activate(prompt_ids[0]),
                lambda: activate(prompt_ids[1]),
            )
            assert all(not isinstance(outcome, Exception) for outcome in outcomes)
            async with sessions() as session:
                prompts = list(
                    (
                        await session.scalars(
                            select(AttributePromptVersion).where(
                                AttributePromptVersion.attribute_definition_id
                                == definition_id
                            )
                        )
                    ).all()
                )
                assert len(prompts) == 2
                assert sum(prompt.is_active for prompt in prompts) == 1
                active = next(prompt for prompt in prompts if prompt.is_active)
                definition = await session.get(AttributeDefinition, definition_id)
                assert definition is not None
                assert definition.extraction_prompt == active.extraction_prompt

            async def assign_template() -> object:
                async with sessions() as session:
                    return await AttributePlatformService(session).assign_template(
                        template_id,
                        category_id,
                    )

            outcomes = await race(assign_template, assign_template)
            assert_one_winner(outcomes)
            async with sessions() as session:
                assignments = await session.scalar(
                    select(func.count())
                    .select_from(CategoryAttribute)
                    .where(
                        CategoryAttribute.category_id == category_id,
                        CategoryAttribute.attribute_id == definition_id,
                    )
                )
                associations = await session.scalar(
                    select(func.count())
                    .select_from(CategoryAttributeTemplate)
                    .where(
                        CategoryAttributeTemplate.category_id == category_id,
                        CategoryAttributeTemplate.template_id == template_id,
                    )
                )
                assert assignments == 1
                assert associations == 1
                assert await session.scalar(select(1)) == 1
    finally:
        await engine.dispose()
