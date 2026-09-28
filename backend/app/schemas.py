"""
backend/app/schemas.py — Pydantic models for REST API request/response payloads.
"""

from typing import Literal
from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    id: str
    name: str
    company: str | None = None
    primary_contact: str | None = None
    influencers: list[str] = Field(default_factory=list)
    quirks: list[str] = Field(default_factory=list)
    notes: str | None = None


class ClientResponse(BaseModel):
    id: str
    name: str
    company: str | None = None
    primary_contact: str | None = None
    influencers: list[str] = Field(default_factory=list)
    quirks: list[str] = Field(default_factory=list)
    notes: str | None = None
    created_at: str | None = None


class BriefItem(BaseModel):
    text: str = Field(description="Summary brief point about the client")
    source_interaction_ids: list[str] = Field(
        default_factory=list, description="List of source interaction IDs cited"
    )
    source_memory_ids: list[str] = Field(
        default_factory=list, description="List of memory unit IDs cited"
    )


class RiskFlagItem(BaseModel):
    type: str = Field(
        description="Type of risk (e.g., payment, scope_creep, communication_channel, compliance)"
    )
    text: str = Field(description="Detailed explanation of the risk flag")
    sources: list[str] = Field(default_factory=list, description="Source interaction or memory IDs")


class MemoryUsedItem(BaseModel):
    id: str
    text: str
    type: str
    source_interaction_id: str
    document_id: str | None = None


class RespondRequest(BaseModel):
    client_id: str
    incoming_text: str
    memory_enabled: bool = True
    compare: bool = False


class SingleAgentOutput(BaseModel):
    response_id: str
    draft_reply: str
    client_brief: list[BriefItem] = Field(default_factory=list)
    risk_flags: list[RiskFlagItem] = Field(default_factory=list)
    memory_used: list[MemoryUsedItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model_used: str


class RespondResponse(BaseModel):
    memory_on: SingleAgentOutput
    memory_off: SingleAgentOutput | None = None


class FeedbackRequest(BaseModel):
    response_id: str
    outcome: Literal["went_well", "pushback"]
    notes: str | None = None


class FeedbackResponse(BaseModel):
    status: str
    message: str
    feedback_id: str
    response_id: str
    outcome: str


class ImportRequest(BaseModel):
    client_id: str
    text: str


class ImportResponse(BaseModel):
    status: str
    client_id: str
    retained_doc_id: str
    recalled_memories: list[MemoryUsedItem]
