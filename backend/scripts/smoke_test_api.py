from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
os.chdir(ROOT_DIR)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import app


def assert_status(code: int, label: str) -> None:
    if code != 200:
        raise RuntimeError(f"{label} failed with status {code}")


def main() -> None:
    print("== MT-Lab Live API smoke test ==")

    with TestClient(app) as client:
        health = client.get("/health")
        assert_status(health.status_code, "health")
        print("[OK] GET /health")

        engines = client.get("/api/v1/engines")
        assert_status(engines.status_code, "engines")
        engine_map = engines.json()
        print(f"[OK] GET /api/v1/engines ({len(engine_map)} engines)")

        test_cases = client.get("/api/v1/test_cases")
        assert_status(test_cases.status_code, "test_cases")
        cases = test_cases.json()
        print(f"[OK] GET /api/v1/test_cases ({len(cases)} cases)")

        translate_payload = {
            "text": "这个问题有点难搞。",
            "src_lang": "zh",
            "tgt_lang": "en",
            "engines": ["rbmt"],
            "reference": "This problem is a bit tricky.",
        }
        single = client.post("/api/v1/translate", json=translate_payload)
        assert_status(single.status_code, "translate")
        single_data = single.json()
        print("[OK] POST /api/v1/translate")
        print(f"     translation={single_data['results'][0]['translation']}")

        batch_payload = {
            "texts": [
                "这个问题有点难搞。",
                "我也是醉了。",
            ],
            "references": [
                "This problem is a bit tricky.",
                "I'm speechless.",
            ],
            "src_lang": "zh",
            "tgt_lang": "en",
            "engines": ["rbmt"],
        }
        batch = client.post("/api/v1/batch_translate", json=batch_payload)
        assert_status(batch.status_code, "batch_translate")
        batch_data = batch.json()
        print(f"[OK] POST /api/v1/batch_translate ({len(batch_data.get('items', []))} items)")

        evaluate_payload = {
            "candidate": "This problem is a bit tricky.",
            "reference": "This problem is a bit tricky.",
        }
        evaluate = client.post("/api/v1/evaluate", json=evaluate_payload)
        assert_status(evaluate.status_code, "evaluate")
        print("[OK] POST /api/v1/evaluate")

        print("\nEngine readiness summary:")
        print(json.dumps(engine_map, ensure_ascii=False, indent=2))

    print("\nSmoke test passed.")


if __name__ == "__main__":
    main()
