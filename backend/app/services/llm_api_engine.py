import asyncio
import base64
import json
import re
from dataclasses import asdict, dataclass
from time import perf_counter

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import Settings
from app.services.base import BaseEngine, TranslationOutput


@dataclass
class LlmRuntimeSettings:
    text_model: str
    image_model: str
    audio_model: str
    video_model: str
    text_prompt: str
    image_prompt: str
    audio_prompt: str
    video_prompt: str
    media_max_base64_chars: int


class LlmApiEngine(BaseEngine):
    name = "llm_api"

    def __init__(self, settings: Settings) -> None:
        self.model = settings.openai_model
        self.timeout_seconds = settings.openai_timeout_seconds
        self.max_tokens = settings.openai_max_tokens
        self.retries = max(0, settings.openai_retries)
        self.retry_backoff_seconds = max(0.0, settings.openai_retry_backoff_seconds)
        self.runtime_settings = LlmRuntimeSettings(
            text_model=settings.openai_model,
            image_model=settings.openai_image_model or settings.openai_model,
            audio_model=settings.openai_audio_model or settings.openai_model,
            video_model=settings.openai_video_model or settings.openai_model,
            text_prompt=settings.openai_text_prompt,
            image_prompt=settings.openai_image_prompt,
            audio_prompt=settings.openai_audio_prompt,
            video_prompt=settings.openai_video_prompt,
            media_max_base64_chars=settings.openai_media_max_base64_chars,
        )
        if settings.openai_base_url and settings.openai_api_key:
            self.client: AsyncOpenAI | None = AsyncOpenAI(
                base_url=settings.openai_base_url,
                api_key=settings.openai_api_key,
                timeout=settings.openai_timeout_seconds,
            )
        else:
            self.client = None
        self.output_contract = (
            "Output contract: return only the final translated text in target language. "
            "No labels, no explanation, no markdown, no JSON, no extra symbols."
        )

    def status(self) -> tuple[bool, str]:
        if self.client is None:
            return False, "missing OPENAI_BASE_URL or OPENAI_API_KEY"
        return True, f"ready: text={self.runtime_settings.text_model}"

    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> TranslationOutput:
        return await self.process_multimodal(
            modality="text",
            text=text,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            prompt=None,
            media_base64=None,
            media_mime_type=None,
            media_url=None,
        )

    def get_runtime_settings(self) -> dict[str, str | int]:
        return asdict(self.runtime_settings)

    def update_runtime_settings(self, payload: dict[str, str | int | None]) -> dict[str, str | int]:
        for key, value in payload.items():
            if value is None:
                continue
            if key == "media_max_base64_chars":
                numeric = int(value)
                self.runtime_settings.media_max_base64_chars = max(1024, min(20_000_000, numeric))
                continue
            if hasattr(self.runtime_settings, key):
                setattr(self.runtime_settings, key, str(value))
        return asdict(self.runtime_settings)

    async def process_multimodal(
        self,
        modality: str,
        text: str | None,
        src_lang: str,
        tgt_lang: str,
        prompt: str | None,
        media_base64: str | None,
        media_mime_type: str | None,
        media_url: str | None,
    ) -> TranslationOutput:
        if self.client is None:
            return TranslationOutput(
                text=f"[LLM API not configured] {text or ''}".strip(),
                ready=False,
                error="Set OPENAI_BASE_URL and OPENAI_API_KEY in backend .env",
            )

        prepared = self._build_messages(
            modality=modality,
            text=text,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            prompt=prompt,
            media_base64=media_base64,
            media_mime_type=media_mime_type,
            media_url=media_url,
        )
        if isinstance(prepared, str):
            return TranslationOutput(text=text or "", ready=False, error=prepared)

        model_name, messages = prepared
        response = None
        last_error: Exception | None = None
        started = perf_counter()
        for attempt in range(self.retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=model_name,
                    temperature=0,
                    max_tokens=self.max_tokens,
                    messages=messages,
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
                return TranslationOutput(text=text or "", ready=False, error=str(exc))

        if response is None:
            return TranslationOutput(text=text or "", ready=False, error=str(last_error or "LLM API failed"))

        translated = response.choices[0].message.content or ""
        translated = self._postprocess_output(translated)
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return TranslationOutput(
            text=translated.strip(),
            meta={
                "modality": modality,
                "model": model_name,
                "latency_ms": elapsed_ms,
            },
        )

    def _build_messages(
        self,
        modality: str,
        text: str | None,
        src_lang: str,
        tgt_lang: str,
        prompt: str | None,
        media_base64: str | None,
        media_mime_type: str | None,
        media_url: str | None,
    ) -> tuple[str, list[dict[str, object]]] | str:
        modality_key = modality.lower()
        settings = self.runtime_settings

        if modality_key == "text":
            input_text = (text or "").strip()
            if not input_text:
                return "text modality requires non-empty text"
            user_prompt = (
                prompt.strip()
                if prompt and prompt.strip()
                else f"Translate from {src_lang} to {tgt_lang}:\n{input_text}"
            )
            return settings.text_model, [
                {
                    "role": "system",
                    "content": self._compose_system_prompt(settings.text_prompt, src_lang, tgt_lang),
                },
                {"role": "user", "content": user_prompt},
            ]

        if modality_key not in {"image", "audio", "video"}:
            return f"unsupported modality: {modality_key}"

        if media_base64 and len(media_base64) > settings.media_max_base64_chars:
            return (
                f"media_base64 too large ({len(media_base64)} chars), "
                f"limit={settings.media_max_base64_chars}"
            )

        default_prompt_map = {
            "image": settings.image_prompt,
            "audio": settings.audio_prompt,
            "video": settings.video_prompt,
        }
        model_map = {
            "image": settings.image_model,
            "audio": settings.audio_model,
            "video": settings.video_model,
        }
        default_prompt = default_prompt_map[modality_key]
        model_name = model_map[modality_key]
        final_prompt = (prompt or "").strip() or default_prompt

        if modality_key == "image":
            content_parts: list[dict[str, object]] = [{"type": "text", "text": final_prompt}]
            if media_url:
                content_parts.append({"type": "image_url", "image_url": {"url": media_url}})
            elif media_base64:
                mime = (media_mime_type or "image/png").strip()
                try:
                    _ = base64.b64decode(media_base64, validate=True)
                except Exception:
                    return "image media_base64 is not valid base64"
                content_parts.append(
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{media_base64}"}}
                )
            else:
                return "image modality requires media_url or media_base64"
            return model_name, [
                {
                    "role": "system",
                    "content": self._compose_system_prompt(default_prompt, src_lang, tgt_lang),
                },
                {"role": "user", "content": content_parts},
            ]

        # audio / video: keep OpenAI-compatible chat.completions shape by placing media pointer in text.
        media_pointer = media_url
        if not media_pointer and media_base64:
            media_pointer = f"base64://{modality_key}({len(media_base64)} chars)"
        if not media_pointer:
            return f"{modality_key} modality requires media_url or media_base64"

        text_input = (text or "").strip()
        body = (
            f"{final_prompt}\n\n"
            f"Source language: {src_lang}\n"
            f"Target language: {tgt_lang}\n"
            f"{modality_key.capitalize()} reference: {media_pointer}\n"
        )
        if text_input:
            body += f"\nAdditional text context:\n{text_input}\n"

        return model_name, [
            {
                "role": "system",
                "content": self._compose_system_prompt(default_prompt, src_lang, tgt_lang),
            },
            {"role": "user", "content": body},
        ]

    def _compose_system_prompt(self, base_prompt: str, src_lang: str, tgt_lang: str) -> str:
        base = (base_prompt or "").strip()
        lines = [
            "You are a translation engine.",
            f"Source language is {src_lang}.",
            f"Target language is {tgt_lang}.",
            self.output_contract,
        ]
        if base:
            lines.append(f"Task hint: {base}")
        return "\n".join(lines)

    def _postprocess_output(self, text: str) -> str:
        value = (text or "").strip()
        if not value:
            return value

        if value.startswith("```") and value.endswith("```"):
            value = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", value)
            value = re.sub(r"\n?```$", "", value).strip()

        if value.startswith("{") and value.endswith("}"):
            try:
                data = json.loads(value)
                if isinstance(data, dict):
                    for key in ("translation", "translated_text", "target_text", "output"):
                        candidate = data.get(key)
                        if isinstance(candidate, str) and candidate.strip():
                            value = candidate.strip()
                            break
            except Exception:
                pass

        value = re.sub(
            r"^(translation|translated text|translated|译文|翻译)\s*[:：]\s*",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1].strip()

        return value
