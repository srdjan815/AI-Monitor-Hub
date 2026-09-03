from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.product_content.constants import (
    ContentSource,
    WorkflowStatus,
)
from app.modules.product_content.models import ProductContent
from app.modules.product_content.revision_service import RevisionService
from app.modules.product_content.schemas import ContentWrite, WorkflowRequest


def persistence_error() -> IntegrityError:
    return IntegrityError("statement", {}, RuntimeError("forced constraint"))


def revision_service() -> tuple[RevisionService, AsyncMock, AsyncMock]:
    session = AsyncMock()
    service = RevisionService(session)
    repository = AsyncMock()
    service.repository = repository
    return service, session, repository


def content_write(
    language_id: uuid.UUID,
    content_type_id: uuid.UUID,
    *,
    content: str = "Body",
    status: WorkflowStatus = WorkflowStatus.DRAFT,
) -> ContentWrite:
    return ContentWrite(
        language_id=language_id,
        content_type_id=content_type_id,
        title="Title",
        subtitle="Subtitle",
        content=content,
        summary="Summary",
        status=status,
        approval_status=status,
        source_type=ContentSource.MANUAL,
        source_reference="source",
        source_metadata={"key": "value"},
        created_by="author",
        campaign="campaign",
        priority=2,
    )


def content_entity(
    product_id: uuid.UUID,
    language_id: uuid.UUID,
    content_type_id: uuid.UUID,
    *,
    content_key: uuid.UUID | None = None,
    revision: int = 1,
    is_current: bool = True,
    status: str = WorkflowStatus.DRAFT.value,
    body: str = "Body",
) -> ProductContent:
    return ProductContent(
        id=uuid.uuid4(),
        content_key=content_key or uuid.uuid4(),
        product_id=product_id,
        language_id=language_id,
        content_type_id=content_type_id,
        title="Title",
        subtitle="Subtitle",
        content=body,
        summary="Summary",
        status=status,
        approval_status=status,
        source_type=ContentSource.MANUAL.value,
        source_reference="source",
        source_metadata={"key": "value"},
        created_by="author",
        revision=revision,
        is_current=is_current,
        content_hash="0" * 64,
        campaign="campaign",
        priority=2,
    )


@pytest.mark.asyncio
async def test_create_content_sets_duplicate_lineage_and_mutates_atomically() -> None:
    product_id = uuid.uuid4()
    language_id = uuid.uuid4()
    content_type_id = uuid.uuid4()
    service, _, repository = revision_service()
    service.required = AsyncMock()  # type: ignore[method-assign]
    service.mutate_with_event = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda entity, _action, _product_id: entity
    )
    duplicate = content_entity(product_id, language_id, content_type_id)
    repository.duplicate_content.return_value = duplicate
    data = content_write(
        language_id,
        content_type_id,
        content="  Same body  ",
    )

    created = await service.create_content(product_id, data)

    assert created.product_id == product_id
    assert created.duplicate_of_id == duplicate.id
    assert created.content_hash
    assert service.required.await_count == 3
    service.mutate_with_event.assert_awaited_once_with(
        created,
        "CREATED",
        product_id,
    )

    repository.duplicate_content.return_value = None
    created_without_duplicate = await service.create_content(product_id, data)
    assert created_without_duplicate.duplicate_of_id is None


@pytest.mark.asyncio
async def test_revision_guards_success_and_rollback_on_build_failures() -> None:
    product_id = uuid.uuid4()
    language_id = uuid.uuid4()
    content_type_id = uuid.uuid4()
    data = content_write(language_id, content_type_id, content="Revision")

    service, _, _ = revision_service()
    service.required_for_update = AsyncMock(  # type: ignore[method-assign]
        return_value=content_entity(
            product_id,
            language_id,
            content_type_id,
            is_current=False,
        )
    )
    with pytest.raises(HTTPException) as historical:
        await service.revise_content(uuid.uuid4(), data)
    assert historical.value.status_code == 409

    service, session, repository = revision_service()
    current = content_entity(product_id, language_id, content_type_id)
    service.required_for_update = AsyncMock(return_value=current)  # type: ignore[method-assign]
    revised = await service.revise_content(current.id, data)
    assert current.is_current is False
    assert revised.content_key == current.content_key
    assert revised.revision == 2
    assert revised.content == "Revision"
    assert repository.add.await_count == 2
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(revised)

    for error, expected_status in (
        (persistence_error(), 409),
        (RuntimeError("revision failure"), None),
    ):
        service, session, _ = revision_service()
        current = content_entity(product_id, language_id, content_type_id)
        service.required_for_update = AsyncMock(return_value=current)  # type: ignore[method-assign]
        service._build_revision = AsyncMock(side_effect=error)  # type: ignore[method-assign]
        if expected_status is None:
            with pytest.raises(RuntimeError, match="revision failure"):
                await service.revise_content(current.id, data)
        else:
            with pytest.raises(HTTPException) as failure:
                await service.revise_content(current.id, data)
            assert failure.value.status_code == expected_status
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_workflow_rejects_invalid_transitions_and_stamps_approval_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product_id = uuid.uuid4()
    language_id = uuid.uuid4()
    content_type_id = uuid.uuid4()

    service, _, _ = revision_service()
    invalid = content_entity(
        product_id,
        language_id,
        content_type_id,
        status="INVALID",
    )
    service.required_for_update = AsyncMock(return_value=invalid)  # type: ignore[method-assign]
    with pytest.raises(HTTPException) as invalid_status:
        await service.workflow(
            invalid.id,
            WorkflowRequest(status=WorkflowStatus.APPROVED),
        )
    assert invalid_status.value.status_code == 409

    service, _, _ = revision_service()
    draft = content_entity(product_id, language_id, content_type_id)
    service.required_for_update = AsyncMock(return_value=draft)  # type: ignore[method-assign]
    with pytest.raises(HTTPException) as invalid_transition:
        await service.workflow(
            draft.id,
            WorkflowRequest(status=WorkflowStatus.PUBLISHED),
        )
    assert invalid_transition.value.status_code == 409

    monkeypatch.setattr(
        "app.modules.product_content.revision_service.current_actor_id",
        lambda: "principal-actor",
    )
    service, session, _ = revision_service()
    waiting = content_entity(
        product_id,
        language_id,
        content_type_id,
        status=WorkflowStatus.WAITING_REVIEW.value,
    )
    service.required_for_update = AsyncMock(return_value=waiting)  # type: ignore[method-assign]
    approved = await service.workflow(
        waiting.id,
        WorkflowRequest(status=WorkflowStatus.APPROVED, actor="payload-actor"),
    )
    assert approved.status == WorkflowStatus.APPROVED.value
    assert approved.approved_by == "principal-actor"
    assert approved.approved_at is not None
    session.commit.assert_awaited_once()

    monkeypatch.setattr(
        "app.modules.product_content.revision_service.current_actor_id",
        lambda: None,
    )
    service, _, _ = revision_service()
    approved_current = content_entity(
        product_id,
        language_id,
        content_type_id,
        status=WorkflowStatus.APPROVED.value,
    )
    service.required_for_update = AsyncMock(return_value=approved_current)  # type: ignore[method-assign]
    published = await service.workflow(
        approved_current.id,
        WorkflowRequest(status=WorkflowStatus.PUBLISHED, actor="payload-actor"),
    )
    assert published.status == WorkflowStatus.PUBLISHED.value
    assert published.published_at is not None
    assert published.created_by == "payload-actor"


@pytest.mark.asyncio
async def test_workflow_build_failures_rollback_without_partial_revision() -> None:
    product_id = uuid.uuid4()
    language_id = uuid.uuid4()
    content_type_id = uuid.uuid4()
    current = content_entity(
        product_id,
        language_id,
        content_type_id,
        status=WorkflowStatus.WAITING_REVIEW.value,
    )
    request = WorkflowRequest(status=WorkflowStatus.APPROVED)

    for error, expected_status in (
        (persistence_error(), 409),
        (RuntimeError("workflow failure"), None),
    ):
        service, session, _ = revision_service()
        service.required_for_update = AsyncMock(return_value=current)  # type: ignore[method-assign]
        service._build_revision = AsyncMock(side_effect=error)  # type: ignore[method-assign]
        if expected_status is None:
            with pytest.raises(RuntimeError, match="workflow failure"):
                await service.workflow(current.id, request)
        else:
            with pytest.raises(HTTPException) as failure:
                await service.workflow(current.id, request)
            assert failure.value.status_code == expected_status
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_history_rollback_and_diff_cover_not_found_and_success() -> None:
    product_id = uuid.uuid4()
    language_id = uuid.uuid4()
    content_type_id = uuid.uuid4()
    content_key = uuid.uuid4()
    first = content_entity(
        product_id,
        language_id,
        content_type_id,
        content_key=content_key,
        body="before\nline",
    )
    current = content_entity(
        product_id,
        language_id,
        content_type_id,
        content_key=content_key,
        revision=2,
        body="after\nline",
    )
    service, _, repository = revision_service()
    repository.content_history.return_value = [current, first]
    assert await service.history(content_key) == [current, first]

    repository.content_history_page.return_value = ([current], 2)
    assert await service.history_page(
        content_key,
        limit=1,
        after_revision=None,
        snapshot_revision=None,
    ) == ([current], 2)

    repository.content_revision.return_value = None
    repository.current_content.return_value = current
    with pytest.raises(HTTPException) as missing_rollback:
        await service.rollback(content_key, 1, "actor")
    assert missing_rollback.value.status_code == 404

    repository.content_revision.return_value = first
    repository.current_content.return_value = None
    with pytest.raises(HTTPException) as changed_current:
        await service.rollback(content_key, 1, "actor")
    assert changed_current.value.status_code == 409

    repository.content_revision.return_value = first
    repository.current_content.return_value = current
    service.revise_content = AsyncMock(return_value=current)  # type: ignore[method-assign]
    assert await service.rollback(content_key, 1, "rollback-actor") is current
    rollback_payload = service.revise_content.await_args.args[1]
    assert rollback_payload.source_reference == "rollback:1"
    assert rollback_payload.created_by == "rollback-actor"

    repository.content_revision.side_effect = [None, current]
    with pytest.raises(HTTPException) as missing_diff:
        await service.diff(content_key, 1, 2)
    assert missing_diff.value.status_code == 404

    repository.content_revision.side_effect = [first, current]
    difference = await service.diff(content_key, 1, 2)
    assert difference["from_revision"] == 1
    assert difference["to_revision"] == 2
    assert any(line == "-before" for line in difference["diff"])
    assert any(line == "+after" for line in difference["diff"])
