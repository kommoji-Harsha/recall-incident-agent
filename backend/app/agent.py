"""
backend/app/agent.py — Deterministic agent pipeline: (Recall -> Synthesize -> Citation Grounding Filter).
"""

import logging
import uuid
from typing import Any
from pydantic import BaseModel, Field

from app.memory.models import MemoryItem
from app.memory.protocol import MemoryBackend
from app.llm.client import LLMClient
from app.schemas import BriefItem, MemoryUsedItem, RiskFlagItem, SingleAgentOutput

logger = logging.getLogger(__name__)


class LLMSynthesisSchema(BaseModel):
    draft_reply: str = Field(description="Draft response message for the client")
    client_brief: list[BriefItem] = Field(default_factory=list, description="Client history points with citations")
    risk_flags: list[RiskFlagItem] = Field(default_factory=list, description="Risk flags with citations")


class AgentPipeline:
    def __init__(self, memory_backend: MemoryBackend | None, llm_client: LLMClient) -> None:
        self.memory_backend = memory_backend
        self.llm_client = llm_client

    async def run(
        self,
        client_id: str,
        incoming_text: str,
        memory_enabled: bool = True,
        client_info: dict[str, Any] | None = None,
    ) -> SingleAgentOutput:
        response_id = f"resp-{uuid.uuid4().hex[:12]}"
        warnings: list[str] = []

        client_name = client_info.get("name", client_id) if client_info else client_id
        recalled_memories: list[MemoryItem] = []

        if memory_enabled and self.memory_backend is not None:
            try:
                recalled_memories = await self.memory_backend.recall_client(
                    client_id=client_id,
                    query=incoming_text,
                    max_results=10,
                )
            except Exception as ex:
                warn_msg = f"Hindsight memory recall failed: {ex}. Proceeding with degraded memory-off baseline."
                logger.warning(warn_msg)
                warnings.append(warn_msg)
                recalled_memories = []

        no_history = memory_enabled and len(recalled_memories) == 0

        memory_used_items: list[MemoryUsedItem] = [
            MemoryUsedItem(
                id=m.id,
                text=m.text,
                type=m.type,
                source_interaction_id=m.source_interaction_id,
                document_id=m.document_id,
            )
            for m in recalled_memories
        ]

        valid_source_ids = {m.source_interaction_id for m in recalled_memories}
        valid_doc_ids = {m.document_id for m in recalled_memories if m.document_id}
        valid_memory_ids = {m.id for m in recalled_memories}
        all_valid_ids = valid_source_ids | valid_doc_ids | valid_memory_ids

        if not memory_enabled:
            system_prompt = (
                "You are Rapport, an expert client communication assistant for freelancers.\n"
                "Memory is currently OFF. Draft a polite, professional, standard response to the client's message.\n"
                "Do NOT invent client history, payment habits, or past preferences. Do NOT include citations or risk flags."
            )
            user_prompt = f"Client: {client_name}\nIncoming Message: {incoming_text}"
        elif no_history:
            system_prompt = (
                "You are Rapport, an expert client communication assistant for freelancers.\n"
                "This client has NO prior interaction history recorded in memory yet.\n"
                "Explicitly note in the draft or brief that there is 'no history yet' for this new client.\n"
                "Draft a welcoming, professional response and do NOT invent past interactions or citations."
            )
            user_prompt = f"Client: {client_name} (New Client - No history recorded yet)\nIncoming Message: {incoming_text}"
        else:
            formatted_memories = []
            for m in recalled_memories:
                formatted_memories.append(
                    f"- [Memory ID: {m.id} | Source Interaction ID: {m.source_interaction_id}] "
                    f"({m.type}): {m.text}"
                )
            memories_str = "\n".join(formatted_memories)

            system_prompt = (
                "You are Rapport, an AI client-memory assistant for freelancers.\n"
                "Your objective is to help the freelancer respond to a client message by recalling history from memory.\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. CITATIONS & GROUNDING:\n"
                "   - Every point in `client_brief` MUST cite `source_interaction_ids` and `source_memory_ids` from recalled memories.\n"
                "   - Every item in `risk_flags` MUST cite `sources` from recalled memories.\n"
                "   - Never invent source IDs or memory IDs not present in recalled memory.\n"
                "2. CONTRADICTIONS & PREFERENCES:\n"
                "   - If recalled memories contradict an older fact (e.g. channel changed from email to Slack), "
                "state the CURRENT preference clearly and mention the change.\n"
                "3. DRAFT REPLY TONE & PRIVACY:\n"
                "   - The draft reply must align with client preferences (tone, conciseness, communication timing, channel, payment rules).\n"
                "   - NEVER reveal raw internal freelancer notes or internal risk flags inside the draft reply itself.\n"
            )

            user_prompt = (
                f"Client Name: {client_name}\n"
                f"Incoming Message: {incoming_text}\n\n"
                f"Recalled Client Memory History:\n{memories_str}\n\n"
                "Synthesize JSON output conforming to the required schema."
            )

        synth_result, model_used, llm_warnings = await self.llm_client.generate_structured(
            prompt=user_prompt,
            system_prompt=system_prompt,
            response_schema=LLMSynthesisSchema,
        )
        warnings.extend(llm_warnings)

        if synth_result is None:
            degraded_draft = self._build_degraded_draft(client_name, incoming_text, recalled_memories, memory_enabled)
            degraded_brief = [
                BriefItem(
                    text=f"Recalled memory: {m.text[:100]}...",
                    source_interaction_ids=[m.source_interaction_id],
                    source_memory_ids=[m.id],
                )
                for m in recalled_memories[:3]
            ]
            warnings.append("LLM service unavailable. Generated degraded draft response directly from recalled memories.")

            return SingleAgentOutput(
                response_id=response_id,
                draft_reply=degraded_draft,
                client_brief=degraded_brief,
                risk_flags=[],
                memory_used=memory_used_items,
                warnings=warnings,
                model_used="none",
            )

        grounded_brief: list[BriefItem] = []
        for item in synth_result.client_brief:
            valid_srcs = [sid for sid in item.source_interaction_ids if sid in all_valid_ids]
            valid_mems = [mid for mid in item.source_memory_ids if mid in all_valid_ids]
            grounded_brief.append(
                BriefItem(
                    text=item.text,
                    source_interaction_ids=valid_srcs,
                    source_memory_ids=valid_mems,
                )
            )

        grounded_risks: list[RiskFlagItem] = []
        for risk in synth_result.risk_flags:
            valid_risk_sources = [s for s in risk.sources if s in all_valid_ids]
            grounded_risks.append(
                RiskFlagItem(
                    type=risk.type,
                    text=risk.text,
                    sources=valid_risk_sources,
                )
            )

        return SingleAgentOutput(
            response_id=response_id,
            draft_reply=synth_result.draft_reply,
            client_brief=grounded_brief,
            risk_flags=grounded_risks,
            memory_used=memory_used_items,
            warnings=warnings,
            model_used=model_used,
        )

    def _build_degraded_draft(
        self, client_name: str, incoming_text: str, memories: list[MemoryItem], memory_enabled: bool
    ) -> str:
        if not memory_enabled or not memories:
            return f"Hi {client_name},\n\nThank you for your message. I have received your request regarding: '{incoming_text[:60]}...'\n\nBest regards,\nJules"

        summary_points = "; ".join([m.text for m in memories[:2]])
        return (
            f"Hi {client_name},\n\n"
            f"Thank you for reaching out. Based on our prior interactions ({summary_points}), "
            f"I have received your note: '{incoming_text}' and will get back to you shortly with next steps.\n\n"
            "Best regards,\nJules"
        )
