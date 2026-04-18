from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class KbServiceImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    summary: str = Field(..., min_length=1)
    industries: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(
        default_factory=list,
        description='JSON array of strings, e.g. ["workflow design", "APIs"]',
    )
    keywords: list[str] = Field(default_factory=list)
    is_active: bool = Field(default=True)


class KbCaseStudyImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=100)
    client_problem: str = Field(..., min_length=1)
    solution: str = Field(..., min_length=1)
    outcomes: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    is_active: bool = Field(default=True)


class KbPricingImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=1, max_length=100)
    service_type: str = Field(..., min_length=1, max_length=100)
    pricing_model: str = Field(..., min_length=1, max_length=50)
    range_text: str = Field(..., min_length=1, max_length=255)
    notes: str | None = None
    keywords: list[str] = Field(default_factory=list)
    is_active: bool = Field(default=True)


class KbSnippetImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=1, max_length=100)
    section: str = Field(..., min_length=1, max_length=100)
    proposal_type: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    keywords: list[str] = Field(default_factory=list)
    is_active: bool = Field(default=True)


class KnowledgeImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    services: list[KbServiceImportRow] = Field(default_factory=list)
    case_studies: list[KbCaseStudyImportRow] = Field(default_factory=list)
    pricing: list[KbPricingImportRow] = Field(default_factory=list)
    snippets: list[KbSnippetImportRow] = Field(default_factory=list)


class KnowledgeImportResponse(BaseModel):
    """Row counts processed per table (insert or upsert on slug conflict)."""

    applied: dict[str, int]
