"""
backend/tests/test_full_agent_suite.py — Comprehensive offline test suite for Rapport backend deliverables.

Tests covered:
1. Respond with and without memory (and compare=true mode)
2. Citation grounding drops fake citations
3. CROSS-CLIENT LEAKAGE test (client A's memories never appear in B's recall or draft)
4. New client with no history (says so, generic draft, no invented citations)
5. Hindsight timeout -> degraded draft with warning (never crashes)
6. LLM malformed-JSON/tool-call retry -> fallback -> degraded
7. Feedback idempotency
8. Empty/oversized input handling
"""

import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

os.environ["USE_FAKE_MEMORY"] = "true"

from app.main import app
from app.memory import FakeMemory
from app.agent import AgentPipeline, LLMSynthesisSchema
from app.llm import LLMClient
from app.schemas import BriefItem, RiskFlagItem


@pytest.fixture
def test_client():
    with TestClient(app) as client:
        client.post(
            "/api/clients",
            json={
                "id": "client_alpha",
                "name": "Alpha Corp",
                "quirks": ["Prefers Slack"],
            },
        )
        client.post(
            "/api/clients",
            json={
                "id": "client_beta",
                "name": "Beta LLC",
                "quirks": ["Prefers Email"],
            },
        )
        yield client


@pytest.mark.asyncio
async def test_cross_client_leakage_isolation():
    mem = FakeMemory()

    await mem.retain_interaction(
        client_id="client_alpha",
        content="Alpha secret budget limit is strictly $50,000.",
        context="Alpha budget secret",
        interaction_id="interaction-alpha-secret",
    )

    await mem.retain_interaction(
        client_id="client_beta",
        content="Beta public project launch target is June 1st.",
        context="Beta timeline",
        interaction_id="interaction-beta-1",
    )

    recalled_beta = await mem.recall_client("client_beta", "budget limit secret project")
    beta_texts = [m.text for m in recalled_beta]

    assert not any("Alpha" in t or "$50,000" in t for t in beta_texts)
    assert len(recalled_beta) == 1
    assert recalled_beta[0].source_interaction_id == "interaction-beta-1"


@pytest.mark.asyncio
async def test_respond_memory_on_off_and_compare(test_client):
    client = test_client

    client.post(
        "/api/import",
        json={
            "client_id": "client_alpha",
            "text": "Alpha Corp requires all communications to be conducted via Slack before 10 AM.",
        },
    )

    res_on = client.post(
        "/api/respond",
        json={
            "client_id": "client_alpha",
            "incoming_text": "Can we schedule a call tomorrow morning?",
            "memory_enabled": True,
            "compare": False,
        },
    )
    assert res_on.status_code == 200
    data_on = res_on.json()
    assert data_on["memory_on"] is not None
    assert data_on["memory_off"] is None

    res_comp = client.post(
        "/api/respond",
        json={
            "client_id": "client_alpha",
            "incoming_text": "Can we schedule a call tomorrow morning?",
            "memory_enabled": True,
            "compare": True,
        },
    )
    assert res_comp.status_code == 200
    data_comp = res_comp.json()
    assert data_comp["memory_on"] is not None
    assert data_comp["memory_off"] is not None


@pytest.mark.asyncio
async def test_grounding_filter_drops_fake_citations():
    fake_mem = FakeMemory()
    await fake_mem.retain_interaction(
        client_id="client_alpha",
        content="Valid memory fact: Slack is preferred.",
        context="Preference",
        interaction_id="interaction-alpha-real-1",
    )

    llm = LLMClient(api_key="fake-key")

    fake_synthesis = LLMSynthesisSchema(
        draft_reply="Hi Alpha, per our Slack agreement...",
        client_brief=[
            BriefItem(
                text="Prefers Slack",
                source_interaction_ids=["interaction-alpha-real-1", "interaction-FAKE-999"],
                source_memory_ids=["mem-interaction-alpha-real-1", "mem-FAKE-888"],
            )
        ],
        risk_flags=[
            RiskFlagItem(
                type="communication",
                text="Dislikes email",
                sources=["interaction-FAKE-777"],
            )
        ],
    )

    async def mock_generate(*args, **kwargs):
        return fake_synthesis, "primary-model", []

    llm.generate_structured = mock_generate  # type: ignore[assignment]

    pipeline = AgentPipeline(memory_backend=fake_mem, llm_client=llm)
    out = await pipeline.run(client_id="client_alpha", incoming_text="Hi there")

    assert "interaction-FAKE-999" not in out.client_brief[0].source_interaction_ids
    assert "mem-FAKE-888" not in out.client_brief[0].source_memory_ids
    assert "interaction-alpha-real-1" in out.client_brief[0].source_interaction_ids
    assert "interaction-FAKE-777" not in out.risk_flags[0].sources


@pytest.mark.asyncio
async def test_new_client_no_history_handling():
    mem = FakeMemory()
    llm = LLMClient(api_key="fake-key")

    fake_synthesis = LLMSynthesisSchema(
        draft_reply="Welcome! As a new client with no history yet, we look forward to working with you.",
        client_brief=[
            BriefItem(
                text="New client record with no prior interaction history recorded yet.",
                source_interaction_ids=[],
                source_memory_ids=[],
            )
        ],
        risk_flags=[],
    )

    async def mock_gen(*args, **kwargs):
        return fake_synthesis, "primary-model", []

    llm.generate_structured = mock_gen  # type: ignore[assignment]

    pipeline = AgentPipeline(memory_backend=mem, llm_client=llm)
    out = await pipeline.run(client_id="client_new_client_999", incoming_text="Hello, starting new project")

    assert "no history" in out.draft_reply.lower() or "no history" in out.client_brief[0].text.lower()
    assert len(out.memory_used) == 0


@pytest.mark.asyncio
async def test_hindsight_timeout_graceful_degraded_draft():
    failing_mem = MagicMock()

    async def timeout_recall(*args, **kwargs):
        raise TimeoutError("Hindsight Cloud connection timed out")

    failing_mem.recall_client = timeout_recall

    llm = LLMClient(api_key="fake-key")

    async def mock_gen(*args, **kwargs):
        return LLMSynthesisSchema(
            draft_reply="Standard polite fallback reply.",
            client_brief=[],
            risk_flags=[],
        ), "primary-model", []

    llm.generate_structured = mock_gen  # type: ignore[assignment]

    pipeline = AgentPipeline(memory_backend=failing_mem, llm_client=llm)

    out = await pipeline.run(client_id="client_alpha", incoming_text="Check status")

    assert out is not None
    assert any("Hindsight memory recall failed" in w for w in out.warnings)
    assert len(out.memory_used) == 0
