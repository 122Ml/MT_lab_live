from __future__ import annotations

import sys
import shlex
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings


def resolve_path(path_like: str) -> Path:
    raw_path = Path(path_like)
    if raw_path.is_absolute():
        return raw_path
    return (ROOT_DIR / raw_path).resolve()


def check_dir(model_name: str, required_files: Iterable[str]) -> tuple[bool, list[str], str]:
    model_path = resolve_path(model_name)
    if not model_path.exists() or not model_path.is_dir():
        return False, list(required_files), "NOT_LOCAL_DIR"

    missing = [file_name for file_name in required_files if not (model_path / file_name).exists()]
    return len(missing) == 0, missing, str(model_path)


def check_file(file_path: str, file_label: str) -> tuple[bool, str, str]:
    resolved = resolve_path(file_path)
    if resolved.exists() and resolved.is_file():
        return True, file_label, str(resolved)
    return False, file_label, str(resolved)


def discover_moses_bin_from_root(moses_root: str | None) -> Path | None:
    if not moses_root:
        return None
    root_path = resolve_path(moses_root)
    candidates = [
        root_path / "bin" / "moses",
        root_path / "bin" / "moses.exe",
        root_path / "moses",
        root_path / "moses.exe",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def looks_like_resource_path(token: str) -> bool:
    stripped = token.strip().strip('"').strip("'")
    if not stripped:
        return False
    if stripped.startswith("-"):
        return False

    lower = stripped.lower()
    known_extensions = (
        ".bin",
        ".gz",
        ".arpa",
        ".ini",
        ".model",
        ".txt",
        ".srilm",
    )
    if lower.endswith(known_extensions):
        return True

    has_sep = "/" in stripped or "\\" in stripped
    return has_sep and "." in stripped


def extract_paths_from_moses_ini(moses_ini: Path) -> list[Path]:
    collected: set[Path] = set()
    for raw_line in moses_ini.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue

        content = line.split("#", 1)[0].strip()
        if not content:
            continue

        for key in ("path=", "file="):
            if key in content:
                value = content.split(key, 1)[1].strip().split()[0]
                candidate = Path(value.strip('"').strip("'"))
                if not candidate.is_absolute():
                    candidate = (moses_ini.parent / candidate).resolve()
                collected.add(candidate)

        try:
            tokens = shlex.split(content, posix=False)
        except ValueError:
            tokens = content.split()

        for token in tokens:
            if "=" in token:
                _, raw_value = token.split("=", 1)
                if looks_like_resource_path(raw_value):
                    candidate = Path(raw_value.strip('"').strip("'"))
                else:
                    continue
            else:
                if not looks_like_resource_path(token):
                    continue
                candidate = Path(token.strip('"').strip("'"))

            if not candidate.is_absolute():
                candidate = (moses_ini.parent / candidate).resolve()
            collected.add(candidate)

    return sorted(collected)


def main() -> None:
    settings = get_settings()
    print("== MT-Lab Live model readiness check (no download) ==")
    print("This script checks local model directories only.")

    model_checks = [
        (
            "nmt zh->en",
            settings.nmt_model_zh_en,
            [
                "pytorch_model.bin",
                "config.json",
                "tokenizer_config.json",
                "vocab.json",
                "source.spm",
                "target.spm",
            ],
        ),
        (
            "nmt en->zh",
            settings.nmt_model_en_zh,
            [
                "pytorch_model.bin",
                "config.json",
                "tokenizer_config.json",
                "vocab.json",
                "source.spm",
                "target.spm",
            ],
        ),
    ]

    if settings.transformer_enabled:
        model_checks.append(
            (
                "transformer",
                settings.transformer_model,
                [
                    "pytorch_model.bin",
                    "config.json",
                    "tokenizer.json",
                    "tokenizer_config.json",
                    "sentencepiece.bpe.model",
                    "special_tokens_map.json",
                ],
            )
        )

    has_blockers = False

    if settings.smt_enabled:
        print("\n== SMT runtime checks ==")
        if settings.smt_mode.lower() == "local":
            if settings.smt_moses_bin:
                ok, label, resolved = check_file(settings.smt_moses_bin, "SMT_MOSES_BIN")
                if ok:
                    print(f"[OK] {label}: {resolved}")
                else:
                    has_blockers = True
                    print(f"[MISS] {label}: {resolved}")
            else:
                discovered = discover_moses_bin_from_root(settings.smt_moses_root)
                if discovered:
                    print(f"[OK] SMT_MOSES_ROOT resolved bin: {discovered}")
                else:
                    has_blockers = True
                    print("[MISS] SMT local Moses binary not found from SMT_MOSES_ROOT")

        moses_ini_path = resolve_path(settings.smt_model_dir) / "moses.ini"
        if moses_ini_path.exists():
            print(f"[OK] SMT model package: {moses_ini_path}")
            referenced_paths = extract_paths_from_moses_ini(moses_ini_path)
            if referenced_paths:
                missing_refs = [path for path in referenced_paths if not path.exists()]
                if missing_refs:
                    has_blockers = True
                    print("[MISS] SMT moses.ini referenced files missing:")
                    for missing in missing_refs:
                        print(f"       - {missing}")
                else:
                    print(f"[OK] SMT moses.ini references: {len(referenced_paths)} files exist")
            else:
                print("[WARN] SMT moses.ini has no detectable file references")
        else:
            has_blockers = True
            print(f"[MISS] SMT model package missing moses.ini: {moses_ini_path}")
            example_path = moses_ini_path.with_suffix(".ini.example")
            if example_path.exists():
                print(f"       Hint: copy template first -> {example_path.name} to moses.ini")

        kenlm_candidate = resolve_path(settings.smt_model_dir) / "lm.binary"
        if kenlm_candidate.exists():
            print(f"[OK] KenLM binary: {kenlm_candidate}")
        else:
            print(f"[WARN] KenLM binary not found (optional check): {kenlm_candidate}")

    for label, model_name, required in model_checks:
        ok, missing, detail = check_dir(model_name, required)
        if ok:
            print(f"[OK] {label}: {detail}")
            continue

        has_blockers = True
        print(f"[MISS] {label}: {model_name}")
        if detail == "NOT_LOCAL_DIR":
            print("       Please set this env value to a local model folder path.")
        else:
            print(f"       Missing files: {', '.join(missing)}")

    if has_blockers:
        print("\nResolve missing items, then run this script again.")
    else:
        print("\nAll required local model files are ready.")


if __name__ == "__main__":
    main()
