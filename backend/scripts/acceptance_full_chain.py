from __future__ import annotations

import base64
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
from app.services.llm_api_engine import LlmApiEngine


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletionResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    async def create(self, model: str, temperature: int, max_tokens: int, messages: list[dict[str, object]]):  # type: ignore[override]
        last = messages[-1]
        payload = last.get("content")
        if isinstance(payload, str):
            payload_summary = payload[:120]
        else:
            payload_summary = json.dumps(payload, ensure_ascii=False)[:120]
        return _FakeCompletionResponse(f"[fake:{model}] {payload_summary}")


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeOpenAI:
    def __init__(self) -> None:
        self.chat = _FakeChat()


def assert_ok(code: int, label: str) -> None:
    if code != 200:
        raise RuntimeError(f"{label} failed with status={code}")


def assert_non_empty(value: str, label: str) -> None:
    if not value.strip():
        raise RuntimeError(f"{label} returned empty result")


def main() -> None:
    print("== MT-Lab Live acceptance test: all methods + multimodal ==")
    png_1x1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6q5WQAAAAASUVORK5CYII="
    wav_stub = base64.b64encode(b"RIFF....WAVEfmt ").decode("ascii")
    mp4_stub = base64.b64encode(b"\x00\x00\x00\x18ftypmp42").decode("ascii")

    with TestClient(app) as client:
        manager = app.state.engine_manager
        llm_engine = manager.engines["llm_api"]
        if isinstance(llm_engine, LlmApiEngine):
            llm_engine.client = _FakeOpenAI()  # type: ignore[assignment]

        health = client.get("/health")
        assert_ok(health.status_code, "GET /health")
        print("[OK] /health")

        engines = client.get("/api/v1/engines")
        assert_ok(engines.status_code, "GET /api/v1/engines")
        engine_map = engines.json()
        print(f"[OK] /api/v1/engines => {len(engine_map)} engines")

        all_engines = ["rbmt", "smt", "nmt", "transformer", "llm_api"]
        sample_text = "这个问题有点难搞。"

        for engine_name in all_engines:
            resp = client.post(
                "/api/v1/translate",
                json={
                    "text": sample_text,
                    "src_lang": "zh",
                    "tgt_lang": "en",
                    "engines": [engine_name],
                },
            )
            assert_ok(resp.status_code, f"POST /api/v1/translate ({engine_name})")
            data = resp.json()
            result = data["results"][0]
            assert_non_empty(result["translation"], f"engine={engine_name}")
            print(
                f"[OK] engine={engine_name:<11} ready={str(result['ready']):<5} "
                f"latency_ms={result['latency_ms']} translation={result['translation'][:40]}"
            )

        llm_settings = client.get("/api/v1/settings/llm")
        assert_ok(llm_settings.status_code, "GET /api/v1/settings/llm")
        print("[OK] /api/v1/settings/llm")

        update_settings = client.put(
            "/api/v1/settings/llm",
            json={
                "image_prompt": "Describe image and translate into English.",
                "audio_prompt": "Transcribe audio and translate into English.",
                "video_prompt": "Summarize video and translate into English.",
            },
        )
        assert_ok(update_settings.status_code, "PUT /api/v1/settings/llm")
        print("[OK] /api/v1/settings/llm (update)")

        for modality, media_base64, mime in [
            ("image", png_1x1, "image/png"),
            ("audio", wav_stub, "audio/wav"),
            ("video", mp4_stub, "video/mp4"),
        ]:
            resp = client.post(
                "/api/v1/llm/process",
                json={
                    "modality": modality,
                    "src_lang": "zh",
                    "tgt_lang": "en",
                    "text": "请输出关键信息。",
                    "media_base64": media_base64,
                    "media_mime_type": mime,
                },
            )
            assert_ok(resp.status_code, f"POST /api/v1/llm/process ({modality})")
            result = resp.json()["result"]
            assert_non_empty(result["translation"], f"modality={modality}")
            print(
                f"[OK] modality={modality:<5} ready={str(result['ready']):<5} "
                f"translation={result['translation'][:48]}"
            )

        text_modality = client.post(
            "/api/v1/llm/process",
            json={
                "modality": "text",
                "text": "机器翻译正在快速发展",
                "src_lang": "zh",
                "tgt_lang": "en",
            },
        )
        assert_ok(text_modality.status_code, "POST /api/v1/llm/process (text)")
        assert_non_empty(text_modality.json()["result"]["translation"], "modality=text")
        print("[OK] modality=text")

    print("\nAcceptance test passed.")


if __name__ == "__main__":
    main()
