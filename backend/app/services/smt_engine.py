import asyncio
import shutil
import subprocess
from pathlib import Path

from app.core.config import Settings
from app.services.base import BaseEngine, TranslationOutput


class SmtEngine(BaseEngine):
    name = "smt"

    def __init__(self, settings: Settings) -> None:
        self.base_dir = Path(__file__).resolve().parents[2]
        self.enabled = settings.smt_enabled
        self.mode = (settings.smt_mode or "local").lower()
        self.moses_root = settings.smt_moses_root
        self.moses_bin_override = settings.smt_moses_bin
        self.model_dir = settings.smt_model_dir
        self.docker_image = settings.smt_docker_image
        self.timeout_seconds = settings.smt_timeout_seconds

    def status(self) -> tuple[bool, str]:
        if not self.enabled:
            return False, "SMT disabled by config"

        moses_ini = self._resolve_moses_ini()
        if moses_ini is None:
            return False, f"SMT model package missing: {self.model_dir}/moses.ini"

        if self.mode == "local":
            moses_bin = self._resolve_local_moses_bin()
            if moses_bin is None:
                return False, "local Moses binary not found (set SMT_MOSES_BIN or SMT_MOSES_ROOT)"
            return True, f"ready(local): {moses_bin} + {moses_ini}"

        if self.mode == "docker":
            if shutil.which("docker") is None:
                return False, "docker executable not found"
            model_dir = self._resolve_path(self.model_dir)
            if not model_dir.exists() or not model_dir.is_dir():
                return False, f"SMT model directory not found: {model_dir}"
            return True, f"ready(docker): {self.docker_image} + {moses_ini}"

        return False, f"unsupported SMT_MODE: {self.mode}"

    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> TranslationOutput:
        ready, message = self.status()
        if not ready:
            return TranslationOutput(text=text, ready=False, error=message)

        if self.mode == "local":
            return await asyncio.to_thread(self._run_local_decode, text)
        if self.mode == "docker":
            return await asyncio.to_thread(self._run_docker_decode, text)

        return TranslationOutput(text=text, ready=False, error=f"unsupported SMT_MODE: {self.mode}")

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
