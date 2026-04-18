from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.knowledge_models import KbCaseStudy, KbPricing, KbService, KbSnippet
from app.db.models import utcnow
from app.db.session import async_session_maker
from app.schemas.knowledge import (
    KbCaseStudyImportRow,
    KbPricingImportRow,
    KbServiceImportRow,
    KbSnippetImportRow,
    KnowledgeImportPayload,
    KnowledgeImportResponse,
)

router = APIRouter(tags=["knowledge"])


async def _upsert_service(session: AsyncSession, row: KbServiceImportRow) -> None:
    now = utcnow()
    v: dict[str, Any] = {
        "id": uuid.uuid4(),
        "slug": row.slug.strip(),
        "title": row.title.strip(),
        "summary": row.summary.strip(),
        "industries": row.industries,
        "deliverables": list(row.deliverables),
        "keywords": row.keywords,
        "is_active": row.is_active,
        "created_at": now,
        "updated_at": now,
    }
    ins = pg_insert(KbService).values(**v)
    ins = ins.on_conflict_do_update(
        index_elements=[KbService.slug],
        set_={
            "title": ins.excluded.title,
            "summary": ins.excluded.summary,
            "industries": ins.excluded.industries,
            "deliverables": ins.excluded.deliverables,
            "keywords": ins.excluded.keywords,
            "is_active": ins.excluded.is_active,
            "updated_at": now,
        },
    )
    await session.execute(ins)


async def _upsert_case_study(session: AsyncSession, row: KbCaseStudyImportRow) -> None:
    now = utcnow()
    v: dict[str, Any] = {
        "id": uuid.uuid4(),
        "slug": row.slug.strip(),
        "title": row.title.strip(),
        "industry": (row.industry.strip() or None) if row.industry else None,
        "client_problem": row.client_problem.strip(),
        "solution": row.solution.strip(),
        "outcomes": list(row.outcomes),
        "keywords": row.keywords,
        "is_active": row.is_active,
        "created_at": now,
        "updated_at": now,
    }
    ins = pg_insert(KbCaseStudy).values(**v)
    ins = ins.on_conflict_do_update(
        index_elements=[KbCaseStudy.slug],
        set_={
            "title": ins.excluded.title,
            "industry": ins.excluded.industry,
            "client_problem": ins.excluded.client_problem,
            "solution": ins.excluded.solution,
            "outcomes": ins.excluded.outcomes,
            "keywords": ins.excluded.keywords,
            "is_active": ins.excluded.is_active,
            "updated_at": now,
        },
    )
    await session.execute(ins)


async def _upsert_pricing(session: AsyncSession, row: KbPricingImportRow) -> None:
    now = utcnow()
    v: dict[str, Any] = {
        "id": uuid.uuid4(),
        "slug": row.slug.strip(),
        "service_type": row.service_type.strip(),
        "pricing_model": row.pricing_model.strip(),
        "range_text": row.range_text.strip(),
        "notes": row.notes.strip() if row.notes else None,
        "keywords": row.keywords,
        "is_active": row.is_active,
        "created_at": now,
        "updated_at": now,
    }
    ins = pg_insert(KbPricing).values(**v)
    ins = ins.on_conflict_do_update(
        index_elements=[KbPricing.slug],
        set_={
            "service_type": ins.excluded.service_type,
            "pricing_model": ins.excluded.pricing_model,
            "range_text": ins.excluded.range_text,
            "notes": ins.excluded.notes,
            "keywords": ins.excluded.keywords,
            "is_active": ins.excluded.is_active,
            "updated_at": now,
        },
    )
    await session.execute(ins)


async def _upsert_snippet(session: AsyncSession, row: KbSnippetImportRow) -> None:
    now = utcnow()
    v: dict[str, Any] = {
        "id": uuid.uuid4(),
        "slug": row.slug.strip(),
        "section": row.section.strip(),
        "proposal_type": row.proposal_type.strip(),
        "title": row.title.strip(),
        "content": row.content.strip(),
        "keywords": row.keywords,
        "is_active": row.is_active,
        "created_at": now,
        "updated_at": now,
    }
    ins = pg_insert(KbSnippet).values(**v)
    ins = ins.on_conflict_do_update(
        index_elements=[KbSnippet.slug],
        set_={
            "section": ins.excluded.section,
            "proposal_type": ins.excluded.proposal_type,
            "title": ins.excluded.title,
            "content": ins.excluded.content,
            "keywords": ins.excluded.keywords,
            "is_active": ins.excluded.is_active,
            "updated_at": now,
        },
    )
    await session.execute(ins)


@router.post("/knowledge/import", response_model=KnowledgeImportResponse)
async def import_knowledge(payload: KnowledgeImportPayload) -> KnowledgeImportResponse:
    total = (
        len(payload.services)
        + len(payload.case_studies)
        + len(payload.pricing)
        + len(payload.snippets)
    )
    if total == 0:
        raise HTTPException(
            status_code=400,
            detail="Payload must include at least one record across "
            "services, case_studies, pricing, or snippets.",
        )

    applied = {
        "services": len(payload.services),
        "case_studies": len(payload.case_studies),
        "pricing": len(payload.pricing),
        "snippets": len(payload.snippets),
    }

    try:
        async with async_session_maker() as session:
            async with session.begin():
                for row in payload.services:
                    await _upsert_service(session, row)
                for row in payload.case_studies:
                    await _upsert_case_study(session, row)
                for row in payload.pricing:
                    await _upsert_pricing(session, row)
                for row in payload.snippets:
                    await _upsert_snippet(session, row)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Database import failed: {exc}",
        ) from exc

    return KnowledgeImportResponse(applied=applied)
