from app.services.base import BaseEngine, TranslationOutput


class RbmtEngine(BaseEngine):
    name = "rbmt"

    def __init__(self) -> None:
        self.dictionary = {
            "我也是醉了": "I'm speechless.",
            "这个问题有点难搞": "This problem is a bit tricky.",
            "捡了芝麻丢西瓜": "Penny wise, pound foolish.",
        }

    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> TranslationOutput:
        if src_lang == "zh" and tgt_lang == "en":
            normalized = self._normalize_zh(text)
            translated = self.dictionary.get(normalized) or self.dictionary.get(text)
            if translated:
                return TranslationOutput(text=translated)
        return TranslationOutput(text=f"[RBMT fallback] {text}")

    @staticmethod
    def _normalize_zh(text: str) -> str:
        normalized = text.strip()
        punctuation = "。！？!?,，；;：:、"
        while normalized and normalized[-1] in punctuation:
            normalized = normalized[:-1]
        return normalized.strip()
