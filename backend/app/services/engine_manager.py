import asyncio
import logging
from time import perf_counter

from app.core.config import Settings
from app.schemas.translation import EngineName, EngineResult
from app.services.base import BaseEngine
from app.services.llm_api_engine import LlmApiEngine
from app.services.nmt_engine import NmtEngine
from app.services.rbmt_engine import RbmtEngine
from app.services.smt_engine import SmtEngine
from app.services.transformer_engine import TransformerEngine

logger = logging.getLogger(__name__)


class EngineManager:
    def __init__(self, settings: Settings) -> None:
        self.engines: dict[EngineName, BaseEngine] = {
            "rbmt": RbmtEngine(settings),
            "smt": SmtEngine(settings),
            "nmt": NmtEngine(settings),
            "transformer": TransformerEngine(settings),
            "llm_api": LlmApiEngine(settings),
        }

    def status(self) -> dict[str, dict[str, str | bool]]:
        output: dict[str, dict[str, str | bool]] = {}
        for name, engine in self.engines.items():
            ready, message = engine.status()
            output[name] = {"ready": ready, "message": message}
        return output

    async def translate_with_selected(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        selected: list[EngineName],
    ) -> list[EngineResult]:
        async def run_single(engine_name: EngineName) -> EngineResult:
            engine = self.engines[engine_name]
            start = perf_counter()
            result = await engine.translate(text=text, src_lang=src_lang, tgt_lang=tgt_lang)
            elapsed_ms = (perf_counter() - start) * 1000
            return EngineResult(
                engine=engine_name,
                translation=result.text,
                latency_ms=round(elapsed_ms, 2),
                ready=result.ready,
                error=result.error,
                meta=result.meta,
            )

        tasks = [run_single(name) for name in selected if name in self.engines]
        if not tasks:
            return []
        return await asyncio.gather(*tasks)

    async def warmup(self, text: str, src_lang: str, tgt_lang: str) -> None:
        warmup_targets: list[EngineName] = ["nmt", "transformer"]

        async def run_warmup(engine_name: EngineName) -> None:
            engine = self.engines.get(engine_name)
            if engine is None:
                return

            ready, message = engine.status()
            if not ready:
                logger.info("warmup skip %s: %s", engine_name, message)
                return

            started = perf_counter()
            try:
                output = await engine.translate(text=text, src_lang=src_lang, tgt_lang=tgt_lang)
                elapsed_ms = (perf_counter() - started) * 1000
                logger.info(
                    "warmup done %s: ready=%s, latency=%.2fms",
                    engine_name,
                    output.ready,
                    elapsed_ms,
                )
            except Exception as exc:
                logger.exception("warmup failed %s: %s", engine_name, exc)

        for engine_name in warmup_targets:
            await run_warmup(engine_name)

    def get_llm_settings(self) -> dict[str, str | int]:
        engine = self.engines["llm_api"]
        assert isinstance(engine, LlmApiEngine)
        return engine.get_runtime_settings()

    def update_llm_settings(self, payload: dict[str, str | int | None]) -> dict[str, str | int]:
        engine = self.engines["llm_api"]
        assert isinstance(engine, LlmApiEngine)
        return engine.update_runtime_settings(payload)

    async def run_llm_multimodal(
        self,
        modality: str,
        text: str | None,
        src_lang: str,
        tgt_lang: str,
        prompt: str | None,
        media_base64: str | None,
        media_mime_type: str | None,
        media_url: str | None,
    ) -> EngineResult:
        engine = self.engines["llm_api"]
        assert isinstance(engine, LlmApiEngine)
        started = perf_counter()
        output = await engine.process_multimodal(
            modality=modality,
            text=text,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            prompt=prompt,
            media_base64=media_base64,
            media_mime_type=media_mime_type,
            media_url=media_url,
        )
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return EngineResult(
            engine="llm_api",
            translation=output.text,
            latency_ms=elapsed_ms,
            ready=output.ready,
            error=output.error,
            meta=output.meta,
        )
