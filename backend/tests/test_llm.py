"""
backend/tests/test_llm.py — Unit tests for LLMClient retries, model fallback, and degradation.
"""

import pytest
from pydantic import BaseModel
from app.llm import LLMClient


class DummySchema(BaseModel):
    greeting: str
    count: int


@pytest.mark.asyncio
async def test_llm_client_success_primary():
    client = LLMClient(api_key="fake-key", primary_model="primary-m", fallback_model="fallback-m")

    def mock_call(model, system_prompt, user_prompt):
        return '{"greeting": "hello", "count": 42}'

    client._call_groq = mock_call  # type: ignore[assignment]

    obj, model_used, warnings = await client.generate_structured(
        prompt="Hi", system_prompt="Sys", response_schema=DummySchema
    )

    assert obj is not None
    assert obj.greeting == "hello"
    assert obj.count == 42
    assert model_used == "primary-m"
    assert len(warnings) == 0


@pytest.mark.asyncio
async def test_llm_client_fallback_model():
    client = LLMClient(
        api_key="fake-key",
        primary_model="primary-m",
        fallback_model="fallback-m",
        max_retries_per_model=2,
        base_backoff_seconds=0.01,
    )

    calls = []

    def mock_call(model, system_prompt, user_prompt):
        calls.append(model)
        if model == "primary-m":
            raise RuntimeError("Primary model rate limit 429")
        return '{"greeting": "fallback_hello", "count": 99}'

    client._call_groq = mock_call  # type: ignore[assignment]

    obj, model_used, warnings = await client.generate_structured(
        prompt="Hi", system_prompt="Sys", response_schema=DummySchema
    )

    assert obj is not None
    assert obj.greeting == "fallback_hello"
    assert model_used == "fallback-m"
    assert calls == ["primary-m", "primary-m", "fallback-m"]
    assert any("Primary model rate limit 429" in w for w in warnings)


@pytest.mark.asyncio
async def test_llm_client_both_failed_degraded():
    client = LLMClient(
        api_key="fake-key",
        primary_model="primary-m",
        fallback_model="fallback-m",
        max_retries_per_model=2,
        base_backoff_seconds=0.01,
    )

    def mock_call(model, system_prompt, user_prompt):
        raise RuntimeError("Service unavailable")

    client._call_groq = mock_call  # type: ignore[assignment]

    obj, model_used, warnings = await client.generate_structured(
        prompt="Hi", system_prompt="Sys", response_schema=DummySchema
    )

    assert obj is None
    assert model_used == "none"
    assert any("Returning degraded response" in w for w in warnings)
