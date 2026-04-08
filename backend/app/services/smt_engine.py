from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.config import Settings
from app.services.base import BaseEngine, TranslationOutput


class SmtEngine(BaseEngine):
    name = "smt"

    def __init__(self, settings: Settings) -> None:
        self.base_dir = Path(__file__).resolve().parents[2]
        self.enabled = settings.smt_enabled
        self.mode = (settings.smt_mode or "auto").lower()
        self.moses_root = settings.smt_moses_root
        self.moses_bin_override = settings.smt_moses_bin
        self.niutrans_root = settings.smt_niutrans_root
        self.niutrans_bin_override = settings.smt_niutrans_bin
        self.niutrans_config = settings.smt_niutrans_config
        self.model_dir = settings.smt_model_dir
        self.docker_image = settings.smt_docker_image
        self.timeout_seconds = settings.smt_timeout_seconds

        self.lite_model_path = settings.smt_lite_model_path
        self.lite_seed_path = settings.smt_lite_seed_path
        self.lite_max_cedict_entries = max(0, settings.smt_lite_max_cedict_entries)
        self.cedict_path = settings.rbmt_cedict_path

        self._lite_tables: dict[tuple[str, str], dict[str, str]] = {
            ("zh", "en"): {},
            ("en", "zh"): {},
        }
        self._lite_phrase_len: dict[tuple[str, str], int] = {
            ("zh", "en"): 1,
            ("en", "zh"): 1,
        }
        self._lite_error: str | None = None
        self._lite_loaded_entries = 0
        self._load_lite_resources()

    def status(self) -> tuple[bool, str]:
        if not self.enabled:
            return False, "SMT disabled by config"

        if self.mode == "local":
            return self._status_local()
        if self.mode == "niutrans":
            return self._status_niutrans()
        if self.mode == "docker":
            return self._status_docker()
        if self.mode == "lite":
            return self._status_lite()
        if self.mode == "auto":
            local_ready, local_msg = self._status_local()
            if local_ready:
                return True, f"ready(auto->local): {local_msg}"

            niutrans_ready, niutrans_msg = self._status_niutrans()
            if niutrans_ready:
                return True, f"ready(auto->niutrans): {niutrans_msg}"

            docker_ready, docker_msg = self._status_docker()
            if docker_ready:
                return True, f"ready(auto->docker): {docker_msg}"

            lite_ready, lite_msg = self._status_lite()
            if lite_ready:
                return True, f"ready(auto->lite): {lite_msg}"
            return (
                False,
                f"auto failed: local={local_msg}; niutrans={niutrans_msg}; docker={docker_msg}; lite={lite_msg}",
            )

        return False, f"unsupported SMT_MODE: {self.mode}"

    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> TranslationOutput:
        if not self.enabled:
            return TranslationOutput(text=text, ready=False, error="SMT disabled by config")

        if self.mode == "local":
            return await asyncio.to_thread(self._run_local_decode, text)
        if self.mode == "niutrans":
            return await asyncio.to_thread(self._run_niutrans_decode, text)
        if self.mode == "docker":
            return await asyncio.to_thread(self._run_docker_decode, text)
        if self.mode == "lite":
            return self._run_lite_decode(text, src_lang, tgt_lang)
        if self.mode == "auto":
            local_ready, _ = self._status_local()
            if local_ready:
                return await asyncio.to_thread(self._run_local_decode, text)
            niutrans_ready, _ = self._status_niutrans()
            if niutrans_ready:
                return await asyncio.to_thread(self._run_niutrans_decode, text)
            docker_ready, _ = self._status_docker()
            if docker_ready:
                return await asyncio.to_thread(self._run_docker_decode, text)
            return self._run_lite_decode(text, src_lang, tgt_lang)

        return TranslationOutput(text=text, ready=False, error=f"unsupported SMT_MODE: {self.mode}")

    def _status_local(self) -> tuple[bool, str]:
        moses_ini = self._resolve_moses_ini()
        if moses_ini is None:
            return False, f"SMT model package missing: {self.model_dir}/moses.ini"
        moses_bin = self._resolve_local_moses_bin()
        if moses_bin is None:
            return False, "local Moses binary not found (set SMT_MOSES_BIN or SMT_MOSES_ROOT)"
        return True, f"{moses_bin} + {moses_ini}"

    def _status_docker(self) -> tuple[bool, str]:
        if shutil.which("docker") is None:
            return False, "docker executable not found"
        moses_ini = self._resolve_moses_ini()
        if moses_ini is None:
            return False, f"SMT model package missing: {self.model_dir}/moses.ini"
        model_dir = self._resolve_path(self.model_dir)
        if not model_dir.exists() or not model_dir.is_dir():
            return False, f"SMT model directory not found: {model_dir}"
        return True, f"{self.docker_image} + {moses_ini}"

    def _status_niutrans(self) -> tuple[bool, str]:
        decoder = self._resolve_niutrans_decoder_bin()
        if decoder is None:
            return False, "NiuTrans.Decoder binary not found (set SMT_NIUTRANS_BIN or SMT_NIUTRANS_ROOT)"
        config_path = self._resolve_niutrans_config()
        if config_path is None:
            return False, "NiuTrans config not found (set SMT_NIUTRANS_CONFIG)"
        return True, f"{decoder} + {config_path}"

    def _status_lite(self) -> tuple[bool, str]:
        if self._lite_error:
            return False, self._lite_error
        zh_en = len(self._lite_tables[("zh", "en")])
        en_zh = len(self._lite_tables[("en", "zh")])
        if zh_en == 0 and en_zh == 0:
            return False, "SMT lite table is empty (provide SMT_LITE_MODEL_PATH or SMT_LITE_SEED_PATH)"
        return True, f"lite table loaded: zh->en={zh_en}, en->zh={en_zh}"

    def _run_local_decode(self, text: str) -> TranslationOutput:
        moses_bin = self._resolve_local_moses_bin()
        moses_ini = self._resolve_moses_ini()
        if moses_bin is None or moses_ini is None:
            return TranslationOutput(text=text, ready=False, error="SMT local runtime missing")

        command = [str(moses_bin), "-f", str(moses_ini)]
        try:
            result = subprocess.run(
                command,
                input=(text.strip() + "\n"),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except Exception as exc:
            return TranslationOutput(text=text, ready=False, error=f"SMT local execution failed: {exc}")

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            return TranslationOutput(text=text, ready=False, error=f"SMT decode failed: {stderr}")

        translated = (result.stdout or "").strip().splitlines()
        output = translated[0].strip() if translated else text
        return TranslationOutput(text=output or text)

    def _run_docker_decode(self, text: str) -> TranslationOutput:
        model_dir = self._resolve_path(self.model_dir)
        if not model_dir.exists() or not model_dir.is_dir():
            return TranslationOutput(text=text, ready=False, error=f"SMT model directory not found: {model_dir}")

        host_mount = model_dir.as_posix()

        command = [
            "docker",
            "run",
            "--rm",
            "-i",
            "-v",
            f"{host_mount}:/model",
            self.docker_image,
            "/usr/local/bin/moses",
            "-f",
            "/model/moses.ini",
        ]

        try:
            result = subprocess.run(
                command,
                input=(text.strip() + "\n"),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except Exception as exc:
            return TranslationOutput(text=text, ready=False, error=f"SMT docker execution failed: {exc}")

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            return TranslationOutput(text=text, ready=False, error=f"SMT docker decode failed: {stderr}")

        translated = (result.stdout or "").strip().splitlines()
        output = translated[0].strip() if translated else text
        return TranslationOutput(text=output or text)

    def _run_niutrans_decode(self, text: str) -> TranslationOutput:
        decoder = self._resolve_niutrans_decoder_bin()
        config_path = self._resolve_niutrans_config()
        if decoder is None or config_path is None:
            return TranslationOutput(text=text, ready=False, error="NiuTrans runtime missing")

        with tempfile.TemporaryDirectory(prefix="smt_niutrans_") as tmp_dir:
            work = Path(tmp_dir)
            input_file = work / "input.txt"
            output_file = work / "output.txt"
            input_file.write_text((text.strip() + "\n"), encoding="utf-8")

            command = [
                str(decoder),
                "-decoding",
                str(input_file),
                "-config",
                str(config_path),
                "-output",
                str(output_file),
            ]

            try:
                result = subprocess.run(
                    command,
                    text=True,
                    capture_output=True,
                    cwd=str(config_path.parent),
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except Exception as exc:
                return TranslationOutput(text=text, ready=False, error=f"NiuTrans execution failed: {exc}")

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                stdout = (result.stdout or "").strip()
                message = stderr or stdout or f"exit_code={result.returncode}"
                return TranslationOutput(text=text, ready=False, error=f"NiuTrans decode failed: {message}")

            if not output_file.exists():
                return TranslationOutput(text=text, ready=False, error="NiuTrans decode finished but no output file")

            translated_lines = output_file.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
            output = translated_lines[0].strip() if translated_lines else text
            return TranslationOutput(text=output or text)

    def _run_lite_decode(self, text: str, src_lang: str, tgt_lang: str) -> TranslationOutput:
        ready, message = self._status_lite()
        if not ready:
            return TranslationOutput(text=text, ready=False, error=message)

        pair = (src_lang, tgt_lang)
        table = self._lite_tables.get(pair, {})
        if not table:
            return TranslationOutput(text=text, ready=False, error=f"SMT lite unsupported pair: {src_lang}->{tgt_lang}")

        if src_lang == "zh" and tgt_lang == "en":
            translated = self._translate_zh_to_en_lite(text, table, self._lite_phrase_len[pair])
            return TranslationOutput(text=translated, meta={"mode": "lite"})

        if src_lang == "en" and tgt_lang == "zh":
            translated = self._translate_en_to_zh_lite(text, table, self._lite_phrase_len[pair])
            return TranslationOutput(text=translated, meta={"mode": "lite"})

        return TranslationOutput(text=text, ready=False, error=f"SMT lite unsupported pair: {src_lang}->{tgt_lang}")

    def _load_lite_resources(self) -> None:
        zh_en: dict[str, str] = {}
        en_zh: dict[str, str] = {}

        model_path = self._resolve_path(self.lite_model_path)
        if model_path.exists():
            try:
                data = json.loads(model_path.read_text(encoding="utf-8"))
                zh_en.update({str(k): str(v) for k, v in data.get("zh->en", {}).items() if k and v})
                en_zh.update({str(k).lower(): str(v) for k, v in data.get("en->zh", {}).items() if k and v})
            except Exception as exc:
                self._lite_error = f"SMT lite model invalid: {exc}"
                return

        seed_path = self._resolve_path(self.lite_seed_path)
        if seed_path.exists():
            try:
                for raw in seed_path.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) < 4:
                        continue
                    src_lang, tgt_lang, source, target = [part.strip() for part in parts[:4]]
                    if src_lang == "zh" and tgt_lang == "en" and source and target and source not in zh_en:
                        zh_en[source] = target
                    if src_lang == "en" and tgt_lang == "zh" and source and target:
                        key = self._normalize_en_phrase(source)
                        if key and key not in en_zh:
                            en_zh[key] = target
            except Exception as exc:
                self._lite_error = f"SMT lite seed load failed: {exc}"
                return

        cedict = self._resolve_optional_path(self.cedict_path)
        if cedict and cedict.exists():
            self._load_from_cedict(cedict, zh_en)

        for zh_text, en_text in zh_en.items():
            key = self._normalize_en_phrase(en_text)
            if key and key not in en_zh and len(zh_text) <= 8:
                en_zh[key] = zh_text

        self._lite_tables[("zh", "en")] = zh_en
        self._lite_tables[("en", "zh")] = en_zh
        self._lite_phrase_len[("zh", "en")] = max((len(key) for key in zh_en), default=1)
        self._lite_phrase_len[("en", "zh")] = max((len(key.split()) for key in en_zh), default=1)
        self._lite_loaded_entries = len(zh_en) + len(en_zh)

    def _load_from_cedict(self, cedict_path: Path, zh_en: dict[str, str]) -> None:
        pattern = re.compile(r"^(\S+)\s+(\S+)\s+\[(.+?)\]\s+/(.+)/$")
        loaded = 0
        for raw in cedict_path.read_text(encoding="utf-8", errors="ignore").splitlines():
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
            if simplified in zh_en:
                continue
            zh_en[simplified] = translation
            loaded += 1
            if self.lite_max_cedict_entries and loaded >= self.lite_max_cedict_entries:
                break

    @staticmethod
    def _extract_primary_gloss(definition_raw: str) -> str:
        parts = [item.strip() for item in definition_raw.split("/") if item.strip()]
        if not parts:
            return ""
        value = parts[0].split(";")[0].strip()
        value = re.sub(r"\([^)]*\)", "", value).strip()
        value = re.sub(r"\s+", " ", value)
        if value.lower().startswith("variant of "):
            return ""
        if value.lower().startswith("classifier for "):
            return ""
        return value

    def _translate_zh_to_en_lite(self, text: str, table: dict[str, str], max_phrase_len: int) -> str:
        punctuation = {
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
        normalized = text.strip()
        output: list[str] = []
        index = 0
        total = len(normalized)

        while index < total:
            token = normalized[index]
            if token.isspace():
                index += 1
                continue
            if token in punctuation:
                output.append(punctuation[token])
                index += 1
                continue

            matched = False
            window = min(max_phrase_len, total - index)
            for size in range(window, 1, -1):
                candidate = normalized[index : index + size]
                translated = table.get(candidate)
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

        return self._join_en_tokens(output)

    def _translate_en_to_zh_lite(self, text: str, table: dict[str, str], max_phrase_words: int) -> str:
        tokens = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+|[^\w\s]", text)
        output: list[str] = []
        index = 0
        total = len(tokens)

        while index < total:
            token = tokens[index]
            if re.fullmatch(r"[^\w\s]", token):
                output.append(token)
                index += 1
                continue

            matched = False
            window = min(max_phrase_words, total - index)
            for size in range(window, 0, -1):
                phrase_tokens = tokens[index : index + size]
                phrase = " ".join(part.lower() for part in phrase_tokens if re.match(r"[A-Za-z0-9']", part))
                phrase = self._normalize_en_phrase(phrase)
                if not phrase:
                    continue
                translated = table.get(phrase)
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

        return self._join_zh_tokens(output)

    @staticmethod
    def _join_en_tokens(tokens: list[str]) -> str:
        punctuation_tokens = {".", ",", ";", "!", "?"}
        output: list[str] = []
        for token in tokens:
            if token in punctuation_tokens and output:
                output[-1] = output[-1].rstrip() + token
            else:
                output.append(token)
        return " ".join(part for part in output if part).strip()

    @staticmethod
    def _join_zh_tokens(tokens: list[str]) -> str:
        punctuation_tokens = {".", ",", ";", "!", "?", "\u3002", "\uff0c", "\uff1b", "\uff01", "\uff1f"}
        output: list[str] = []
        for token in tokens:
            if token in punctuation_tokens and output:
                output[-1] = output[-1].rstrip() + token
            else:
                output.append(token)
        combined = "".join(output).strip()
        return re.sub(r"\s+", " ", combined)

    @staticmethod
    def _normalize_en_phrase(text: str) -> str:
        normalized = text.lower().strip()
        normalized = re.sub(r"[^a-z0-9'\s]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _resolve_local_moses_bin(self) -> Path | None:
        if self.moses_bin_override:
            path = self._resolve_path(self.moses_bin_override)
            if path.exists():
                return path

        if not self.moses_root:
            return None

        root = self._resolve_path(self.moses_root)
        candidates = [
            root / "bin" / "moses",
            root / "bin" / "moses.exe",
            root / "moses",
            root / "moses.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _resolve_niutrans_decoder_bin(self) -> Path | None:
        if self.niutrans_bin_override:
            path = self._resolve_path(self.niutrans_bin_override)
            if path.exists():
                return path

        if not self.niutrans_root:
            return None

        root = self._resolve_path(self.niutrans_root)
        candidates = [
            root / "bin" / "NiuTrans.Decoder.exe",
            root / "bin" / "NiuTrans.Decoder",
            root / "NiuTrans.Decoder.exe",
            root / "NiuTrans.Decoder",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _resolve_niutrans_config(self) -> Path | None:
        if not self.niutrans_config:
            return None
        config_path = self._resolve_path(self.niutrans_config)
        if config_path.exists():
            return config_path
        return None

    def _resolve_moses_ini(self) -> Path | None:
        model_dir = self._resolve_path(self.model_dir)
        moses_ini = model_dir / "moses.ini"
        if moses_ini.exists():
            return moses_ini
        return None

    def _resolve_path(self, path_like: str | None) -> Path:
        if not path_like:
            return self.base_dir
        path = Path(path_like)
        if path.is_absolute():
            return path.resolve()
        return (self.base_dir / path).resolve()

    def _resolve_optional_path(self, path_like: str | None) -> Path | None:
        if not path_like:
            return None
        return self._resolve_path(path_like)
