#!/usr/bin/env python3
import asyncio
import os
import sys
from pathlib import Path

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, Field

from backend.app.llm.client import GroqLLMClient


class SmokeSchema(BaseModel):
    status: str
    message: str
    confidence: float = Field(ge=0.0, le=1.0)


async def main():
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("ERROR: GROQ_API_KEY environment variable is missing.", file=sys.stderr)
        sys.exit(1)

    primary_model = os.environ.get("GROQ_PRIMARY_MODEL", "openai/gpt-oss-120b")
    fallback_model = os.environ.get("GROQ_FALLBACK_MODEL", "qwen/qwen3-32b")

    print("Testing Groq LLM Client...")
    print(f"Primary model: {primary_model}")
    print(f"Fallback model: {fallback_model}\n")

    client = GroqLLMClient(
        api_key=api_key,
        primary_model=primary_model,
        fallback_model=fallback_model,
        timeout=15.0,
    )

    prompt = "Generate a trivial status report in JSON format indicating system operation is healthy."

    # 1. Test Primary Model
    print("--- 1. Testing Primary Model ---")
    try:
        res1 = await client.generate_structured(
            prompt=prompt,
            response_model=SmokeSchema,
        )
        print("Primary model succeeded!")
        print(f"Model used: {res1.model_used}")
        print(f"Parsed data: {res1.data}")
        if res1.warnings:
            print(f"Warnings: {res1.warnings}")
    except Exception as exc:
        print(f"Primary model call failed: {exc}", file=sys.stderr)

    # 2. Test Fallback Model Directly
    print("\n--- 2. Testing Fallback Model Directly ---")
    fallback_client = GroqLLMClient(
        api_key=api_key,
        primary_model=fallback_model,
        fallback_model=fallback_model,
        timeout=15.0,
    )
    try:
        res2 = await fallback_client.generate_structured(
            prompt=prompt,
            response_model=SmokeSchema,
        )
        print("Fallback model succeeded!")
        print(f"Model used: {res2.model_used}")
        print(f"Parsed data: {res2.data}")
        if res2.warnings:
            print(f"Warnings: {res2.warnings}")
    except Exception as exc:
        print(f"Fallback model call failed: {exc}", file=sys.stderr)

    print("\nLLM Smoke Test completed.")


if __name__ == "__main__":
    asyncio.run(main())
