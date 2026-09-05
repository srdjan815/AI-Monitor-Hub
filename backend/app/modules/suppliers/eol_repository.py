from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.eol_models import EolExportBatch, EolExportItem
from app.modules.suppliers.snapshot_models import SupplierSnapshot, SupplierSnapshotItem


class SupplierEolRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sync_snapshot(
        self, snapshot: SupplierSnapshot, items: list[SupplierSnapshotItem]
    ) -> None:
        await self.session.execute(
            text(
                "UPDATE supplier_product_presence SET is_currently_offered=false, updated_at=now() WHERE source_connection_id=:source_id"
            ),
            {"source_id": snapshot.source_connection_id},
        )
        statement = text("""
            INSERT INTO supplier_product_presence (
                id, supplier_id, source_connection_id, product_code,
                product_code_normalized, identity_key, ean, product_name,
                last_seen_at, last_snapshot_id, is_currently_offered, last_data,
                created_at, updated_at
            ) VALUES (
                :id, :supplier_id, :source_id, :product_code,
                :product_code_normalized, :identity_key, :ean, :product_name,
                :last_seen_at, :snapshot_id, true, CAST(:last_data AS jsonb), now(), now()
            )
            ON CONFLICT (source_connection_id, product_code_normalized, identity_key) DO UPDATE SET
                product_code=EXCLUDED.product_code,
                identity_key=EXCLUDED.identity_key,
                ean=EXCLUDED.ean,
                product_name=EXCLUDED.product_name,
                last_seen_at=EXCLUDED.last_seen_at,
                last_snapshot_id=EXCLUDED.last_snapshot_id,
                is_currently_offered=true,
                last_data=EXCLUDED.last_data,
                updated_at=now()
        """)
        import json

        values = []
        seen: set[str] = set()
        for item in items:
            data = item.mapped_data
            code = str(data.get("product_code") or item.source_identifier or "").strip()
            normalized = code.casefold()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ean = str(data.get("ean") or "").strip() or None
            identity = (
                f"ean:{ean}"
                if ean
                else f"supplier:{snapshot.supplier_id}:code:{normalized}"
            )
            values.append(
                {
                    "id": uuid.uuid4(),
                    "supplier_id": snapshot.supplier_id,
                    "source_id": snapshot.source_connection_id,
                    "product_code": code,
                    "product_code_normalized": normalized,
                    "identity_key": identity,
                    "ean": ean,
                    "product_name": str(data.get("name") or "").strip() or None,
                    "last_seen_at": snapshot.finalized_at or snapshot.created_at,
                    "snapshot_id": snapshot.id,
                    "last_data": json.dumps(data, ensure_ascii=False, default=str),
                }
            )
        if values:
            await self.session.execute(statement, values)
            active_identities = sorted({str(value["identity_key"]) for value in values})
            await self.session.execute(
                text("""
                    UPDATE eol_export_items
                    SET status='SKIPPED',
                        target_results=jsonb_build_object(
                            'reason', 'PRODUCT_REAPPEARED',
                            'message', 'Artikal se ponovo pojavio u aktivnoj ponudi.'
                        ),
                        updated_at=now()
                    WHERE status='PENDING'
                      AND identity_key=ANY(CAST(:identity_keys AS text[]))
                """),
                {"identity_keys": active_identities},
            )

    async def list_candidates(
        self,
        *,
        cutoff: datetime,
        supplier_id: uuid.UUID | None,
        search: str | None,
        limit: int,
        offset: int,
        identity_keys: list[str] | None = None,
    ) -> tuple[list[dict[str, object]], int]:
        filters = ["last_seen_at < :cutoff"]
        params: dict[str, object] = {"cutoff": cutoff, "limit": limit, "offset": offset}
        if supplier_id:
            filters.append(":supplier_id = ANY(supplier_ids)")
            params["supplier_id"] = supplier_id
        if search:
            filters.append(
                "(ean ILIKE :search OR product_name ILIKE :search OR product_codes_text ILIKE :search)"
            )
            params["search"] = f"%{search}%"
        if identity_keys is not None:
            filters.append("identity_key = ANY(CAST(:identity_keys AS text[]))")
            params["identity_keys"] = identity_keys
        where = " AND ".join(filters)
        cte = """
            WITH latest_export AS (
                SELECT DISTINCT ON (item.identity_key)
                       item.identity_key, item.status AS item_status,
                       batch.status AS batch_status, batch.batch_code
                FROM eol_export_items item
                JOIN eol_export_batches batch ON batch.id=item.batch_id
                WHERE batch.status <> 'CANCELLED'
                ORDER BY item.identity_key, batch.created_at DESC, batch.id DESC
            ), grouped AS (
                SELECT p.identity_key, max(p.ean) AS ean,
                       (array_agg(p.product_name ORDER BY p.last_seen_at DESC))[1] AS product_name,
                       max(p.last_seen_at) AS last_seen_at,
                       bool_or(p.is_currently_offered) AS currently_offered,
                       array_agg(DISTINCT p.supplier_id) AS supplier_ids,
                       string_agg(DISTINCT p.product_code, ', ') AS product_codes_text,
                       max(latest.item_status) AS export_item_status,
                       max(latest.batch_status) AS export_batch_status,
                       max(latest.batch_code) AS export_batch_code,
                       jsonb_agg(jsonb_build_object(
                           'supplier_id', p.supplier_id, 'supplier_name', s.company_name,
                           'product_code', p.product_code, 'last_seen_at', p.last_seen_at,
                           'is_currently_offered', p.is_currently_offered
                       ) ORDER BY p.last_seen_at DESC) AS suppliers
                FROM supplier_product_presence p
                JOIN suppliers s ON s.id=p.supplier_id
                LEFT JOIN latest_export latest ON latest.identity_key=p.identity_key
                GROUP BY p.identity_key
                HAVING NOT bool_or(p.is_currently_offered)
            )
        """
        rows = (
            (
                await self.session.execute(
                    text(
                        cte
                        + f"SELECT *, count(*) OVER() AS total FROM grouped WHERE {where} ORDER BY last_seen_at, identity_key LIMIT :limit OFFSET :offset"
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows], int(rows[0]["total"]) if rows else 0

    async def batch_by_key(self, key: str) -> EolExportBatch | None:
        result = await self.session.scalar(
            select(EolExportBatch).where(EolExportBatch.idempotency_key == key)
        )
        return cast(EolExportBatch | None, result)

    async def add_batch(
        self, batch: EolExportBatch, items: list[EolExportItem]
    ) -> None:
        self.session.add(batch)
        self.session.add_all(items)


__all__ = ["SupplierEolRepository"]
