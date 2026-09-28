from typing import Any, Literal

from pydantic import BaseModel, Field


class RootCause(BaseModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    sources: list[str] = Field(default_factory=list)


class FixStep(BaseModel):
    rank: int
    step: str
    rationale: str
    source_incident_ids: list[str] = Field(default_factory=list)
    source_memory_ids: list[str] = Field(default_factory=list)
    prior_outcome: Literal["worked", "failed", "unknown"] = "unknown"


class AnalysisOutput(BaseModel):
    likely_root_cause: RootCause
    fix_steps: list[FixStep] = Field(default_factory=list)
    runbooks: list[str] = Field(default_factory=list)
    memory_used: list[dict[str, Any]] = Field(default_factory=list)
    memory_status: Literal["off", "ok", "no_match", "unavailable"] = "ok"
    warnings: list[str] = Field(default_factory=list)
    model_used: str = "memory-degraded"


# Response models for endpoints
class AnalyzeRequest(BaseModel):
    alert_text: str
    memory_enabled: bool = True
    compare: bool = False


class AnalyzeResponse(BaseModel):
    analysis_id: str
    memory_on: AnalysisOutput
    memory_off: AnalysisOutput | None = None


class OutcomeRequest(BaseModel):
    analysis_id: str
    result: Literal["fixed", "didnt_work"]
    notes: str = ""


class PostmortemRequest(BaseModel):
    title: str | None = None
    text: str


class PostmortemResponse(BaseModel):
    postmortem_id: str
    status: str
    recalled_sample: list[dict[str, Any]] = Field(default_factory=list)
