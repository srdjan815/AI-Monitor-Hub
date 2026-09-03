from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from app.modules.catalog.formula_engine import FormulaError
from app.modules.catalog.models import AttributeDefinition
from app.modules.catalog.platform_models import AttributeFormula
from app.modules.catalog.platform_service_support import _PlatformServiceSupport
from app.modules.catalog.schemas.attribute_platform import (
    FormulaCreate,
    FormulaPreview,
    FormulaUpdate,
)


class AttributeFormulaService(_PlatformServiceSupport):
    """Owns formula definitions, graph validation, and safe preview."""

    async def create_formula(self, data: FormulaCreate) -> AttributeFormula:
        target = await self._required(
            AttributeDefinition,
            data.target_attribute_id,
            "Target attribute",
        )
        dependencies = self.formulas.dependencies(data.expression)
        for name in dependencies:
            if await self.repository.definition_by_identity(name) is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown formula attribute: {name}",
                )
        await self._validate_formula_graph(target.api_name, dependencies)
        formula = AttributeFormula(
            target_attribute_id=target.id,
            formula_kind=data.formula_kind,
            expression=data.expression,
            description=data.description,
        )
        self.session.add(formula)
        await self.session.flush()
        return await self._commit(formula)

    async def list_formulas(
        self,
        *,
        kind: str | None,
        active_only: bool,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AttributeFormula]:
        return await self.repository.list_formulas(
            kind=kind,
            active_only=active_only,
            offset=offset,
            limit=limit,
        )

    async def update_formula(
        self,
        formula_id: uuid.UUID,
        data: FormulaUpdate,
    ) -> AttributeFormula:
        formula = await self._required(
            AttributeFormula,
            formula_id,
            "Formula",
        )
        changes = data.model_dump(exclude_unset=True)
        expression = changes.get("expression", formula.expression)
        target = await self._required(
            AttributeDefinition,
            formula.target_attribute_id,
            "Target attribute",
        )
        dependencies = self.formulas.dependencies(expression)
        await self._validate_formula_graph(
            target.api_name,
            dependencies,
            formula.id,
        )
        for key, value in changes.items():
            setattr(formula, key, value)
        formula.version += 1
        await self.session.flush()
        return await self._commit(formula)

    async def _validate_formula_graph(
        self,
        target_name: str,
        dependencies: set[str],
        excluded_id: uuid.UUID | None = None,
    ) -> None:
        rows = await self.session.execute(
            select(AttributeFormula, AttributeDefinition.api_name)
            .join(
                AttributeDefinition,
                AttributeDefinition.id == AttributeFormula.target_attribute_id,
            )
            .where(AttributeFormula.is_active.is_(True))
        )
        graph = {
            name: self.formulas.dependencies(formula.expression)
            for formula, name in rows
            if formula.id != excluded_id
        }
        graph[target_name] = dependencies
        try:
            self.formulas.validate_graph(graph)
        except FormulaError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def preview_formula(
        self,
        formula_id: uuid.UUID,
        data: FormulaPreview,
    ) -> dict[str, Any]:
        formula = await self._required(
            AttributeFormula,
            formula_id,
            "Formula",
        )
        try:
            result = self.formulas.evaluate(formula.expression, data.values)
        except FormulaError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "result": str(result),
            "dependencies": sorted(self.formulas.dependencies(formula.expression)),
        }
