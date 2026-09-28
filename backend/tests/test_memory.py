"""
backend/tests/test_memory.py — Unit tests for FakeMemory and memory layer tag isolation.
"""

import pytest
from app.memory import FakeMemory, MemoryBackend


@pytest.mark.asyncio
async def test_fake_memory_protocol():
    mem = FakeMemory()
    assert isinstance(mem, MemoryBackend)


@pytest.mark.asyncio
async def test_fake_memory_tag_isolation():
    mem = FakeMemory()

    await mem.retain_interaction(
        client_id="client_a",
        content="Client A requires Slack messages only.",
        context="Communication preference",
        interaction_id="interaction-a-1",
    )

    await mem.retain_interaction(
        client_id="client_b",
        content="Client B requires Zoom calls on Mondays.",
        context="Communication preference",
        interaction_id="interaction-b-1",
    )

    recalled_a = await mem.recall_client("client_a", "communication channel preference")
    assert len(recalled_a) == 1
    assert recalled_a[0].source_interaction_id == "interaction-a-1"
    assert "Slack messages" in recalled_a[0].text

    recalled_b = await mem.recall_client("client_b", "communication channel preference")
    assert len(recalled_b) == 1
    assert recalled_b[0].source_interaction_id == "interaction-b-1"
    assert "Zoom calls" in recalled_b[0].text

    recalled_c = await mem.recall_client("client_c", "communication channel preference")
    assert len(recalled_c) == 0


@pytest.mark.asyncio
async def test_fake_memory_feedback_and_source_id():
    mem = FakeMemory()

    await mem.retain_interaction(
        client_id="client_a",
        content="Initial meeting note.",
        context="Meeting",
        interaction_id="interaction-a-10",
    )

    await mem.retain_feedback(
        client_id="client_a",
        interaction_id="interaction-a-10",
        outcome="went_well",
        notes="Client liked the quick summary.",
    )

    recalled = await mem.recall_client("client_a", "summary feedback")
    assert len(recalled) == 2
    feedback_item = next(r for r in recalled if "feedback-interaction-a-10" in r.document_id)
    assert feedback_item.source_interaction_id == "interaction-a-10"
    assert "went_well" in feedback_item.text
