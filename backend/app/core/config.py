from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="MT-Lab Live API", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    hf_local_files_only: bool = Field(default=True, alias="HF_LOCAL_FILES_ONLY")
    model_cache_dir: str | None = Field(default=None, alias="MODEL_CACHE_DIR")

    nmt_enabled: bool = Field(default=True, alias="NMT_ENABLED")
    nmt_model_zh_en: str = Field(default="Helsinki-NLP/opus-mt-zh-en", alias="NMT_MODEL_ZH_EN")
    nmt_model_en_zh: str = Field(default="Helsinki-NLP/opus-mt-en-zh", alias="NMT_MODEL_EN_ZH")

    smt_enabled: bool = Field(default=True, alias="SMT_ENABLED")
    smt_mode: str = Field(default="local", alias="SMT_MODE")
    smt_moses_root: str | None = Field(default=None, alias="SMT_MOSES_ROOT")
    smt_moses_bin: str | None = Field(default=None, alias="SMT_MOSES_BIN")
    smt_model_dir: str = Field(default="./smt_model", alias="SMT_MODEL_DIR")
    smt_docker_image: str = Field(default="moses-smt:latest", alias="SMT_DOCKER_IMAGE")
    smt_timeout_seconds: int = Field(default=60, alias="SMT_TIMEOUT_SECONDS")

    transformer_enabled: bool = Field(default=False, alias="TRANSFORMER_ENABLED")
    transformer_model: str = Field(default="facebook/nllb-200-distilled-600M", alias="TRANSFORMER_MODEL")

    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_timeout_seconds: int = Field(default=45, alias="OPENAI_TIMEOUT_SECONDS")
    openai_max_tokens: int = Field(default=512, alias="OPENAI_MAX_TOKENS")
    openai_retries: int = Field(default=2, alias="OPENAI_RETRIES")
    openai_retry_backoff_seconds: float = Field(default=1.0, alias="OPENAI_RETRY_BACKOFF_SECONDS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
