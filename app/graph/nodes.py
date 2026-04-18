from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.graph.state import ProposalGraphState
from app.knowledge.db_retrieval import retrieve_kb_chunks
from app.knowledge.store import KnowledgeChunk
from app.llm.factory import get_chat_model, get_chat_model_json
from app.llm.json_utils import llm_content_to_str, parse_and_validate
from app.schemas.agents import (
    ProposalDraftOut,
    RequirementsOutput,
    RetrievalKeywordsJson,
    ReviewOutput,
)

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "for",
    "of",
    "to",
    "in",
    "on",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "it",
    "we",
    "you",
    "our",
    "their",
    "with",
    "from",
    "that",
    "this",
    "will",
    "can",
    "should",
    "into",
    "about",
}


def _heuristic_keywords(state: ProposalGraphState) -> list[str]:
    req = state.get("requirements") or {}
    chunks: list[str] = []
    for key in ("goals", "pain_points", "constraints"):
        for line in req.get(key) or []:
            if isinstance(line, str):
                chunks.append(line)
    text = " ".join(chunks).lower()
    words = re.split(r"[^\w]+", text)
    out: list[str] = []
    for w in words:
        w = w.strip()
        if len(w) < 3 or w in STOPWORDS:
            continue
        if w not in out:
            out.append(w)
    return out[:18]


def _format_kb_hits(items: list[KnowledgeChunk]) -> str:
    blocks: list[str] = []
    for it in items:
        kw = ", ".join(it.keywords)
        blocks.append(
            f"[{it.category}] {it.title}\nKeywords: {kw}\n{it.body.strip()}",
        )
    return "\n\n---\n\n".join(blocks)


def _clip(s: str, max_chars: int) -> str:
    if max_chars <= 0 or len(s) <= max_chars:
        return s
    return s[: max_chars - 20].rstrip() + "\n…[truncated]"


async def intake_agent(state: ProposalGraphState) -> dict[str, Any]:
    llm = get_chat_model()
    raw = state.get("raw_requirements", "") or "(empty)"
    raw = _clip(raw, settings.groq_clip_raw_requirements_chars)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the Intake Agent. Normalize messy client notes into a clean internal brief: "
                "short executive overview (2–4 sentences) then bullet facts (client context, stated needs, "
                "links, numbers, dates). Preserve meaning; do not invent facts. Be concise.",
            ),
            (
                "human",
                "Client name: {client_name}\nWebsite: {website}\nBudget (as provided): {budget}\n"
                "Timeline (as provided): {timeline}\nRaw requirements / notes:\n{requirements}",
            ),
        ],
    )
    chain = prompt | llm
    msg = await chain.ainvoke(
        {
            "client_name": state.get("client_name", "") or "(not provided)",
            "website": state.get("website", "") or "(not provided)",
            "budget": state.get("budget_input", "") or "(not provided)",
            "timeline": state.get("timeline_input", "") or "(not provided)",
            "requirements": raw,
        },
    )
    return {"normalized_brief": (msg.content or "").strip()}


async def requirements_agent(state: ProposalGraphState) -> dict[str, Any]:
    llm = get_chat_model_json(max_tokens=settings.groq_max_tokens_requirements)
    brief = _clip(state.get("normalized_brief", ""), settings.groq_clip_brief_chars)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the Requirements Agent. Extract structured engagement requirements from the brief. "
                "Use concise bullet strings in the arrays. If budget or timeline are unknown, use null.\n\n"
                "Reply with ONLY a JSON object (no markdown) with keys exactly: "
                "goals, pain_points, constraints (each an array of strings), budget (string or null), "
                "timeline (string or null).",
            ),
            ("human", "{brief}"),
        ],
    )
    chain = prompt | llm
    msg = await chain.ainvoke({"brief": brief})
    result = parse_and_validate(llm_content_to_str(msg.content), RequirementsOutput)
    return {"requirements": result.model_dump()}


async def kb_retrieval_agent(state: ProposalGraphState) -> dict[str, Any]:
    """Retrieval agent: LLM suggests keywords, then search in-memory knowledge base."""
    brief = _clip(state.get("normalized_brief", ""), settings.groq_clip_retrieval_brief_chars)
    req_str = json.dumps(state.get("requirements") or {}, indent=2)
    req_str = _clip(req_str, settings.groq_clip_retrieval_req_chars)

    llm = get_chat_model_json(max_tokens=settings.groq_max_tokens_retrieval)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the Retrieval Agent. Propose up to 12 short search keywords or phrases "
                "to find relevant internal content: services, case studies, reusable proposal language, "
                "and pricing references.\n\n"
                "Reply with ONLY a JSON object (no markdown) with key exactly: keywords (array of strings).",
            ),
            (
                "human",
                "Normalized brief:\n{brief}\n\nStructured requirements JSON:\n{req}\n",
            ),
        ],
    )
    chain = prompt | llm
    llm_keywords: list[str] = []
    try:
        msg = await chain.ainvoke({"brief": brief, "req": req_str})
        parsed = parse_and_validate(
            llm_content_to_str(msg.content),
            RetrievalKeywordsJson,
        )
        llm_keywords = [
            w.strip()
            for w in parsed.keywords
            if isinstance(w, str) and w.strip()
        ][:12]
    except Exception:
        llm_keywords = []

    merged: list[str] = []
    for w in llm_keywords + _heuristic_keywords(state):
        w = w.strip()
        if w and w.lower() not in {m.lower() for m in merged}:
            merged.append(w)

    hits = await retrieve_kb_chunks(merged)
    ctx = _format_kb_hits(hits)
    ctx = _clip(ctx, settings.groq_clip_retrieval_context_chars)
    return {"retrieval_context": ctx}


async def proposal_writer_agent(state: ProposalGraphState) -> dict[str, Any]:
    llm = get_chat_model_json(max_tokens=settings.groq_max_tokens_writer)
    brief = _clip(state.get("normalized_brief", ""), settings.groq_clip_brief_chars)
    req_str = json.dumps(state.get("requirements") or {}, indent=2)
    req_str = _clip(req_str, settings.groq_clip_requirements_json_chars)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the Proposal Writer Agent. Draft a professional sales proposal as structured sections. "
                "Use INTERNAL KNOWLEDGE BASE excerpts where they genuinely strengthen scope, proof points, "
                "or commercial framing; do not invent facts beyond that material or the client brief. "
                "Do not fabricate metrics or legal promises. "
                "Mirror client language from requirements. Include headings: Executive summary; "
                "Understanding & objectives; Proposed approach & scope; Timeline & milestones; "
                "Investment & commercial terms; Assumptions & dependencies; Next steps. "
                "Keep each body section concise (2–4 short paragraphs or tight bullets) to stay within output limits.\n\n"
                "Reply with ONLY a JSON object (no markdown). Keys exactly: "
                "title (string), sections (array of objects with heading and body strings). "
                "Escape double quotes inside strings as \\\". Use \\n for newlines in body strings.",
            ),
            (
                "human",
                "Client: {client_name}\nWebsite: {website}\nBudget field: {budget}\nTimeline field: {timeline}\n\n"
                "Normalized brief:\n{brief}\n\nStructured requirements:\n{req}\n\n"
                "Knowledge base excerpts (internal):\n{kb}\n",
            ),
        ],
    )
    chain = prompt | llm
    kb = _clip(
        state.get("retrieval_context", "") or "(no knowledge base excerpts)",
        settings.groq_clip_retrieval_context_chars,
    )
    msg = await chain.ainvoke(
        {
            "client_name": state.get("client_name", "") or "Client",
            "website": state.get("website", "") or "N/A",
            "budget": state.get("budget_input", "") or "TBD",
            "timeline": state.get("timeline_input", "") or "TBD",
            "brief": brief,
            "req": req_str,
            "kb": kb,
        },
    )
    draft = parse_and_validate(llm_content_to_str(msg.content), ProposalDraftOut)
    generated_at = datetime.now(timezone.utc).isoformat()
    proposal = {
        "title": draft.title,
        "sections": [s.model_dump() for s in draft.sections],
        "generatedAt": generated_at,
    }
    return {"proposal": proposal}


async def review_agent(state: ProposalGraphState) -> dict[str, Any]:
    llm = get_chat_model_json(max_tokens=settings.groq_max_tokens_review)
    req_str = json.dumps(state.get("requirements") or {}, indent=2)
    req_str = _clip(req_str, settings.groq_clip_requirements_json_chars)
    proposal_json = json.dumps(state.get("proposal") or {}, indent=2)
    proposal_json = _clip(proposal_json, settings.groq_clip_proposal_review_chars)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the Review Agent. Evaluate the proposal for completeness vs the stated requirements, "
                "internal consistency, missing standard sections, risky or unsubstantiated claims, and weak writing. "
                "When knowledge base excerpts are provided, flag claims that are not supported by them or the requirements. "
                "Be brief and actionable. Set ready_to_send true only if issues are minor.\n\n"
                "Reply with ONLY a JSON object (no markdown) with keys exactly: "
                "completeness_notes, consistency_notes, missing_sections, risky_claims, weak_writing, "
                "suggested_fixes (each an array of strings), ready_to_send (boolean), overall_verdict (string).",
            ),
            (
                "human",
                "Structured requirements:\n{req}\n\nProposal JSON:\n{proposal}\n\n"
                "Knowledge base excerpts (internal, same as used for drafting):\n{kb}\n",
            ),
        ],
    )
    chain = prompt | llm
    kb_ctx = _clip(
        state.get("retrieval_context", "") or "(none)",
        min(2500, settings.groq_clip_retrieval_context_chars),
    )
    msg = await chain.ainvoke(
        {
            "req": req_str,
            "proposal": proposal_json,
            "kb": kb_ctx,
        },
    )
    review = parse_and_validate(llm_content_to_str(msg.content), ReviewOutput)
    return {"review": review.model_dump()}
