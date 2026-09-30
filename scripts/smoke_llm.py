#!/usr/bin/env python3
import asyncio
import os
import sys
from pathlib import Path

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, Field

from backend.app.llm.client import GroqProvider, OpenAIProvider, get_llm_provider


class SmokeSchema(BaseModel):
    status: str
    message: str
    confidence: float = Field(ge=0.0, le=1.0)


async def main():
    active_provider_name = os.environ.get("LLM_PROVIDER", "groq").lower()
    print(f"Active LLM Provider: {active_provider_name.upper()}\n")

    prompt = "Generate a trivial status report in JSON format indicating system operation is healthy."

    # 1. Test Groq Provider if key present
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key or active_provider_name == "groq":
        print("--- Testing Groq Provider ---")
        try:
            groq_provider = GroqProvider(api_key=groq_key)
            parsed, model = await groq_provider.complete_json(
                system="Output strictly valid JSON matching schema.",
                user=prompt,
                schema=SmokeSchema,
            )
            print("Groq Provider succeeded!")
            print(f"Model used: {model}")
            print(f"Parsed data: {parsed}\n")
        except Exception as exc:
            print(f"Groq Provider call failed: {exc}\n", file=sys.stderr)

    # 2. Test OpenAI Provider if key present
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key or active_provider_name == "openai":
        print("--- Testing OpenAI Provider ---")
        try:
            openai_provider = OpenAIProvider(api_key=openai_key)
            parsed, model = await openai_provider.complete_json(
                system="Output strictly valid JSON matching schema.",
                user=prompt,
                schema=SmokeSchema,
            )
            print("OpenAI Provider succeeded!")
            print(f"Model used: {model}")
            print(f"Parsed data: {parsed}\n")
        except Exception as exc:
            print(f"OpenAI Provider call failed: {exc}\n", file=sys.stderr)

    # 3. Test factory function
    print("--- Testing get_llm_provider() Factory ---")
    provider = get_llm_provider()
    print(f"Factory returned provider instance: {provider.__class__.__name__}")
    print(f"Primary model: {provider.primary_model} | Fallback model: {provider.fallback_model}")

    print("\nLLM Provider Smoke Test completed.")


if __name__ == "__main__":
    asyncio.run(main())
