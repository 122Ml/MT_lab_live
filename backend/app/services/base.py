from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranslationOutput:
    text: str
    ready: bool = True
    error: str | None = None


class BaseEngine(ABC):
    name: str

    def status(self) -> tuple[bool, str]:
        return True, "ok"

    @abstractmethod
    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> TranslationOutput:
        raise NotImplementedError
