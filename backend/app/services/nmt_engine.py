import asyncio
import re
from collections.abc import Callable
from pathlib import Path

from app.core.config import Settings
from app.services.base import BaseEngine, TranslationOutput


class NmtEngine(BaseEngine):
    name = "nmt"

    def __init__(self, settings: Settings) -> None:
        self.base_dir = Path(__file__).resolve().parents[2]
        self.enabled = settings.nmt_enabled
        self.local_files_only = settings.hf_local_files_only
        self.cache_dir = settings.model_cache_dir
        self.model_map: dict[tuple[str, str], str] = {
            ("zh", "en"): settings.nmt_model_zh_en,
            ("en", "zh"): settings.nmt_model_en_zh,
        }
        self.en_zh_rules_path = settings.nmt_en_zh_rules_path
        self.en_zh_rules = self._load_en_zh_rules(self.en_zh_rules_path)
        self._translators: dict[tuple[str, str], Callable[..., list[dict[str, str]]]] = {}
        self._load_errors: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()
        self._prefer_cuda = self._detect_cuda()

    def status(self) -> tuple[bool, str]:
        if not self.enabled:
            return False, "NMT disabled by config"
        if self.local_files_only:
            not_ready: list[str] = []
            for src_tgt, model_ref in self.model_map.items():
                if not self._is_local_model_dir(model_ref):
                    not_ready.append(f"{src_tgt[0]}->{src_tgt[1]}")
            if not_ready:
                pending = ", ".join(not_ready)
                return False, f"local model path not set for: {pending}"
        if self._load_errors:
            return False, next(iter(self._load_errors.values()))
        if self._translators:
            loaded = ", ".join([f"{src}->{tgt}" for src, tgt in self._translators])
            device = "cuda" if self._prefer_cuda else "cpu"
            return True, f"loaded: {loaded} (device={device}, en->zh_rules={len(self.en_zh_rules)})"
        mode = "local-only" if self.local_files_only else "allow-download"
        device = "cuda" if self._prefer_cuda else "cpu"
        return True, f"ready (lazy load, mode={mode}, device={device}, en->zh_rules={len(self.en_zh_rules)})"

    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> TranslationOutput:
        if not self.enabled:
            return TranslationOutput(text=text, ready=False, error="NMT disabled by config")

        pair = (src_lang, tgt_lang)
        if pair not in self.model_map:
            return TranslationOutput(
                text=text,
                ready=False,
                error=f"NMT unsupported language pair: {src_lang}->{tgt_lang}",
            )

        model_ref = self.model_map[pair]
        if self.local_files_only and not self._is_local_model_dir(model_ref):
            return TranslationOutput(
                text=text,
                ready=False,
                error=(
                    f"NMT local model path is not ready for {src_lang}->{tgt_lang}. "
                    "Set NMT_MODEL_* to local folder path."
                ),
            )

        translator = await self._get_translator(pair)
        if translator is None:
            return TranslationOutput(text=text, ready=False, error=self._load_errors.get(pair, "NMT load failed"))

        try:
            result = await asyncio.to_thread(translator, text, max_length=512)
            translated = result[0].get("translation_text", "").strip()
            if pair == ("en", "zh") and translated:
                translated = self._apply_en_zh_rules(translated)
            return TranslationOutput(text=translated or text)
        except Exception as exc:
            return TranslationOutput(text=text, ready=False, error=f"NMT inference failed: {exc}")

    async def _get_translator(self, pair: tuple[str, str]) -> Callable[..., list[dict[str, str]]] | None:
        if pair in self._translators:
            return self._translators[pair]

        async with self._lock:
            if pair in self._translators:
                return self._translators[pair]
            self._load_errors.pop(pair, None)

            model_name = self.model_map[pair]
            model_ref = self._resolve_model_ref(model_name)

            def build_pipeline(use_cuda: bool) -> Callable[..., list[dict[str, str]]]:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
                import torch

                model_kwargs: dict[str, object] = {}
                if use_cuda:
                    model_kwargs["torch_dtype"] = torch.float16

                tokenizer = AutoTokenizer.from_pretrained(
                    model_ref,
                    use_fast=False,
                    local_files_only=self.local_files_only,
                    cache_dir=self.cache_dir,
                )
                model = AutoModelForSeq2SeqLM.from_pretrained(
                    model_ref,
                    local_files_only=self.local_files_only,
                    cache_dir=self.cache_dir,
                    **model_kwargs,
                )

                return pipeline(task="translation", model=model, tokenizer=tokenizer, device=0 if use_cuda else -1)

            try:
                translator = await asyncio.to_thread(build_pipeline, self._prefer_cuda)
            except Exception as exc:
                if self._prefer_cuda:
                    try:
                        self._prefer_cuda = False
                        translator = await asyncio.to_thread(build_pipeline, False)
                        self._translators[pair] = translator
                        return translator
                    except Exception:
                        pass
                hint = ""
                if self.local_files_only:
                    hint = " (please ensure local model files and required Python deps are available)"
                self._load_errors[pair] = f"NMT load failed for {model_name}: {exc}{hint}"
                return None

            self._translators[pair] = translator
            self._load_errors.pop(pair, None)
            return translator

    @staticmethod
    def _detect_cuda() -> bool:
        try:
            import torch

            return bool(torch.cuda.is_available())
        except Exception:
            return False

    @staticmethod
    def _is_local_model_dir(model_ref: str) -> bool:
        model_path = Path(model_ref)
        if not model_path.is_absolute():
            model_path = (Path(__file__).resolve().parents[2] / model_path).resolve()
        return model_path.exists() and model_path.is_dir()

    def _resolve_model_ref(self, model_ref: str) -> str:
        if not self.local_files_only:
            return model_ref
        path = Path(model_ref)
        if path.is_absolute():
            try:
                rel = path.resolve().relative_to(self.base_dir.resolve())
                return str(Path(".") / rel).replace("\\", "/")
            except Exception:
                return str(path)
        return model_ref

    def _load_en_zh_rules(self, path_like: str | None) -> list[tuple[re.Pattern[str], str]]:
        if not path_like:
            return []
        path = Path(path_like)
        if not path.is_absolute():
            path = (self.base_dir / path).resolve()
        if not path.exists():
            return []

        rules: list[tuple[re.Pattern[str], str]] = []
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                pattern, replacement = parts[0].strip(), parts[1].strip()
                if not pattern:
                    continue
                rules.append((re.compile(pattern, flags=re.IGNORECASE), replacement))
        except Exception:
            return []

        return rules

    def _apply_en_zh_rules(self, text: str) -> str:
        translated = text
        for pattern, replacement in self.en_zh_rules:
            translated = pattern.sub(replacement, translated)

        punctuation_map = {
            ",": "，",
            ".": "。",
            "!": "！",
            "?": "？",
            ";": "；",
            ":": "：",
        }
        for key, value in punctuation_map.items():
            translated = translated.replace(key, value)

        translated = re.sub(r"\s*([，。！？；：])\s*", r"\1", translated)
        translated = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", translated)
        translated = re.sub(r"\s+", " ", translated).strip()
        return translated
