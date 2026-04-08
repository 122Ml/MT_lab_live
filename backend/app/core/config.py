from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="MT-Lab Live API", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    warmup_on_start: bool = Field(default=True, alias="WARMUP_ON_START")
    warmup_text: str = Field(default="Warmup sentence for model preload.", alias="WARMUP_TEXT")
    warmup_src_lang: str = Field(default="zh", alias="WARMUP_SRC_LANG")
    warmup_tgt_lang: str = Field(default="en", alias="WARMUP_TGT_LANG")
    rbmt_use_cedict: bool = Field(default=True, alias="RBMT_USE_CEDICT")
    rbmt_cedict_path: str | None = Field(default=None, alias="RBMT_CEDICT_PATH")
    rbmt_cedict_max_entries: int = Field(default=300000, alias="RBMT_CEDICT_MAX_ENTRIES")
    rbmt_en_zh_tmx_path: str | None = Field(default="./data/ebmt/en-zh.tmx", alias="RBMT_EN_ZH_TMX_PATH")
    rbmt_tmx_max_entries: int = Field(default=200000, alias="RBMT_TMX_MAX_ENTRIES")

    hf_local_files_only: bool = Field(default=True, alias="HF_LOCAL_FILES_ONLY")
    model_cache_dir: str | None = Field(default=None, alias="MODEL_CACHE_DIR")

    nmt_enabled: bool = Field(default=True, alias="NMT_ENABLED")
    nmt_model_zh_en: str = Field(default="Helsinki-NLP/opus-mt-zh-en", alias="NMT_MODEL_ZH_EN")
    nmt_model_en_zh: str = Field(default="Helsinki-NLP/opus-mt-en-zh", alias="NMT_MODEL_EN_ZH")
    nmt_en_zh_rules_path: str = Field(default="./data/nmt_en_zh_rules.tsv", alias="NMT_EN_ZH_RULES_PATH")

    smt_enabled: bool = Field(default=True, alias="SMT_ENABLED")
    smt_mode: str = Field(default="auto", alias="SMT_MODE")
    smt_moses_root: str | None = Field(default=None, alias="SMT_MOSES_ROOT")
    smt_moses_bin: str | None = Field(default=None, alias="SMT_MOSES_BIN")
    smt_niutrans_root: str | None = Field(default="../tools/NiuTrans.SMT", alias="SMT_NIUTRANS_ROOT")
    smt_niutrans_bin: str | None = Field(default="", alias="SMT_NIUTRANS_BIN")
    smt_niutrans_config: str | None = Field(
        default="../tools/NiuTrans.SMT/config/NiuTrans.phrase.config",
        alias="SMT_NIUTRANS_CONFIG",
    )
    smt_model_dir: str = Field(default="./smt_model", alias="SMT_MODEL_DIR")
    smt_docker_image: str = Field(default="moses-smt:latest", alias="SMT_DOCKER_IMAGE")
    smt_timeout_seconds: int = Field(default=60, alias="SMT_TIMEOUT_SECONDS")
    smt_lite_model_path: str = Field(default="./smt_model/lite_phrase_table.json", alias="SMT_LITE_MODEL_PATH")
    smt_lite_seed_path: str = Field(default="./data/smt_lite_seed.tsv", alias="SMT_LITE_SEED_PATH")
    smt_lite_max_cedict_entries: int = Field(default=120000, alias="SMT_LITE_MAX_CEDICT_ENTRIES")

    transformer_enabled: bool = Field(default=False, alias="TRANSFORMER_ENABLED")
    transformer_model: str = Field(default="facebook/nllb-200-distilled-600M", alias="TRANSFORMER_MODEL")

    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_image_model: str | None = Field(default=None, alias="OPENAI_IMAGE_MODEL")
    openai_audio_model: str | None = Field(default=None, alias="OPENAI_AUDIO_MODEL")
    openai_video_model: str | None = Field(default=None, alias="OPENAI_VIDEO_MODEL")
    openai_text_prompt: str = Field(
        default="You are a translation engine. Return only the translated text.",
        alias="OPENAI_TEXT_PROMPT",
    )
    openai_image_prompt: str = Field(
        default="Describe the image briefly and provide a concise translation in target language.",
        alias="OPENAI_IMAGE_PROMPT",
    )
    openai_audio_prompt: str = Field(
        default="Transcribe and translate the provided audio into target language.",
        alias="OPENAI_AUDIO_PROMPT",
    )
    openai_video_prompt: str = Field(
        default="Summarize and translate the key information from the provided video into target language.",
        alias="OPENAI_VIDEO_PROMPT",
    )
    openai_media_max_base64_chars: int = Field(default=2_000_000, alias="OPENAI_MEDIA_MAX_BASE64_CHARS")
    openai_timeout_seconds: int = Field(default=45, alias="OPENAI_TIMEOUT_SECONDS")
    openai_max_tokens: int = Field(default=512, alias="OPENAI_MAX_TOKENS")
    openai_retries: int = Field(default=2, alias="OPENAI_RETRIES")
    openai_retry_backoff_seconds: float = Field(default=1.0, alias="OPENAI_RETRY_BACKOFF_SECONDS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
