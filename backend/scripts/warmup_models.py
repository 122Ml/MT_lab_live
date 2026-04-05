import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings


def warmup_nmt() -> None:
    settings = get_settings()
    model_names = [settings.nmt_model_zh_en, settings.nmt_model_en_zh]

    try:
        from transformers import pipeline
    except Exception as exc:
        raise SystemExit(f"transformers is not installed: {exc}")

    for model_name in model_names:
        print(f"[warmup] downloading/loading {model_name} ...")
        translator = pipeline(
            task="translation",
            model=model_name,
            tokenizer=model_name,
            local_files_only=settings.hf_local_files_only,
            cache_dir=settings.model_cache_dir,
        )
        sample = translator("This is a warmup sentence.", max_length=128)
        print(f"[warmup] ok -> {sample[0].get('translation_text', '')[:60]}")


if __name__ == "__main__":
    warmup_nmt()
