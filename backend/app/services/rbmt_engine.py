from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

from app.core.config import Settings
from app.services.base import BaseEngine, TranslationOutput


class RbmtEngine(BaseEngine):
    name = "rbmt"

    def __init__(self, settings: Settings) -> None:
        self.base_dir = Path(__file__).resolve().parents[2]
        self.seed_dictionary: dict[str, str] = {
            "\u6211\u4e5f\u9189\u4e86": "I'm speechless.",
            "\u8fd9\u4e2a\u95ee\u9898\u6709\u70b9\u96be\u641e": "This problem is a bit tricky.",
            "\u6361\u4e86\u829d\u9ebb\u4e22\u4e86\u897f\u74dc": "Penny wise, pound foolish.",
            "\u6211\u559c\u6b22\u4eba\u5de5\u667a\u80fd\uff0c\u6211\u5bf9\u8fd9\u7247\u5927\u5730\u7231\u5f97\u6df1\u6c89": "I love artificial intelligence, and I deeply love this land.",
        }
        self.seed_reverse_dictionary: dict[str, str] = {
            "i'm speechless": "\u6211\u4e5f\u9189\u4e86",
            "this problem is a bit tricky": "\u8fd9\u4e2a\u95ee\u9898\u6709\u70b9\u96be\u641e",
            "penny wise, pound foolish": "\u6361\u4e86\u829d\u9ebb\u4e22\u4e86\u897f\u74dc",
            "i love artificial intelligence, and i deeply love this land": "\u6211\u559c\u6b22\u4eba\u5de5\u667a\u80fd\uff0c\u6211\u5bf9\u8fd9\u7247\u5927\u5730\u7231\u5f97\u6df1\u6c89",
            "he sat on the bank and watched the river flow": "\u4ed6\u5750\u5728\u6cb3\u5cb8\u4e0a\uff0c\u770b\u7740\u6cb3\u6c34\u6d41\u6dcc\u3002",
        }
        self.dictionary: dict[str, str] = dict(self.seed_dictionary)
        self.reverse_dictionary: dict[str, str] = dict(self.seed_reverse_dictionary)
        self.max_phrase_len = max((len(key) for key in self.dictionary), default=1)
        self.max_en_phrase_tokens = max((len(key.split()) for key in self.reverse_dictionary), default=1)
        self.cedict_loaded_entries = 0
        self.tmx_loaded_entries = 0
        self.cedict_error: str | None = None
        self.tmx_error: str | None = None
        self.use_cedict = settings.rbmt_use_cedict
        self.en_zh_tmx_path = self._resolve_optional_path(settings.rbmt_en_zh_tmx_path)
        self.tmx_max_entries = max(0, settings.rbmt_tmx_max_entries)

        cedict_path = self._resolve_optional_path(settings.rbmt_cedict_path)
        if self.use_cedict and cedict_path:
            try:
                self.cedict_loaded_entries = self._load_cedict(
                    cedict_path=cedict_path,
                    max_entries=max(0, settings.rbmt_cedict_max_entries),
                )
                self.max_phrase_len = max((len(key) for key in self.dictionary), default=1)
            except Exception as exc:
                self.cedict_error = f"cedict load failed: {exc}"

        if self.en_zh_tmx_path and self.en_zh_tmx_path.exists():
            try:
                self.tmx_loaded_entries = self._load_en_zh_tmx(self.en_zh_tmx_path, self.tmx_max_entries)
            except Exception as exc:
                self.tmx_error = f"tmx load failed: {exc}"

        self.max_en_phrase_tokens = max((len(key.split()) for key in self.reverse_dictionary), default=1)
        self.max_en_phrase_tokens = max(1, min(self.max_en_phrase_tokens, 12))

    def status(self) -> tuple[bool, str]:
        if self.cedict_error:
            return False, self.cedict_error
        if self.tmx_error:
            return False, self.tmx_error

        parts = [
            f"seed_zh_en={len(self.seed_dictionary)}",
            f"seed_en_zh={len(self.seed_reverse_dictionary)}",
        ]
        if self.cedict_loaded_entries > 0:
            parts.append(f"cedict={self.cedict_loaded_entries}")
        if self.tmx_loaded_entries > 0:
            parts.append(f"tmx={self.tmx_loaded_entries}")
        parts.append(f"en_zh_rules={len(self.reverse_dictionary)}")
        return True, f"ok ({', '.join(parts)})"

    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> TranslationOutput:
        if src_lang == "zh" and tgt_lang == "en":
            normalized = self._normalize_zh(text)
            direct = self.dictionary.get(normalized) or self.dictionary.get(text.strip())
            if direct:
                return TranslationOutput(text=direct, meta={"mode": "direct"})

            segmented = self._segment_translate(normalized)
            if segmented and segmented != normalized:
                return TranslationOutput(text=segmented, meta={"mode": "segmented"})

        if src_lang == "en" and tgt_lang == "zh":
            normalized_en = self._normalize_en(text)
            direct = self._lookup_en_zh(normalized_en)
            if direct:
                return TranslationOutput(text=direct, meta={"mode": "direct_en_zh"})

            segmented_en = self._segment_translate_en_zh(normalized_en)
            if segmented_en and segmented_en != normalized_en:
                return TranslationOutput(text=segmented_en, meta={"mode": "segmented_en_zh"})

        return TranslationOutput(text=f"[RBMT fallback] {text}")

    def _segment_translate(self, text: str) -> str:
        output: list[str] = []
        index = 0
        total = len(text)
        while index < total:
            token = text[index]
            if token.isspace():
                index += 1
                continue

            punctuation = self._map_punctuation(token)
            if punctuation is not None:
                output.append(punctuation)
                index += 1
                continue

            matched = False
            max_window = min(self.max_phrase_len, total - index)
            for size in range(max_window, 1, -1):
                candidate = text[index : index + size]
                translated = self.dictionary.get(candidate)
                if not translated:
                    continue
                output.append(translated.strip())
                index += size
                matched = True
                break

            if matched:
                continue

            output.append(token)
            index += 1

        return self._join_tokens(output)

    @staticmethod
    def _join_tokens(tokens: list[str]) -> str:
        if not tokens:
            return ""
        output: list[str] = []
        punctuation_tokens = {".", ",", ";", "!", "?"}
        for token in tokens:
            if not token:
                continue
            if token in punctuation_tokens and output:
                output[-1] = output[-1].rstrip() + token
            else:
                output.append(token)
        return " ".join(output).strip()

    @staticmethod
    def _normalize_zh(text: str) -> str:
        normalized = text.strip()
        punctuation = "\u3002\uff01\uff1f\uff1b\uff0c\u3001,.!?;:\uff1a"
        while normalized and normalized[-1] in punctuation:
            normalized = normalized[:-1]
        return normalized.strip()

    @staticmethod
    def _normalize_en(text: str) -> str:
        normalized = text.strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip(" \t\r\n\"'“”‘’`")
        normalized = normalized.rstrip(".,!?;:")
        return normalized.strip()

    @staticmethod
    def _map_punctuation(ch: str) -> str | None:
        mapping = {
            "\u3002": ".",
            "\uff01": "!",
            "\uff1f": "?",
            "\uff1b": ";",
            "\uff0c": ",",
            "\u3001": ",",
            ".": ".",
            "!": "!",
            "?": "?",
            ";": ";",
            ",": ",",
        }
        return mapping.get(ch)

    @staticmethod
    def _map_en_punctuation_to_zh(ch: str) -> str | None:
        mapping = {
            ".": "\u3002",
            "!": "\uff01",
            "?": "\uff1f",
            ";": "\uff1b",
            ":": "\uff1a",
            ",": "\uff0c",
        }
        return mapping.get(ch)

    def _load_cedict(self, cedict_path: Path, max_entries: int) -> int:
        pattern = re.compile(r"^(\S+)\s+(\S+)\s+\[(.+?)\]\s+/(.+)/$")
        loaded = 0
        with cedict_path.open("r", encoding="utf-8") as file:
            for raw in file:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                match = pattern.match(line)
                if not match:
                    continue

                simplified = match.group(2).strip()
                definition_raw = match.group(4).strip()
                translation = self._extract_primary_gloss(definition_raw)
                if not simplified or not translation:
                    continue
                if simplified in self.dictionary:
                    continue

                self.dictionary[simplified] = translation
                self._register_en_zh(translation, simplified)
                loaded += 1
                if max_entries and loaded >= max_entries:
                    break
        return loaded

    def _load_en_zh_tmx(self, tmx_path: Path, max_entries: int) -> int:
        xml_lang_key = "{http://www.w3.org/XML/1998/namespace}lang"
        loaded = 0

        for _, elem in ElementTree.iterparse(tmx_path, events=("end",)):
            if not isinstance(elem.tag, str) or not elem.tag.endswith("tu"):
                continue

            en_text: str | None = None
            zh_text: str | None = None

            for tuv in elem:
                if not isinstance(tuv.tag, str) or not tuv.tag.endswith("tuv"):
                    continue
                lang = (tuv.attrib.get(xml_lang_key) or tuv.attrib.get("lang") or "").lower()
                seg_text = ""
                for seg in tuv:
                    if isinstance(seg.tag, str) and seg.tag.endswith("seg"):
                        seg_text = "".join(seg.itertext()).strip()
                        break
                if not seg_text:
                    continue
                if lang.startswith("en"):
                    en_text = seg_text
                elif lang.startswith("zh"):
                    zh_text = seg_text

            if en_text and zh_text and self._register_en_zh(en_text, zh_text):
                loaded += 1
                if max_entries and loaded >= max_entries:
                    break

            elem.clear()

        return loaded

    @staticmethod
    def _extract_primary_gloss(definition_raw: str) -> str:
        parts = [item.strip() for item in definition_raw.split("/") if item.strip()]
        if not parts:
            return ""
        value = parts[0]
        value = value.split(";")[0].strip()
        value = re.sub(r"\([^)]*\)", "", value).strip()
        value = re.sub(r"\s+", " ", value)
        if value.lower().startswith("variant of "):
            return ""
        if value.lower().startswith("classifier for "):
            return ""
        return value

    @staticmethod
    def _lemma_en_word(token: str) -> str:
        word = token.lower().strip()
        irregular = {
            "sat": "sit",
            "was": "be",
            "were": "be",
            "watched": "watch",
            "flowed": "flow",
            "saw": "see",
            "went": "go",
            "did": "do",
            "had": "have",
        }
        if word in irregular:
            return irregular[word]
        if len(word) > 4 and word.endswith("ing"):
            return word[:-3]
        if len(word) > 3 and word.endswith("ed"):
            return word[:-2]
        if len(word) > 3 and word.endswith("s"):
            return word[:-1]
        return word

    def _register_en_zh(self, source_en: str, target_zh: str) -> bool:
        normalized_en = self._normalize_en(source_en)
        normalized_zh = self._normalize_zh(target_zh)
        if not normalized_en or not normalized_zh:
            return False
        if normalized_en in self.reverse_dictionary:
            return False

        self.reverse_dictionary[normalized_en] = normalized_zh

        if normalized_en.startswith("to "):
            bare = normalized_en[3:].strip()
            if bare and bare not in self.reverse_dictionary:
                self.reverse_dictionary[bare] = normalized_zh

        return True

    def _lookup_en_zh(self, text: str) -> str | None:
        normalized = self._normalize_en(text)
        if not normalized:
            return None

        direct = self.reverse_dictionary.get(normalized)
        if direct:
            return direct

        words = normalized.split()
        if words:
            lemma_phrase = " ".join(self._lemma_en_word(word) for word in words)
            if lemma_phrase != normalized:
                lemma_direct = self.reverse_dictionary.get(lemma_phrase)
                if lemma_direct:
                    return lemma_direct

            if len(words) == 1:
                candidate = f"to {self._lemma_en_word(words[0])}"
                prefixed = self.reverse_dictionary.get(candidate)
                if prefixed:
                    return prefixed

        return None

    def _segment_translate_en_zh(self, text: str) -> str:
        tokens = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+|[^\w\s]", text)
        if not tokens:
            return ""

        output: list[str] = []
        index = 0
        total = len(tokens)
        while index < total:
            token = tokens[index]

            punct = self._map_en_punctuation_to_zh(token)
            if punct is not None:
                output.append(punct)
                index += 1
                continue

            if not re.match(r"^[A-Za-z0-9']+$", token):
                output.append(token)
                index += 1
                continue

            matched = False
            max_window = min(self.max_en_phrase_tokens, total - index)
            for size in range(max_window, 0, -1):
                candidate_tokens = tokens[index : index + size]
                if any(self._map_en_punctuation_to_zh(item) is not None for item in candidate_tokens):
                    continue
                if not all(re.match(r"^[A-Za-z0-9']+$", item) for item in candidate_tokens):
                    continue

                candidate = " ".join(candidate_tokens)
                translated = self._lookup_en_zh(candidate)
                if not translated:
                    continue
                output.append(translated)
                index += size
                matched = True
                break

            if matched:
                continue

            output.append(token)
            index += 1

        return self._join_tokens_zh(output)

    @staticmethod
    def _join_tokens_zh(tokens: list[str]) -> str:
        if not tokens:
            return ""

        punctuation_tokens = {"\u3002", "\uff0c", "\uff1f", "\uff01", "\uff1b", "\uff1a"}
        pieces: list[str] = []
        for token in tokens:
            value = token.strip()
            if not value:
                continue
            if value in punctuation_tokens and pieces:
                pieces[-1] = pieces[-1].rstrip() + value
                continue
            if pieces and re.match(r"^[A-Za-z0-9']+$", pieces[-1]) and re.match(r"^[A-Za-z0-9']+$", value):
                pieces[-1] = pieces[-1] + " " + value
                continue
            pieces.append(value)

        return "".join(pieces).strip()

    def _resolve_optional_path(self, path_value: str | None) -> Path | None:
        if not path_value:
            return None
        path = Path(path_value)
        if path.is_absolute():
            return path
        return (self.base_dir / path).resolve()
