# Provider-Agnostic LLM Layer

Recall supports multiple LLM providers behind a provider-agnostic `LLMProvider` interface.

## Supported Providers

1. **Groq (`LLM_PROVIDER=groq`)** [Default]
   - Uses official `groq` Python SDK.
   - Primary Model: `openai/gpt-oss-120b`
   - Fallback Model: `qwen/qwen3-32b`
   - Recommended for fast inference and generous free tier usage.

2. **OpenAI (`LLM_PROVIDER=openai`)**
   - Uses official `openai` Python SDK (`AsyncOpenAI`).
   - Primary Model: `gpt-4o-mini`
   - Fallback Model: `gpt-4.1-mini`
   - Uses structured JSON mode output validation.

## Switching Providers

Set the `LLM_PROVIDER` environment variable in `.env`:

```bash
# Switch to OpenAI provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_PRIMARY_MODEL=gpt-4o-mini
OPENAI_FALLBACK_MODEL=gpt-4.1-mini
```

## Provider Resilience & Fallback Behavior

Both `GroqProvider` and `OpenAIProvider` implement:
1. **Exponential Backoff Retries:** 3 attempts per model with jitter on transient network/rate limit errors.
2. **Non-Retryable Short-Circuit:** HTTP 400, 401, 403, and 404 errors immediately bypass retries and switch to the fallback model.
3. **Degraded Memory Response:** If both primary and fallback models fail for the selected provider, Recall gracefully degrades to assemble suggestions directly from recalled memories.
