import asyncio
from time import perf_counter

from app.core.config import Settings
from app.schemas.translation import EngineName, EngineResult
from app.services.base import BaseEngine
from app.services.llm_api_engine import LlmApiEngine
from app.services.nmt_engine import NmtEngine
from app.services.rbmt_engine import RbmtEngine
from app.services.smt_engine import SmtEngine
from app.services.transformer_engine import TransformerEngine


class EngineManager:
    def __init__(self, settings: Settings) -> None:
        self.engines: dict[EngineName, BaseEngine] = {
            "rbmt": RbmtEngine(),
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
            )

        tasks = [run_single(name) for name in selected if name in self.engines]
        if not tasks:
            return []
        return await asyncio.gather(*tasks)
