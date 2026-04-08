from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def extract_primary_gloss(definition_raw: str) -> str:
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


def load_seed(seed_path: Path, zh_en: dict[str, str], en_zh: dict[str, str]) -> None:
    if not seed_path.exists():
        return
    for raw in seed_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        src_lang, tgt_lang, source, target = [part.strip() for part in parts[:4]]
        if src_lang == "zh" and tgt_lang == "en" and source and target:
            zh_en.setdefault(source, target)
        elif src_lang == "en" and tgt_lang == "zh" and source and target:
            key = normalize_en_phrase(source)
            if key:
                en_zh.setdefault(key, target)


def load_cedict(cedict_path: Path, zh_en: dict[str, str], max_entries: int) -> int:
    if not cedict_path.exists():
        return 0
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
        translation = extract_primary_gloss(match.group(4).strip())
        if not simplified or not translation:
            continue
        if simplified in zh_en:
            continue
        zh_en[simplified] = translation
        loaded += 1
        if max_entries and loaded >= max_entries:
            break
    return loaded


def build_inverse(zh_en: dict[str, str], en_zh: dict[str, str]) -> None:
    for zh_text, en_text in zh_en.items():
        key = normalize_en_phrase(en_text)
        if key and key not in en_zh and len(zh_text) <= 8:
            en_zh[key] = zh_text


def normalize_en_phrase(text: str) -> str:
    normalized = text.lower().strip()
    normalized = re.sub(r"[^a-z0-9'\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SMT lite phrase table JSON from seed + CEDICT.")
    parser.add_argument(
        "--seed",
        default="data/smt_lite_seed.tsv",
        help="TSV path: src_lang\\ttgt_lang\\tsource\\ttarget",
    )
    parser.add_argument("--cedict", default="", help="Path to cedict_ts.u8 (optional)")
    parser.add_argument("--max-cedict", type=int, default=120000, help="Max CEDICT entries to ingest")
    parser.add_argument("--output", default="smt_model/lite_phrase_table.json", help="Output JSON path")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    seed_path = (root / args.seed).resolve()
    output_path = (root / args.output).resolve()
    cedict_path = Path(args.cedict).resolve() if args.cedict else None

    zh_en: dict[str, str] = {}
    en_zh: dict[str, str] = {}

    load_seed(seed_path, zh_en, en_zh)
    cedict_loaded = 0
    if cedict_path:
        cedict_loaded = load_cedict(cedict_path, zh_en, max(0, args.max_cedict))
    build_inverse(zh_en, en_zh)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "meta": {
            "seed_path": str(seed_path),
            "cedict_path": str(cedict_path) if cedict_path else "",
            "cedict_loaded": cedict_loaded,
            "zh_en_size": len(zh_en),
            "en_zh_size": len(en_zh),
        },
        "zh->en": zh_en,
        "en->zh": en_zh,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] output: {output_path}")
    print(f"[OK] zh->en entries: {len(zh_en)}")
    print(f"[OK] en->zh entries: {len(en_zh)}")
    print(f"[OK] cedict loaded: {cedict_loaded}")


if __name__ == "__main__":
    main()
