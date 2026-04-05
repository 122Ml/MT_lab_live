import asyncio

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import Settings
from app.services.base import BaseEngine, TranslationOutput


class LlmApiEngine(BaseEngine):
    name = "llm_api"

    def __init__(self, settings: Settings) -> None:
        self.model = settings.openai_model
        self.timeout_seconds = settings.openai_timeout_seconds
        self.max_tokens = settings.openai_max_tokens
        self.retries = max(0, settings.openai_retries)
        self.retry_backoff_seconds = max(0.0, settings.openai_retry_backoff_seconds)
        if settings.openai_base_url and settings.openai_api_key:
            self.client: AsyncOpenAI | None = AsyncOpenAI(
                base_url=settings.openai_base_url,
                api_key=settings.openai_api_key,
                timeout=settings.openai_timeout_seconds,
            )
        else:
            self.client = None

    def status(self) -> tuple[bool, str]:
        if self.client is None:
            return False, "missing OPENAI_BASE_URL or OPENAI_API_KEY"
        return True, f"ready: {self.model}"

    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> TranslationOutput:
        if self.client is None:
            return TranslationOutput(
                text=f"[LLM API not configured] {text}",
                ready=False,
                error="Set OPENAI_BASE_URL and OPENAI_API_KEY in backend .env",
            )

        response = None
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    max_tokens=self.max_tokens,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a translation engine. Return only the translated text.",
                        },
                        {
                            "role": "user",
                            "content": f"Translate from {src_lang} to {tgt_lang}:\n{text}",
                        },
                    ],
                )
                break
            except (RateLimitError, APITimeoutError, APIConnectionError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                backoff = self.retry_backoff_seconds * (2**attempt)
                if backoff > 0:
                    await asyncio.sleep(backoff)
            except Exception as exc:
                return TranslationOutput(text=text, ready=False, error=str(exc))

        if response is None:
            return TranslationOutput(text=text, ready=False, error=str(last_error or "LLM API failed"))

        translated = response.choices[0].message.content or ""
        return TranslationOutput(text=translated.strip())
