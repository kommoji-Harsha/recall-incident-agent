from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from backend.app.llm.client import (
    GroqProvider,
    OpenAIProvider,
    get_llm_provider,
)
from openai import BadRequestError as OpenAIBadRequestError
from pydantic import BaseModel


class SampleSchema(BaseModel):
    summary: str
    score: int


def test_get_llm_provider_factory(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    p1 = get_llm_provider()
    assert isinstance(p1, GroqProvider)

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    p2 = get_llm_provider()
    assert isinstance(p2, OpenAIProvider)

    monkeypatch.setenv("LLM_PROVIDER", "unsupported_provider")
    with pytest.raises(ValueError, match="Unrecognized LLM_PROVIDER"):
        get_llm_provider()


@pytest.mark.asyncio
async def test_openai_provider_success() -> None:
    provider = OpenAIProvider(api_key="sk-test-key", primary_model="gpt-4o-mini")

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"summary": "All systems operational", "score": 100}'
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    provider.client = mock_client

    parsed, model_used = await provider.complete_json(
        system="You are an assistant.",
        user="Check status",
        schema=SampleSchema,
    )

    assert parsed.summary == "All systems operational"
    assert parsed.score == 100
    assert model_used == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_openai_provider_malformed_json_retry() -> None:
    provider = OpenAIProvider(api_key="sk-test-key", primary_model="gpt-4o-mini", max_retries_per_model=2)

    mock_resp_bad = MagicMock()
    mock_resp_bad.choices = [MagicMock(message=MagicMock(content="Malformed JSON { summary"))]

    mock_resp_good = MagicMock()
    mock_resp_good.choices = [MagicMock(message=MagicMock(content='{"summary": "Fixed", "score": 90}'))]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[mock_resp_bad, mock_resp_good])
    provider.client = mock_client

    parsed, model_used = await provider.complete_json(
        system="System",
        user="Query",
        schema=SampleSchema,
    )

    assert parsed.summary == "Fixed"
    assert parsed.score == 90
    assert model_used == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_openai_provider_non_retryable_error_switch_to_fallback() -> None:
    provider = OpenAIProvider(
        api_key="sk-test-key",
        primary_model="primary-bad-model",
        fallback_model="fallback-good-model",
    )

    dummy_req = httpx.Request("POST", "http://test")
    dummy_res = httpx.Response(400, request=dummy_req)
    bad_req_err = OpenAIBadRequestError("Invalid model parameter", response=dummy_res, body={})

    mock_resp_fallback = MagicMock()
    mock_resp_fallback.choices = [MagicMock(message=MagicMock(content='{"summary": "Fallback success", "score": 80}'))]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[bad_req_err, mock_resp_fallback])
    provider.client = mock_client

    parsed, model_used = await provider.complete_json(
        system="System",
        user="Query",
        schema=SampleSchema,
    )

    assert parsed.summary == "Fallback success"
    assert model_used == "fallback-good-model"


@pytest.mark.asyncio
async def test_openai_provider_total_failure_raises() -> None:
    provider = OpenAIProvider(api_key="sk-test-key", max_retries_per_model=1)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API Network error"))
    provider.client = mock_client

    with pytest.raises(RuntimeError, match="Both primary .* and fallback .* models failed"):
        await provider.complete_json(
            system="System",
            user="Query",
            schema=SampleSchema,
        )
