import asyncio
import os
import random
from typing import Any, Type, TypeVar

from groq import AsyncGroq
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMResult(BaseModel):
    data: Any
    model_used: str
    warnings: list[str] = []


class GroqLLMClient:
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

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: str = "You are an incident response agent. Output strictly valid JSON matching the requested schema.",
        temperature: float = 0.0,
    ) -> LLMResult:
        if not self.client:
            raise RuntimeError("Groq API key not configured")

        models_to_try = [self.primary_model, self.fallback_model]
        warnings: list[str] = []

        for model_idx, model in enumerate(models_to_try):
            for attempt in range(self.max_retries_per_model):
                try:
                    # Request JSON mode response
                    response = await self.client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        model=model,
                        temperature=temperature,
                        response_format={"type": "json_object"},
                        timeout=self.timeout,
                    )

                    content = response.choices[0].message.content or "{}"

                    # Validate JSON with Pydantic
                    parsed_data = response_model.model_validate_json(content)
                    return LLMResult(data=parsed_data, model_used=model, warnings=warnings)

                except Exception as exc:
                    err_str = str(exc)
                    msg = f"Attempt {attempt + 1} on model {model} failed: {err_str}"
                    warnings.append(msg)

                    # Backoff exponential delay with jitter
                    if attempt < self.max_retries_per_model - 1:
                        sleep_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                        await asyncio.sleep(sleep_time)

            if model_idx == 0:
                warnings.append(
                    f"Primary model {self.primary_model} exhausted all retries. Falling back to {self.fallback_model}."
                )

        raise RuntimeError(f"Both primary ({self.primary_model}) and fallback ({self.fallback_model}) models failed. Warnings: {warnings}")
