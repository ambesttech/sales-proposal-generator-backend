"""Load knowledge-base rows from Postgres and rank for proposal retrieval."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.knowledge_models import KbCaseStudy, KbPricing, KbService, KbSnippet
from app.db.session import async_session_maker
from app.knowledge.store import KnowledgeChunk, search_chunks

logger = logging.getLogger(__name__)


def _deliverables_text(raw: Any) -> str:
    if isinstance(raw, list):
        lines = [f"- {x}" for x in raw if str(x).strip()]
        return "\n".join(lines) if lines else "(none)"
    if raw is None:
        return "(none)"
    return str(raw)


def _outcomes_text(raw: Any) -> str:
    if isinstance(raw, list):
        parts = [str(x).strip() for x in raw if str(x).strip()]
        return "; ".join(parts) if parts else "(none)"
    if raw is None:
        return "(none)"
    return str(raw)


def _keyword_tuple(row_keywords: list[str] | None, slug: str) -> tuple[str, ...]:
    base = [k for k in (row_keywords or []) if k and str(k).strip()]
    slug_words = [w for w in slug.replace("-", " ").split() if w]
    return tuple(dict.fromkeys([*base, *slug_words]))


def _service_to_chunk(row: KbService) -> KnowledgeChunk:
    body = row.summary.strip()
    body = f"{body}\n\nDeliverables:\n{_deliverables_text(row.deliverables)}"
    if row.industries:
        body += "\n\nIndustries: " + ", ".join(str(i) for i in row.industries if str(i).strip())
    return KnowledgeChunk(
        category="service",
        title=row.title,
        body=body,
        keywords=_keyword_tuple(list(row.keywords or []), row.slug),
    )


def _case_study_to_chunk(row: KbCaseStudy) -> KnowledgeChunk:
    parts = [
        f"Problem:\n{row.client_problem.strip()}",
        f"Solution:\n{row.solution.strip()}",
        f"Outcomes: {_outcomes_text(row.outcomes)}",
    ]
    if row.industry and row.industry.strip():
        parts.insert(0, f"Industry: {row.industry.strip()}")
    return KnowledgeChunk(
        category="case_study",
        title=row.title,
        body="\n\n".join(parts),
        keywords=_keyword_tuple(list(row.keywords or []), row.slug),
    )


def _pricing_to_chunk(row: KbPricing) -> KnowledgeChunk:
    body = (
        f"Service type: {row.service_type.strip()}\n"
        f"Pricing model: {row.pricing_model.strip()}\n"
        f"Range: {row.range_text.strip()}"
    )
    if row.notes and row.notes.strip():
        body += f"\n\nNotes:\n{row.notes.strip()}"
    title = f"{row.service_type.strip()} — {row.range_text.strip()}"[:255]
    return KnowledgeChunk(
        category="pricing",
        title=title,
        body=body,
        keywords=_keyword_tuple(list(row.keywords or []), row.slug),
    )


def _snippet_to_chunk(row: KbSnippet) -> KnowledgeChunk:
    return KnowledgeChunk(
        category=f"snippet:{row.section.strip()}",
        title=row.title,
        body=row.content.strip(),
        keywords=_keyword_tuple(list(row.keywords or []), row.slug),
    )


def _needle_in_chunk(chunk: KnowledgeChunk, needle: str) -> bool:
    n = needle.lower().strip()
    if len(n) < 2:
        return False
    if n in chunk.title.lower() or n in chunk.body.lower():
        return True
    return any(n in k.lower() for k in chunk.keywords)


def _rank_chunks(
    chunks: list[KnowledgeChunk],
    needles: list[str],
    *,
    limit: int,
) -> list[KnowledgeChunk]:
    needles = [n.strip() for n in needles if n and len(n.strip()) >= 2][:22]
    if not needles:
        return chunks[:limit]

    scored: list[tuple[int, KnowledgeChunk]] = []
    for ch in chunks:
        score = sum(1 for nd in needles if _needle_in_chunk(ch, nd))
        if score > 0:
            scored.append((score, ch))
    scored.sort(key=lambda x: -x[0])
    out: list[KnowledgeChunk] = [c for _, c in scored]
    if len(out) >= limit:
        return out[:limit]

    seen = {id(c) for c in out}
    for ch in chunks:
        if len(out) >= limit:
            break
        if id(ch) not in seen:
            out.append(ch)
            seen.add(id(ch))
    return out[:limit]


async def _load_all_active_chunks(session: AsyncSession) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []

    res_s = await session.scalars(select(KbService).where(KbService.is_active.is_(True)))
    for row in res_s:
        chunks.append(_service_to_chunk(row))

    res_c = await session.scalars(select(KbCaseStudy).where(KbCaseStudy.is_active.is_(True)))
    for row in res_c:
        chunks.append(_case_study_to_chunk(row))

    res_p = await session.scalars(select(KbPricing).where(KbPricing.is_active.is_(True)))
    for row in res_p:
        chunks.append(_pricing_to_chunk(row))

    res_n = await session.scalars(select(KbSnippet).where(KbSnippet.is_active.is_(True)))
    for row in res_n:
        chunks.append(_snippet_to_chunk(row))

    return chunks


async def retrieve_kb_chunks(needles: list[str], *, limit: int = 14) -> list[KnowledgeChunk]:
    """
    Prefer Postgres KB tables; fall back to bundled static chunks if DB is empty
    or unreachable.
    """
    try:
        async with async_session_maker() as session:
            db_chunks = await _load_all_active_chunks(session)
    except Exception as exc:
        logger.warning("KB database load failed, using static KB: %s", exc)
        return search_chunks(needles, limit=limit)

    if not db_chunks:
        return search_chunks(needles, limit=limit)

    return _rank_chunks(db_chunks, needles, limit=limit)
