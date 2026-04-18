from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GenerateProposalRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    client_name: str = Field(default="", alias="clientName")
    website: str = ""
    budget: str = ""
    timeline: str = ""
    requirements: str = ""
    user_id: str = Field(default="", alias="userId")


class ProposalSectionDTO(BaseModel):
    heading: str
    body: str


class ProposalDocumentDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    title: str
    sections: list[ProposalSectionDTO]
    generated_at: str = Field(serialization_alias="generatedAt")


class AgentReviewDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    completeness_notes: list[str] = Field(default_factory=list)
    consistency_notes: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    risky_claims: list[str] = Field(default_factory=list)
    weak_writing: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)
    ready_to_send: bool = False
    overall_verdict: str = ""


class GenerateProposalResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    run_id: UUID = Field(serialization_alias="runId", alias="runId")
    proposal: ProposalDocumentDTO
    review: AgentReviewDTO
    normalized_brief: str = Field(
        default="",
        serialization_alias="normalizedBrief",
        alias="normalizedBrief",
    )
    requirements: dict = Field(default_factory=dict)
    retrieval_context: str = Field(
        default="",
        serialization_alias="retrievalContext",
        alias="retrievalContext",
    )


class ProposalListItemDTO(BaseModel):
    """Summary row for proposal history (DB)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: UUID
    status: str
    title: str
    client_name: str = Field(default="", serialization_alias="clientName")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ProposalDetailDTO(BaseModel):
    """Single proposal for read-only UI."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: UUID
    status: str
    client_name: str = Field(default="", serialization_alias="clientName")
    title: str
    proposal: ProposalDocumentDTO | None = None
    updated_at: datetime = Field(serialization_alias="updatedAt")
