from typing import Literal

from pydantic import BaseModel, Field


EngineName = Literal["rbmt", "smt", "nmt", "transformer", "llm_api"]
InputModality = Literal["text", "image", "audio", "video"]


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    src_lang: str = Field(default="zh")
    tgt_lang: str = Field(default="en")
    engines: list[EngineName] = Field(default_factory=lambda: ["rbmt", "nmt", "transformer", "llm_api"])
    reference: str | None = Field(default=None)


class BatchTranslateRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=50)
    src_lang: str = Field(default="zh")
    tgt_lang: str = Field(default="en")
    engines: list[EngineName] = Field(default_factory=lambda: ["rbmt", "nmt", "transformer", "llm_api"])
    references: list[str] | None = Field(default=None)


class EvaluateRequest(BaseModel):
    candidate: str = Field(min_length=1)
    reference: str = Field(min_length=1)


class EngineResult(BaseModel):
    engine: EngineName
    translation: str
    latency_ms: float
    ready: bool = True
    error: str | None = None
    bleu: float | None = None
    chrf: float | None = None
    meta: dict[str, str | int | float | bool | None] | None = None


class TranslateResponse(BaseModel):
    text: str
    src_lang: str
    tgt_lang: str
    reference: str | None = None
    results: list[EngineResult]


class EvaluateResponse(BaseModel):
    bleu: float
    chrf: float


class TestCaseItem(BaseModel):
    id: str
    source: str
    reference: str
    src_lang: str
    tgt_lang: str


class LlmSettings(BaseModel):
    text_model: str
    image_model: str
    audio_model: str
    video_model: str
    text_prompt: str
    image_prompt: str
    audio_prompt: str
    video_prompt: str
    media_max_base64_chars: int


class LlmSettingsUpdate(BaseModel):
    text_model: str | None = None
    image_model: str | None = None
    audio_model: str | None = None
    video_model: str | None = None
    text_prompt: str | None = None
    image_prompt: str | None = None
    audio_prompt: str | None = None
    video_prompt: str | None = None
    media_max_base64_chars: int | None = Field(default=None, ge=1024, le=20_000_000)


class LlmMultimodalRequest(BaseModel):
    modality: InputModality = Field(default="text")
    text: str | None = Field(default=None, max_length=8000)
    src_lang: str = Field(default="zh")
    tgt_lang: str = Field(default="en")
    prompt: str | None = Field(default=None, max_length=2000)
    media_base64: str | None = Field(default=None)
    media_mime_type: str | None = Field(default=None, max_length=100)
    media_url: str | None = Field(default=None, max_length=2000)


class LlmMultimodalResponse(BaseModel):
    modality: InputModality
    result: EngineResult
