from typing import Any, TypedDict


class ProposalGraphState(TypedDict, total=False):
    """Shared LangGraph state passed between agent nodes."""

    client_name: str
    website: str
    budget_input: str
    timeline_input: str
    raw_requirements: str

    normalized_brief: str
    requirements: dict[str, Any]
    retrieval_context: str
    proposal: dict[str, Any]
    review: dict[str, Any]
