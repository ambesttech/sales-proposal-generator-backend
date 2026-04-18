from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    intake_agent,
    kb_retrieval_agent,
    proposal_writer_agent,
    requirements_agent,
    review_agent,
)
from app.graph.state import ProposalGraphState


def build_proposal_graph():
    # Node names must not match ProposalGraphState keys (LangGraph reserves state keys).
    g = StateGraph(ProposalGraphState)
    g.add_node("intake", intake_agent)
    g.add_node("extract_requirements", requirements_agent)
    g.add_node("kb_retrieval", kb_retrieval_agent)
    g.add_node("proposal_writer", proposal_writer_agent)
    g.add_node("quality_review", review_agent)

    g.add_edge(START, "intake")
    g.add_edge("intake", "extract_requirements")
    g.add_edge("extract_requirements", "kb_retrieval")
    g.add_edge("kb_retrieval", "proposal_writer")
    g.add_edge("proposal_writer", "quality_review")
    g.add_edge("quality_review", END)

    return g.compile()
