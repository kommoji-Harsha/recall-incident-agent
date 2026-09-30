import asyncio
import os
import random
import re
from typing import Any, Protocol, Type, TypeVar

from groq import (
    APIStatusError as GroqAPIStatusError,
)
from groq import (
    AsyncGroq,
)
from groq import (
    AuthenticationError as GroqAuthenticationError,
)
from groq import (
    BadRequestError as GroqBadRequestError,
)
from groq import (
    NotFoundError as GroqNotFoundError,
)
from groq import (
    PermissionDeniedError as GroqPermissionDeniedError,
)
from openai import (
    APIStatusError as OpenAIAPIStatusError,
)
from openai import (
    AsyncOpenAI,
)
from openai import (
    AuthenticationError as OpenAIAuthenticationError,
)
from openai import (
    BadRequestError as OpenAIBadRequestError,
)
from openai import (
    NotFoundError as OpenAINotFoundError,
)
from openai import (
    PermissionDeniedError as OpenAIPermissionDeniedError,
)
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMResult(BaseModel):
    data: Any
    model_used: str
    warnings: list[str] = []


def strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from LLM response content."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


class LLMProvider(Protocol):
    primary_model: str
    fallback_model: str
    api_key: str

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: Type[T],
    ) -> tuple[T, str]:
        ...


class GroqProvider:
    def __init__(
        self,
        api_key: str | None = None,
        primary_model: str | None = None,
        fallback_model: str | None = None,
        timeout: float = 30.0,
        max_retries_per_model: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.primary_model = primary_model or os.environ.get(
            "GROQ_PRIMARY_MODEL", "openai/gpt-oss-120b"
        )
        self.fallback_model = fallback_model or os.environ.get(
            "GROQ_FALLBACK_MODEL", "qwen/qwen3-32b"
        )
        self.timeout = timeout
        self.max_retries_per_model = max_retries_per_model

        self.client = AsyncGroq(api_key=self.api_key) if self.api_key else None

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: Type[T],
    ) -> tuple[T, str]:
        if not self.client:
            raise RuntimeError("Groq API key not configured")

        models_to_try = [self.primary_model, self.fallback_model]
        warnings: list[str] = []

        for model_idx, model in enumerate(models_to_try):
            for attempt in range(self.max_retries_per_model):
                try:
                    kwargs: dict[str, Any] = {
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "model": model,
                        "temperature": 0.0,
                        "response_format": {"type": "json_object"},
                        "timeout": self.timeout,
                    }

                    if "qwen" in model.lower():
                        kwargs["reasoning_format"] = "hidden"

                    try:
                        response = await self.client.chat.completions.create(**kwargs)
                    except TypeError:
                        kwargs.pop("reasoning_format", None)
                        response = await self.client.chat.completions.create(**kwargs)

                    raw_content = response.choices[0].message.content or "{}"
                    clean_content = strip_think_blocks(raw_content)

                    parsed_data = schema.model_validate_json(clean_content)
                    return parsed_data, model

                except (
                    GroqBadRequestError,
                    GroqAuthenticationError,
                    GroqPermissionDeniedError,
                    GroqNotFoundError,
                ) as err:
                    err_str = str(err)
                    warnings.append(
                        f"Model {model} non-retryable error ({err_str}). Moving to next model."
                    )
                    break

                except GroqAPIStatusError as err:
                    if err.status_code in [400, 401, 403, 404]:
                        warnings.append(
                            f"Model {model} non-retryable HTTP {err.status_code}. Moving to next model."
                        )
                        break
                    err_str = str(err)
                    warnings.append(f"Attempt {attempt + 1} on model {model} failed: {err_str}")
                    if attempt < self.max_retries_per_model - 1:
                        await asyncio.sleep((2 ** attempt) + random.uniform(0.1, 0.5))

                except Exception as exc:
                    err_str = str(exc)
                    warnings.append(f"Attempt {attempt + 1} on model {model} failed: {err_str}")

                    if attempt < self.max_retries_per_model - 1:
                        sleep_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                        await asyncio.sleep(sleep_time)

            if model_idx == 0:
                warnings.append(
                    f"Primary model {self.primary_model} failed/exhausted. Falling back to {self.fallback_model}."
                )

        raise RuntimeError(
            f"Both primary ({self.primary_model}) and fallback ({self.fallback_model}) models failed. Warnings: {warnings}"
        )

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: str = "You are an incident response agent. Output strictly valid JSON matching the requested schema.",
        temperature: float = 0.0,
    ) -> LLMResult:
        parsed_data, model_used = await self.complete_json(
            system=system_prompt,
            user=prompt,
            schema=response_model,
        )
        return LLMResult(data=parsed_data, model_used=model_used, warnings=[])


class OpenAIProvider:
    def __init__(
        self,
        api_key: str | None = None,
        primary_model: str | None = None,
        fallback_model: str | None = None,
        timeout: float = 30.0,
        max_retries_per_model: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.primary_model = primary_model or os.environ.get(
            "OPENAI_PRIMARY_MODEL", "gpt-4o-mini"
        )
        self.fallback_model = fallback_model or os.environ.get(
            "OPENAI_FALLBACK_MODEL", "gpt-4.1-mini"
        )
        self.timeout = timeout
        self.max_retries_per_model = max_retries_per_model

        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: Type[T],
    ) -> tuple[T, str]:
        if not self.client:
            raise RuntimeError("OpenAI API key not configured")

        models_to_try = [self.primary_model, self.fallback_model]
        warnings: list[str] = []

        for model_idx, model in enumerate(models_to_try):
            for attempt in range(self.max_retries_per_model):
                try:
                    kwargs: dict[str, Any] = {
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "model": model,
                        "temperature": 0.0,
                        "response_format": {"type": "json_object"},
                        "timeout": self.timeout,
                    }

                    response = await self.client.chat.completions.create(**kwargs)
                    raw_content = response.choices[0].message.content or "{}"
                    clean_content = strip_think_blocks(raw_content)

                    parsed_data = schema.model_validate_json(clean_content)
                    return parsed_data, model

                except (
                    OpenAIBadRequestError,
                    OpenAIAuthenticationError,
                    OpenAIPermissionDeniedError,
                    OpenAINotFoundError,
                ) as err:
                    err_str = str(err)
                    warnings.append(
                        f"Model {model} non-retryable error ({err_str}). Moving to next model."
                    )
                    break

                except OpenAIAPIStatusError as err:
                    if err.status_code in [400, 401, 403, 404]:
                        warnings.append(
                            f"Model {model} non-retryable HTTP {err.status_code}. Moving to next model."
                        )
                        break
                    err_str = str(err)
                    warnings.append(f"Attempt {attempt + 1} on model {model} failed: {err_str}")
                    if attempt < self.max_retries_per_model - 1:
                        await asyncio.sleep((2 ** attempt) + random.uniform(0.1, 0.5))

                except Exception as exc:
                    err_str = str(exc)
                    warnings.append(f"Attempt {attempt + 1} on model {model} failed: {err_str}")

                    if attempt < self.max_retries_per_model - 1:
                        sleep_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                        await asyncio.sleep(sleep_time)

            if model_idx == 0:
                warnings.append(
                    f"Primary model {self.primary_model} failed/exhausted. Falling back to {self.fallback_model}."
                )

        raise RuntimeError(
            f"Both primary ({self.primary_model}) and fallback ({self.fallback_model}) models failed. Warnings: {warnings}"
        )

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: str = "You are an incident response agent. Output strictly valid JSON matching the requested schema.",
        temperature: float = 0.0,
    ) -> LLMResult:
        parsed_data, model_used = await self.complete_json(
            system=system_prompt,
            user=prompt,
            schema=response_model,
        )
        return LLMResult(data=parsed_data, model_used=model_used, warnings=[])


# Aliases for backwards compatibility
GroqLLMClient = GroqProvider


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    name = (provider_name or os.environ.get("LLM_PROVIDER", "groq")).lower().strip()
    if name == "groq":
        return GroqProvider()
    elif name == "openai":
        return OpenAIProvider()
    else:
        raise ValueError(
            f"Unrecognized LLM_PROVIDER '{name}'. Supported providers are 'groq' and 'openai'."
        )
