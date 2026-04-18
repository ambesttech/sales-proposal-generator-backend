from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Proposal, ProposalStatus
from app.db.session import async_session_maker
from app.graph.pipeline import PROPOSAL_GENERATION_ORDER, PROPOSAL_GENERATION_STEPS
from app.schemas.api import (
    AgentReviewDTO,
    GenerateProposalRequest,
    GenerateProposalResponse,
    ProposalDetailDTO,
    ProposalDocumentDTO,
    ProposalListItemDTO,
    ProposalSectionDTO,
)

router = APIRouter(tags=["proposals"])


def _raw_client_name(raw_input: dict | None) -> str:
    if not raw_input:
        return ""
    v = raw_input.get("clientName")
    if isinstance(v, str) and v.strip():
        return v.strip()
    v2 = raw_input.get("client_name")
    if isinstance(v2, str):
        return v2.strip()
    return ""


def _result_proposal_dict(result: dict | None) -> dict:
    if not result or not isinstance(result, dict):
        return {}
    prop = result.get("proposal")
    return prop if isinstance(prop, dict) else {}


def _list_item_from_row(row: Proposal) -> ProposalListItemDTO:
    prop = _result_proposal_dict(row.result)
    title = str(prop.get("title") or "").strip()
    if not title:
        if row.status == ProposalStatus.completed:
            title = "Proposal"
        elif row.status == ProposalStatus.processing:
            title = "In progress…"
        elif row.status == ProposalStatus.failed:
            title = "Failed"
        else:
            title = row.status
    return ProposalListItemDTO(
        id=row.id,
        status=row.status,
        title=title,
        client_name=_raw_client_name(row.raw_input if isinstance(row.raw_input, dict) else None),
        updated_at=row.updated_at,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_for_db(obj: object) -> object:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize_for_db(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_for_db(v) for v in obj]
    return obj


def _proposal_graph_input(body: GenerateProposalRequest) -> dict[str, object]:
    return {
        "client_name": body.client_name.strip(),
        "website": body.website.strip(),
        "budget_input": body.budget.strip(),
        "timeline_input": body.timeline.strip(),
        "raw_requirements": body.requirements,
    }


def _ndjson_line(payload: dict) -> bytes:
    return (json.dumps(payload, default=str) + "\n").encode("utf-8")


async def _insert_processing_proposal(
    session: AsyncSession,
    *,
    proposal_id: UUID,
    user_id: str,
    thread_id: str,
    raw_input: dict,
) -> None:
    row = Proposal(
        id=proposal_id,
        user_id=user_id,
        status=ProposalStatus.processing,
        raw_input=raw_input,
        thread_id=thread_id,
        result=None,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    session.add(row)
    await session.commit()


async def _finalize_proposal(
    session: AsyncSession,
    *,
    proposal_id: UUID,
    status: str,
    result: dict | None,
) -> None:
    values: dict = {
        "status": status,
        "updated_at": _utcnow(),
    }
    if result is not None:
        values["result"] = _serialize_for_db(result)  # type: ignore[assignment]
    await session.execute(
        update(Proposal).where(Proposal.id == proposal_id).values(**values),
    )
    await session.commit()


def _build_generate_response(
    out: dict[str, object],
    proposal_id: UUID,
) -> tuple[GenerateProposalResponse | None, str | None]:
    """Returns (response, error_detail). On error, response is None."""
    proposal = out.get("proposal") or {}
    sections_raw = proposal.get("sections") or []
    if not isinstance(sections_raw, list) or not sections_raw:
        return None, "Proposal generation returned no sections."

    try:
        sections = [ProposalSectionDTO(**s) for s in sections_raw]
        proposal_dto = ProposalDocumentDTO(
            title=str(proposal.get("title") or "Proposal"),
            sections=sections,
            generated_at=str(proposal.get("generatedAt") or ""),
        )
    except Exception as exc:
        return None, f"Invalid proposal shape from writer: {exc}"

    review_raw = out.get("review") or {}
    try:
        review_dto = AgentReviewDTO.model_validate(review_raw)
    except Exception:
        review_dto = AgentReviewDTO(
            completeness_notes=["Review agent returned an unexpected shape."],
            overall_verdict="Unable to parse structured review output.",
        )

    return (
        GenerateProposalResponse(
            run_id=proposal_id,
            proposal=proposal_dto,
            review=review_dto,
            normalized_brief=str(out.get("normalized_brief", "")),
            requirements=out.get("requirements") or {},
            retrieval_context=str(out.get("retrieval_context", "")),
        ),
        None,
    )


@router.get("/proposals", response_model=list[ProposalListItemDTO])
async def list_proposals(
    user_id: str = Query("", alias="userId"),
    limit: int = Query(100, ge=1, le=200),
) -> list[ProposalListItemDTO]:
    async with async_session_maker() as session:
        stmt = (
            select(Proposal)
            .where(Proposal.user_id == user_id.strip())
            .order_by(Proposal.updated_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    return [_list_item_from_row(r) for r in rows]


@router.get("/proposals/{proposal_id}", response_model=ProposalDetailDTO)
async def get_proposal(
    proposal_id: UUID,
    user_id: str = Query("", alias="userId"),
) -> ProposalDetailDTO:
    async with async_session_maker() as session:
        row = await session.get(Proposal, proposal_id)
    if row is None or row.user_id != user_id.strip():
        raise HTTPException(status_code=404, detail="Proposal not found.")

    raw = row.raw_input if isinstance(row.raw_input, dict) else {}
    client_name = _raw_client_name(raw)
    prop_dict = _result_proposal_dict(row.result)
    title = str(prop_dict.get("title") or "").strip() or "Proposal"
    proposal_dto: ProposalDocumentDTO | None = None
    if row.status == ProposalStatus.completed and prop_dict:
        sections_raw = prop_dict.get("sections") or []
        if isinstance(sections_raw, list) and sections_raw:
            try:
                sections = [ProposalSectionDTO(**s) for s in sections_raw]
                proposal_dto = ProposalDocumentDTO(
                    title=str(prop_dict.get("title") or "Proposal"),
                    sections=sections,
                    generated_at=str(prop_dict.get("generatedAt") or ""),
                )
            except Exception:
                proposal_dto = None

    return ProposalDetailDTO(
        id=row.id,
        status=row.status,
        client_name=client_name,
        title=title,
        proposal=proposal_dto,
        updated_at=row.updated_at,
    )


@router.delete("/proposals/{proposal_id}", status_code=204)
async def delete_proposal(
    proposal_id: UUID,
    user_id: str = Query("", alias="userId"),
) -> Response:
    uid = user_id.strip()
    async with async_session_maker() as session:
        result = await session.execute(
            delete(Proposal).where(
                Proposal.id == proposal_id,
                Proposal.user_id == uid,
            ),
        )
        await session.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Proposal not found.")
    return Response(status_code=204)


@router.post("/proposals/generate", response_model=GenerateProposalResponse)
async def generate_proposal(
    body: GenerateProposalRequest,
    request: Request,
) -> GenerateProposalResponse:
    if not settings.groq_api_key.strip():
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured on the API server.",
        )

    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent graph is not initialized.")

    proposal_id = uuid4()
    thread_id = str(uuid4())
    raw_input = body.model_dump(mode="json", by_alias=True)

    async with async_session_maker() as session:
        await _insert_processing_proposal(
            session,
            proposal_id=proposal_id,
            user_id=body.user_id.strip(),
            thread_id=thread_id,
            raw_input=raw_input,
        )

    initial = _proposal_graph_input(body)
    langgraph_config = {"configurable": {"thread_id": thread_id}}

    try:
        out = await graph.ainvoke(initial, langgraph_config)
    except HTTPException:
        raise
    except Exception as exc:
        async with async_session_maker() as session:
            await _finalize_proposal(
                session,
                proposal_id=proposal_id,
                status=ProposalStatus.failed,
                result={"error": str(exc)},
            )
        raise HTTPException(
            status_code=502,
            detail=f"Agent pipeline failed: {exc}",
        ) from exc

    response, err = _build_generate_response(out, proposal_id)
    if response is None or err:
        detail = err or "Proposal generation failed."
        async with async_session_maker() as session:
            await _finalize_proposal(
                session,
                proposal_id=proposal_id,
                status=ProposalStatus.failed,
                result={"error": detail},
            )
        raise HTTPException(status_code=502, detail=detail)

    proposal = out.get("proposal") or {}
    review_dto = response.review
    graph_payload = {
        "normalized_brief": out.get("normalized_brief", ""),
        "requirements": out.get("requirements") or {},
        "retrieval_context": out.get("retrieval_context", ""),
        "proposal": proposal,
        "review": review_dto.model_dump(),
    }

    async with async_session_maker() as session:
        await _finalize_proposal(
            session,
            proposal_id=proposal_id,
            status=ProposalStatus.completed,
            result=graph_payload,
        )

    return response


@router.post("/proposals/generate/stream")
async def generate_proposal_stream(
    body: GenerateProposalRequest,
    request: Request,
) -> StreamingResponse:
    if not settings.groq_api_key.strip():
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured on the API server.",
        )

    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent graph is not initialized.")

    proposal_id = uuid4()
    thread_id = str(uuid4())
    raw_input = body.model_dump(mode="json", by_alias=True)

    async with async_session_maker() as session:
        await _insert_processing_proposal(
            session,
            proposal_id=proposal_id,
            user_id=body.user_id.strip(),
            thread_id=thread_id,
            raw_input=raw_input,
        )

    initial = _proposal_graph_input(body)
    langgraph_config = {"configurable": {"thread_id": thread_id}}

    async def ndjson_body() -> AsyncIterator[bytes]:
        yield _ndjson_line(
            {
                "type": "start",
                "runId": str(proposal_id),
                "steps": PROPOSAL_GENERATION_STEPS,
            },
        )
        yield _ndjson_line(
            {"type": "step", "id": PROPOSAL_GENERATION_ORDER[0], "status": "running"},
        )

        accum: dict[str, object] = dict(initial)
        out: dict[str, object] = {}

        try:
            async for chunk in graph.astream(
                initial,
                langgraph_config,
                stream_mode="updates",
            ):
                if not isinstance(chunk, dict):
                    continue
                for node_id, delta in chunk.items():
                    if isinstance(delta, dict):
                        accum.update(delta)
                    try:
                        idx = PROPOSAL_GENERATION_ORDER.index(str(node_id))
                    except ValueError:
                        idx = -1
                    yield _ndjson_line(
                        {"type": "step", "id": str(node_id), "status": "completed"},
                    )
                    if idx >= 0 and idx + 1 < len(PROPOSAL_GENERATION_ORDER):
                        nxt = PROPOSAL_GENERATION_ORDER[idx + 1]
                        yield _ndjson_line(
                            {"type": "step", "id": nxt, "status": "running"},
                        )

            out = accum
        except Exception as exc:
            async with async_session_maker() as session:
                await _finalize_proposal(
                    session,
                    proposal_id=proposal_id,
                    status=ProposalStatus.failed,
                    result={"error": str(exc)},
                )
            yield _ndjson_line({"type": "error", "message": f"Agent pipeline failed: {exc}"})
            return

        response, err = _build_generate_response(out, proposal_id)
        if response is None or err:
            detail = err or "Proposal generation failed."
            async with async_session_maker() as session:
                await _finalize_proposal(
                    session,
                    proposal_id=proposal_id,
                    status=ProposalStatus.failed,
                    result={"error": detail},
                )
            yield _ndjson_line({"type": "error", "message": detail})
            return

        proposal = out.get("proposal") or {}
        review_dto = response.review
        graph_payload = {
            "normalized_brief": out.get("normalized_brief", ""),
            "requirements": out.get("requirements") or {},
            "retrieval_context": out.get("retrieval_context", ""),
            "proposal": proposal,
            "review": review_dto.model_dump(),
        }

        async with async_session_maker() as session:
            await _finalize_proposal(
                session,
                proposal_id=proposal_id,
                status=ProposalStatus.completed,
                result=graph_payload,
            )

        done_payload = response.model_dump(mode="json", by_alias=True)
        done_payload["type"] = "done"
        yield _ndjson_line(done_payload)

    return StreamingResponse(
        ndjson_body(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
