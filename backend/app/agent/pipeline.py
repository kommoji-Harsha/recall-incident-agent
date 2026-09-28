import json
import logging
from typing import Any, Sequence

from pydantic import BaseModel, Field

from backend.app.agent.models import AnalysisOutput, FixStep, RootCause
from backend.app.llm.client import GroqLLMClient
from backend.app.memory.protocol import MemoryBackend, RecalledMemory

logger = logging.getLogger(__name__)


class LLMSynthesisSchema(BaseModel):
    root_cause_summary: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    root_cause_sources: list[str] = Field(default_factory=list)
    proposed_fix_steps: list[dict[str, Any]] = Field(default_factory=list)
    suggested_runbooks: list[str] = Field(default_factory=list)


class IncidentAgentPipeline:
    def __init__(
        self,
        memory: MemoryBackend,
        llm_client: GroqLLMClient | None = None,
    ) -> None:
        self.memory = memory
        self.llm_client = llm_client or GroqLLMClient()

    async def analyze(
        self,
        alert_text: str,
        memory_enabled: bool = True,
    ) -> AnalysisOutput:
        alert_text_clean = alert_text.strip()
        if not alert_text_clean:
            return self._build_empty_input_response()

        recalled_memories: list[RecalledMemory] = []
        if memory_enabled:
            try:
                recalled_memories = await self.memory.recall_similar(
                    query=alert_text_clean,
                    budget="mid",
                    max_tokens=4096,
                    prefer_observations=True,
                )
            except Exception as exc:
                logger.warning(f"Hindsight memory recall failed or timed out: {exc}")
                # Hindsight timeout/failure -> fall back gracefully without memory crashing
                recalled_memories = []

        # If memory disabled or recall returned nothing relevant
        if not memory_enabled or not recalled_memories:
            return await self._synthesize_no_memory_or_generic(
                alert_text=alert_text_clean,
                memory_enabled=memory_enabled,
                recalled_memories=recalled_memories,
            )

        # We have recalled memories. Call LLM for synthesis or fall back to degraded memory-only output if LLM fails.
        try:
            return await self._synthesize_with_llm(
                alert_text=alert_text_clean,
                recalled_memories=recalled_memories,
            )
        except Exception as exc:
            logger.error(f"LLM synthesis failed on both primary and fallback models: {exc}")
            return self._build_degraded_memory_response(
                recalled_memories=recalled_memories,
                warning=f"LLM synthesis failed ({str(exc)}). Output assembled directly from recalled memories.",
            )

    async def _synthesize_with_llm(
        self,
        alert_text: str,
        recalled_memories: Sequence[RecalledMemory],
    ) -> AnalysisOutput:
        # Build prompt incorporating memories
        memories_formatted = []
        valid_memory_ids = set()
        valid_incident_ids = set()
        failed_fixes_info = []

        for m in recalled_memories:
            valid_memory_ids.add(m.id)
            if m.source_incident_id:
                valid_incident_ids.add(m.source_incident_id)

            is_failed = False
            if m.metadata and (
                m.metadata.get("result") in ["didnt_work", "failed"]
                or m.metadata.get("has_failed_step") == "true"
            ):
                is_failed = True

            if "FAILED" in m.text or is_failed:
                failed_fixes_info.append(
                    f"Memory {m.id} (Incident {m.source_incident_id or 'unknown'}): {m.text}"
                )

            memories_formatted.append(
                f"- Memory ID: {m.id}\n"
                f"  Type: {m.type}\n"
                f"  Source Incident: {m.source_incident_id or 'none'}\n"
                f"  Text: {m.text}\n"
                f"  Metadata: {json.dumps(m.metadata)}\n"
            )

        prompt = (
            f"ALERT/LOG RECEIVED:\n{alert_text}\n\n"
            f"RECALLED PAST INCIDENT MEMORIES:\n"
            + "\n".join(memories_formatted)
            + "\n\nINSTRUCTIONS:\n"
            "Analyze the alert against recalled memories. Identify root cause and resolution steps.\n"
            "Return JSON matching this structure:\n"
            "{\n"
            '  "root_cause_summary": "...",\n'
            '  "confidence": 0.85,\n'
            '  "root_cause_sources": ["INC-..."],\n'
            '  "proposed_fix_steps": [\n'
            "    {\n"
            '      "step": "...",\n'
            '      "rationale": "...",\n'
            '      "source_incident_ids": ["INC-..."],\n'
            '      "source_memory_ids": ["mem-..."],\n'
            '      "prior_outcome": "worked" | "failed" | "unknown"\n'
            "    }\n"
            "  ],\n"
            '  "suggested_runbooks": ["runbook-..."]\n'
            "}\n"
            "Grounding Rules:\n"
            "1. ONLY reference source memory IDs and incident IDs present in the recalled list above.\n"
            "2. If a past attempt FAILED in a similar incident, set prior_outcome='failed' and explain why."
        )

        llm_res = await self.llm_client.generate_structured(
            prompt=prompt,
            response_model=LLMSynthesisSchema,
        )

        parsed: LLMSynthesisSchema = llm_res.data
        warnings = list(llm_res.warnings)

        # Grounding check: drop citations not in recalled set
        grounded_rc_sources = [
            sid for sid in parsed.root_cause_sources if sid in valid_incident_ids or sid in valid_memory_ids
        ]

        raw_fix_steps = parsed.proposed_fix_steps
        processed_fix_steps: list[FixStep] = []

        for idx, step_item in enumerate(raw_fix_steps):
            step_text = str(step_item.get("step", ""))
            rationale = str(step_item.get("rationale", ""))

            # Filter citations
            step_inc_ids = [
                s for s in step_item.get("source_incident_ids", []) if s in valid_incident_ids
            ]
            step_mem_ids = [
                m for m in step_item.get("source_memory_ids", []) if m in valid_memory_ids
            ]

            prior_outcome = str(step_item.get("prior_outcome", "unknown")).lower()
            if prior_outcome not in ["worked", "failed", "unknown"]:
                prior_outcome = "unknown"

            # Check if this step was marked as failed in recalled memories
            for m in recalled_memories:
                if (
                    m.metadata.get("result") in ["didnt_work", "failed"]
                    or "FAILED" in m.text
                ):
                    if m.source_incident_id and m.source_incident_id not in step_inc_ids:
                        pass
                    # If step text matches a known failed step pattern, mark as failed
                    if any(
                        word in step_text.lower()
                        for word in ["restart", "flushall", "increase", "delete"]
                    ) and ("failed" in m.text.lower() or m.metadata.get("result") == "didnt_work"):
                        if m.source_incident_id and m.source_incident_id not in step_inc_ids:
                            step_inc_ids.append(m.source_incident_id)

            processed_fix_steps.append(
                FixStep(
                    rank=idx + 1,
                    step=step_text,
                    rationale=rationale,
                    source_incident_ids=step_inc_ids,
                    source_memory_ids=step_mem_ids,
                    prior_outcome=prior_outcome,  # type: ignore
                )
            )

        # Demote failed fix steps to bottom rank & append warning
        working_steps = []
        failed_steps = []

        for fs in processed_fix_steps:
            if fs.prior_outcome == "failed":
                failed_inc = fs.source_incident_ids[0] if fs.source_incident_ids else "past incident"
                fs.rationale = f"[DEMOTED - failed in {failed_inc}] {fs.rationale}"
                warnings.append(
                    f"Demoted step '{fs.step[:40]}...' because it previously failed in {failed_inc}."
                )
                failed_steps.append(fs)
            else:
                working_steps.append(fs)

        ranked_steps = working_steps + failed_steps
        for r_idx, fs in enumerate(ranked_steps):
            fs.rank = r_idx + 1

        # Memory used payload
        memory_used = [
            {
                "id": m.id,
                "text": m.text[:200],
                "type": m.type,
                "source_incident_id": m.source_incident_id,
                "scores": m.scores,
            }
            for m in recalled_memories
        ]

        return AnalysisOutput(
            likely_root_cause=RootCause(
                text=parsed.root_cause_summary,
                confidence=parsed.confidence,
                sources=grounded_rc_sources,
            ),
            fix_steps=ranked_steps,
            runbooks=parsed.suggested_runbooks,
            memory_used=memory_used,
            warnings=warnings,
            model_used=llm_res.model_used,
        )

    async def _synthesize_no_memory_or_generic(
        self,
        alert_text: str,
        memory_enabled: bool,
        recalled_memories: Sequence[RecalledMemory],
    ) -> AnalysisOutput:
        # Prompt LLM for generic troubleshooting without past memory
        if not memory_enabled:
            warning_msg = "Memory is OFF. Response generated without historical incident context."
        else:
            warning_msg = "No matching historical incidents found in memory."

        if self.llm_client and self.llm_client.api_key:
            try:
                prompt = (
                    f"ALERT/LOG RECEIVED:\n{alert_text}\n\n"
                    "Analyze this alert and provide generic troubleshooting guidance without referencing any specific past incident history or fake citations.\n"
                    "Return JSON with root_cause_summary, confidence, proposed_fix_steps, suggested_runbooks."
                )
                llm_res = await self.llm_client.generate_structured(
                    prompt=prompt,
                    response_model=LLMSynthesisSchema,
                )
                parsed: LLMSynthesisSchema = llm_res.data

                fix_steps = [
                    FixStep(
                        rank=idx + 1,
                        step=str(item.get("step", "")),
                        rationale=f"[no matching history] {item.get('rationale', '')}",
                        source_incident_ids=[],
                        source_memory_ids=[],
                        prior_outcome="unknown",
                    )
                    for idx, item in enumerate(parsed.proposed_fix_steps)
                ]

                return AnalysisOutput(
                    likely_root_cause=RootCause(
                        text=f"[no matching history] {parsed.root_cause_summary}",
                        confidence=0.5,
                        sources=[],
                    ),
                    fix_steps=fix_steps,
                    runbooks=parsed.suggested_runbooks,
                    memory_used=[],
                    warnings=[warning_msg] + llm_res.warnings,
                    model_used=llm_res.model_used,
                )
            except Exception as exc:
                logger.warning(f"Generic LLM synthesis failed: {exc}")

        # Static offline fallback when no LLM available or LLM fails
        return AnalysisOutput(
            likely_root_cause=RootCause(
                text="[no matching history] Potential service degradation or resource constraint detected.",
                confidence=0.4,
                sources=[],
            ),
            fix_steps=[
                FixStep(
                    rank=1,
                    step="Inspect active service metrics and error logs",
                    rationale="[no matching history] Standard triage procedure when no past memory matches.",
                    source_incident_ids=[],
                    source_memory_ids=[],
                    prior_outcome="unknown",
                ),
                FixStep(
                    rank=2,
                    step="Check downstream database and cache connection limits",
                    rationale="[no matching history] Rule out common infrastructure bottlenecks.",
                    source_incident_ids=[],
                    source_memory_ids=[],
                    prior_outcome="unknown",
                ),
            ],
            runbooks=["runbook-generic-triage.md"],
            memory_used=[],
            warnings=[warning_msg],
            model_used="generic-offline-fallback",
        )

    def _build_degraded_memory_response(
        self,
        recalled_memories: Sequence[RecalledMemory],
        warning: str,
    ) -> AnalysisOutput:
        # Assemble directly from recalled memories when LLM is completely unavailable
        top_mem = recalled_memories[0] if recalled_memories else None

        sources = []
        fix_steps: list[FixStep] = []
        memory_used = []

        for idx, m in enumerate(recalled_memories):
            memory_used.append(
                {
                    "id": m.id,
                    "text": m.text[:200],
                    "type": m.type,
                    "source_incident_id": m.source_incident_id,
                    "scores": m.scores,
                }
            )
            if m.source_incident_id and m.source_incident_id not in sources:
                sources.append(m.source_incident_id)

            # Extract lines from memory text for steps
            lines = [line.strip() for line in m.text.split("\n") if line.strip()]
            for line in lines:
                if line.startswith("- ") or "Resolution:" in line or "Fix:" in line:
                    is_failed = "FAILED" in line or m.metadata.get("result") in ["didnt_work", "failed"]
                    prior_outcome = "failed" if is_failed else "worked"
                    fix_steps.append(
                        FixStep(
                            rank=len(fix_steps) + 1,
                            step=line.lstrip("- ").strip(),
                            rationale=f"Directly extracted from recalled memory {m.id}",
                            source_incident_ids=[m.source_incident_id] if m.source_incident_id else [],
                            source_memory_ids=[m.id],
                            prior_outcome=prior_outcome,  # type: ignore
                        )
                    )

        rc_text = top_mem.text if top_mem else "Uncertain root cause from recalled memories."

        return AnalysisOutput(
            likely_root_cause=RootCause(
                text=f"[Degraded Output] {rc_text[:250]}...",
                confidence=0.6,
                sources=sources,
            ),
            fix_steps=fix_steps[:5],
            runbooks=["runbook-degraded-fallback.md"],
            memory_used=memory_used,
            warnings=[warning],
            model_used="memory-degraded",
        )

    def _build_empty_input_response(self) -> AnalysisOutput:
        return AnalysisOutput(
            likely_root_cause=RootCause(
                text="No alert or log text was provided for analysis.",
                confidence=0.0,
                sources=[],
            ),
            fix_steps=[],
            runbooks=[],
            memory_used=[],
            warnings=["Input alert text was empty."],
            model_used="none",
        )
