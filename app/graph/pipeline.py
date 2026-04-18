"""Ordered LangGraph nodes for proposal generation (used for progress streaming)."""

PROPOSAL_GENERATION_STEPS: list[dict[str, str]] = [
    {
        "id": "intake",
        "title": "Intake agent",
        "detail": "Normalizing notes into an internal brief",
    },
    {
        "id": "extract_requirements",
        "title": "Requirements agent",
        "detail": "Structuring goals, constraints, and commercial context",
    },
    {
        "id": "kb_retrieval",
        "title": "Retrieval agent",
        "detail": "Pulling services, case studies, and reusable content from the knowledge base",
    },
    {
        "id": "proposal_writer",
        "title": "Proposal writer",
        "detail": "Drafting sections using requirements and KB context",
    },
    {
        "id": "quality_review",
        "title": "Review agent",
        "detail": "Completeness, consistency, and risk pass",
    },
]

PROPOSAL_GENERATION_ORDER: tuple[str, ...] = tuple(
    s["id"] for s in PROPOSAL_GENERATION_STEPS
)
