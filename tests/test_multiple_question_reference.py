"""Execute the skill's mixed-question examples with the published SDK."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest
from tazo import AsyncTazo, Tazo

REFERENCE = Path(__file__).resolve().parents[1] / "skills/tazo/references/multiple-questions.md"


@pytest.mark.parametrize("max_questions", [1, 10])
def test_reference_uploads_all_question_ids_or_stops_before_inference(
    monkeypatch, tmp_path, capsys, max_questions
):
    blocks = re.findall(r"```python\n(.*?)```", REFERENCE.read_text(), re.S)
    namespace = {}
    exec(compile(blocks[0], str(REFERENCE), "exec"), namespace)
    monkeypatch.chdir(tmp_path)
    sample = REFERENCE.parents[1] / "assets/weather.wav"
    (tmp_path / "request.wav").write_bytes(sample.read_bytes())
    submitted = []

    def handle(request):
        if request.url.path == "/v1/models":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "id": "tazo-large",
                            "display_name": "Large",
                            "description": "Test",
                            "contract": "typed-decisions-v1",
                            "ready": True,
                            "capabilities": {
                                "question_types": ["choice", "noul"],
                                "max_questions": max_questions,
                                "max_choice_options": 32,
                                "max_audio_seconds": None,
                            },
                        }
                    ]
                },
            )
        assert request.url.path == "/v1/decisions"
        boundary = request.headers["Content-Type"].split("boundary=")[1]
        parts = request.read().split(f"--{boundary}".encode())
        payload = next(part for part in parts if b'name="request"' in part)
        payload = json.loads(payload.split(b"\r\n\r\n", 1)[1].strip())
        assert payload["questions"] == namespace["questions"]
        submitted.append(payload)
        return httpx.Response(
            200,
            json={
                "id": "dec_reference",
                "model": "tazo-large",
                "answers": {
                    "action": {
                        "type": "choice",
                        "choice": "get_weather",
                        "confidence": 0.9,
                        "probabilities": {"get_weather": 0.9, "NO_TOOL": 0.1},
                    },
                    "asking_question": {"type": "noul", "noul": 0.98},
                },
                "usage": {"audio_seconds": 1.267875},
                "elapsed_ms": 5,
            },
        )

    transport = httpx.MockTransport(handle)
    namespace["Tazo"] = lambda: Tazo(
        api_key="test-only", http_client=httpx.Client(transport=transport)
    )
    namespace["AsyncTazo"] = lambda: AsyncTazo(
        api_key="test-only", http_client=httpx.AsyncClient(transport=transport)
    )
    # Both forms reuse the same full question map and capability preflight.
    if max_questions == 1:
        with pytest.raises(RuntimeError, match="does not support"):
            exec(compile(blocks[1], str(REFERENCE), "exec"), namespace)
        exec(compile(blocks[2], str(REFERENCE), "exec"), namespace)
        with pytest.raises(RuntimeError, match="does not support"):
            asyncio.run(namespace["decide"]())
        assert not submitted
    else:
        exec(compile(blocks[1], str(REFERENCE), "exec"), namespace)
        exec(compile(blocks[2], str(REFERENCE), "exec"), namespace)
        asyncio.run(namespace["decide"]())
        assert len(submitted) == 2
        output = capsys.readouterr().out
        assert output.count("action get_weather") == 2
        assert output.count("asking_question probability of true: 0.98") == 2
