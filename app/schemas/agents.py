from pydantic import BaseModel, Field


class RequirementsOutput(BaseModel):
    goals: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    budget: str | None = None
    timeline: str | None = None


class ProposalSectionOut(BaseModel):
    heading: str
    body: str


class ProposalDraftOut(BaseModel):
    title: str
    sections: list[ProposalSectionOut]


class RetrievalKeywordsJson(BaseModel):
    """JSON shape from the Retrieval agent (Groq json_object mode)."""

    keywords: list[str] = Field(default_factory=list)


class ReviewOutput(BaseModel):
    completeness_notes: list[str] = Field(default_factory=list)
    consistency_notes: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    risky_claims: list[str] = Field(default_factory=list)
    weak_writing: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)
    ready_to_send: bool = False
    overall_verdict: str = ""
