from typing import Literal

from pydantic import BaseModel, Field


EngineName = Literal["rbmt", "smt", "nmt", "transformer", "llm_api"]


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
