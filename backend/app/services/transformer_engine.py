import asyncio
from pathlib import Path

from app.core.config import Settings
from app.services.base import BaseEngine, TranslationOutput


class TransformerEngine(BaseEngine):
    name = "transformer"

    def __init__(self, settings: Settings) -> None:
        self.base_dir = Path(__file__).resolve().parents[2]
        self.enabled = settings.transformer_enabled
        self.model_name = settings.transformer_model
        self.local_files_only = settings.hf_local_files_only
        self.cache_dir = settings.model_cache_dir
        self._model = None
        self._tokenizer = None
        self._load_error: str | None = None
        self._lock = asyncio.Lock()

    def status(self) -> tuple[bool, str]:
        if not self.enabled:
            return False, "Transformer engine disabled by config"
        if self.local_files_only and not self._is_local_model_dir(self.model_name):
            return False, "local transformer model path is not set"
        if self._load_error:
            return False, self._load_error
        if self._model is not None and self._tokenizer is not None:
            return True, f"loaded: {self.model_name}"
        mode = "local-only" if self.local_files_only else "allow-download"
        return True, f"ready (lazy load, mode={mode})"

    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> TranslationOutput:
        if not self.enabled:
            return TranslationOutput(text=text, ready=False, error="Transformer engine disabled by config")
        if self.local_files_only and not self._is_local_model_dir(self.model_name):
            return TranslationOutput(
                text=text,
                ready=False,
                error="Transformer local model path is not ready. Set TRANSFORMER_MODEL to local folder path.",
            )

        lang_map = {
            "zh": "zho_Hans",
            "en": "eng_Latn",
        }
        src_code = lang_map.get(src_lang)
        tgt_code = lang_map.get(tgt_lang)
        if src_code is None or tgt_code is None:
            return TranslationOutput(
                text=text,
                ready=False,
                error=f"Transformer unsupported language pair: {src_lang}->{tgt_lang}",
            )

        loaded = await self._ensure_loaded()
        if not loaded:
            return TranslationOutput(text=text, ready=False, error=self._load_error or "Transformer load failed")

        try:
            translated = await asyncio.to_thread(self._infer, text, src_code, tgt_code)
            return TranslationOutput(text=translated)
        except Exception as exc:
            return TranslationOutput(text=text, ready=False, error=f"Transformer inference failed: {exc}")

    async def _ensure_loaded(self) -> bool:
        if self._model is not None and self._tokenizer is not None:
            return True
        if self._load_error:
            return False

        async with self._lock:
            if self._model is not None and self._tokenizer is not None:
                return True
            if self._load_error:
                return False

            def load_model() -> tuple[object, object]:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

                model_ref = self._resolve_model_ref(self.model_name)

                tokenizer = AutoTokenizer.from_pretrained(
                    model_ref,
                    local_files_only=self.local_files_only,
                    cache_dir=self.cache_dir,
                )
                model = AutoModelForSeq2SeqLM.from_pretrained(
                    model_ref,
                    local_files_only=self.local_files_only,
                    cache_dir=self.cache_dir,
                )
                return model, tokenizer

            try:
                model, tokenizer = await asyncio.to_thread(load_model)
            except Exception as exc:
                hint = " (please download model files manually first)" if self.local_files_only else ""
                self._load_error = f"Transformer load failed for {self.model_name}: {exc}{hint}"
                return False

            self._model = model
            self._tokenizer = tokenizer
            return True

    def _infer(self, text: str, src_code: str, tgt_code: str) -> str:
        tokenizer = self._tokenizer
        model = self._model
        if tokenizer is None or model is None:
            raise RuntimeError("model is not loaded")

        tokenizer.src_lang = src_code
        encoded = tokenizer(text, return_tensors="pt", truncation=True)
        generated = model.generate(
            **encoded,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_code),
            max_new_tokens=256,
        )
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        return decoded[0].strip() if decoded else text

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
            return str(path)
        return str((self.base_dir / path).resolve())
