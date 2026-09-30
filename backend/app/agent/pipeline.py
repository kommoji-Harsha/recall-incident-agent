import json
import logging
import re
from typing import Any, Literal, Sequence

from pydantic import BaseModel, Field

from backend.app.agent.models import AnalysisOutput, FixStep, RootCause
from backend.app.llm.client import LLMProvider, get_llm_provider
from backend.app.memory.protocol import MemoryBackend, RecalledMemory

logger = logging.getLogger(__name__)


def tokenize_text(text: str) -> set[str]:
    """Tokenize and normalize text into word tokens for Jaccard overlap."""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = {w for w in clean.split() if len(w) > 2}
    return tokens


def jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate token Jaccard similarity between two strings."""
    tokens1 = tokenize_text(text1)
    tokens2 = tokenize_text(text2)
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)


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
        llm_client: LLMProvider | None = None,
    ) -> None:
        self.memory = memory
        self.llm_client = llm_client or get_llm_provider()

    async def analyze(
        self,
        alert_text: str,
        memory_enabled: bool = True,
    ) -> AnalysisOutput:
        alert_text_clean = alert_text.strip()
        if not alert_text_clean:
            return self._build_empty_input_response()

        if not memory_enabled:
            return await self._synthesize_no_memory_or_generic(
                alert_text=alert_text_clean,
                memory_status="off",
            )

        # Recall with 1 retry on failure
        recalled_memories: list[RecalledMemory] = []
        recall_failed = False
        for attempt in range(2):
            try:
                recalled_memories = await self.memory.recall_similar(
                    query=alert_text_clean,
                    budget="mid",
                    max_tokens=4096,
                    prefer_observations=True,
                )
                recall_failed = False
                break
            except Exception as exc:
                logger.warning(f"Recall attempt {attempt + 1} failed: {exc}")
                recall_failed = True
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(1.0)

        if recall_failed:
            return await self._synthesize_no_memory_or_generic(
                alert_text=alert_text_clean,
                memory_status="unavailable",
            )

        if not recalled_memories:
            return await self._synthesize_no_memory_or_generic(
                alert_text=alert_text_clean,
                memory_status="no_match",
            )

        # Memories found: call LLM provider or fall back to degraded response
        try:
            return await self._synthesize_with_llm(
                alert_text=alert_text_clean,
                recalled_memories=recalled_memories,
            )
        except Exception as exc:
            logger.error(f"LLM synthesis failed on primary and fallback models: {exc}")
            return self._build_degraded_memory_response(
                recalled_memories=recalled_memories,
                warning=f"LLM synthesis failed ({str(exc)}). Output assembled directly from recalled memories.",
            )

    async def _synthesize_with_llm(
        self,
        alert_text: str,
        recalled_memories: Sequence[RecalledMemory],
    ) -> AnalysisOutput:
        memories_formatted = []
        valid_memory_ids = set()
        valid_incident_ids = set()
        failed_fixes_info: list[str] = []

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
                    f"- Memory ID {m.id} (Incident {m.source_incident_id or 'unknown'}): {m.text}"
                )

            memories_formatted.append(
                f"- Memory ID: {m.id}\n"
                f"  Type: {m.type}\n"
                f"  Source Incident: {m.source_incident_id or 'none'}\n"
                f"  Text: {m.text}\n"
                f"  Metadata: {json.dumps(m.metadata)}\n"
            )

        failed_fixes_str = (
            "\n".join(failed_fixes_info)
            if failed_fixes_info
            else "None identified in recalled memories."
        )

        prompt = (
            f"ALERT/LOG RECEIVED:\n{alert_text}\n\n"
            f"RECALLED PAST INCIDENT MEMORIES:\n"
            + "\n".join(memories_formatted)
            + f"\n\nKNOWN FAILED FIX ATTEMPTS IN PAST INCIDENTS:\n{failed_fixes_str}\n\n"
            "INSTRUCTIONS:\n"
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

        system_prompt = (
            "You are an incident response agent. Output strictly valid JSON matching the requested schema."
        )

        parsed, model_used = await self.llm_client.complete_json(
            system=system_prompt,
            user=prompt,
            schema=LLMSynthesisSchema,
        )

        warnings: list[str] = []

        grounded_rc_sources = [
            sid for sid in parsed.root_cause_sources if sid in valid_incident_ids or sid in valid_memory_ids
        ]

        raw_fix_steps = parsed.proposed_fix_steps
        processed_fix_steps: list[FixStep] = []

        failed_texts: list[tuple[str, str]] = []
        for m in recalled_memories:
            is_failed_mem = (
                m.metadata.get("result") in ["didnt_work", "failed"]
                or m.metadata.get("has_failed_step") == "true"
                or "FAILED" in m.text
            )
            if is_failed_mem:
                failed_inc = m.source_incident_id or "INC-unknown"
                for paragraph in m.text.split(". "):
                    if "FAILED" in paragraph or "Tried First" in paragraph or "did not work" in paragraph.lower():
                        failed_texts.append((paragraph, failed_inc))
                if not failed_texts:
                    failed_texts.append((m.text, failed_inc))

        for idx, step_item in enumerate(raw_fix_steps):
            step_text = str(step_item.get("step", ""))
            rationale = str(step_item.get("rationale", ""))

            step_inc_ids = [
                s for s in step_item.get("source_incident_ids", []) if s in valid_incident_ids
            ]
            step_mem_ids = [
                m for m in step_item.get("source_memory_ids", []) if m in valid_memory_ids
            ]

            prior_outcome = str(step_item.get("prior_outcome", "unknown")).lower()
            if prior_outcome not in ["worked", "failed", "unknown"]:
                prior_outcome = "unknown"

            for f_text, f_inc in failed_texts:
                sim = jaccard_similarity(step_text, f_text)
                if sim >= 0.5:
                    prior_outcome = "failed"
                    if f_inc not in step_inc_ids and f_inc != "INC-unknown":
                        step_inc_ids.append(f_inc)
                    break

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

        working_steps: list[FixStep] = []
        failed_steps: list[FixStep] = []

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
            memory_status="ok",
            warnings=warnings,
            model_used=model_used,
        )

    async def _synthesize_no_memory_or_generic(
        self,
        alert_text: str,
        memory_status: Literal["off", "ok", "no_match", "unavailable"],
    ) -> AnalysisOutput:
        warnings = []
        if memory_status == "off":
            recalled_section = "none provided (memory OFF)"
        elif memory_status == "unavailable":
            warnings.append("Memory unavailable: answer generated without history")
            recalled_section = "none provided (memory service unavailable)"
        else:
            warnings.append("No matching historical incidents found in memory.")
            recalled_section = "none provided (no matching history found)"

        prompt = (
            f"ALERT/LOG RECEIVED:\n{alert_text}\n\n"
            f"RECALLED PAST INCIDENT MEMORIES:\n{recalled_section}\n\n"
            "INSTRUCTIONS:\n"
            "Analyze the alert and provide troubleshooting guidance without referencing any specific past incident history or fake citations.\n"
            "Return JSON matching this structure:\n"
            "{\n"
            '  "root_cause_summary": "...",\n'
            '  "confidence": 0.5,\n'
            '  "root_cause_sources": [],\n'
            '  "proposed_fix_steps": [\n'
            "    {\n"
            '      "step": "...",\n'
            '      "rationale": "...",\n'
            '      "source_incident_ids": [],\n'
            '      "source_memory_ids": [],\n'
            '      "prior_outcome": "unknown"\n'
            "    }\n"
            "  ],\n"
            '  "suggested_runbooks": ["runbook-..."]\n'
            "}\n"
            "Grounding Rules:\n"
            "1. ONLY reference source memory IDs and incident IDs present in the recalled list above."
        )

        system_prompt = (
            "You are an incident response agent. Output strictly valid JSON matching the requested schema."
        )

        if self.llm_client and self.llm_client.api_key:
            try:
                parsed, model_used = await self.llm_client.complete_json(
                    system=system_prompt,
                    user=prompt,
                    schema=LLMSynthesisSchema,
                )

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
                    memory_status=memory_status,
                    warnings=warnings,
                    model_used=model_used,
                )
            except Exception as exc:
                logger.warning(f"Generic LLM synthesis failed: {exc}")

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
            memory_status=memory_status,
            warnings=warnings,
            model_used="generic-offline-fallback",
        )

    def _build_degraded_memory_response(
        self,
        recalled_memories: Sequence[RecalledMemory],
        warning: str,
    ) -> AnalysisOutput:
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
            memory_status="ok",
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
            memory_status="off",
            warnings=["Input alert text was empty."],
            model_used="none",
        )
