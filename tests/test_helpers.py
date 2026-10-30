from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import wave
from pathlib import Path

import pytest
import yaml
from conftest import TEST_KEY
from tazo import AsyncTazo, Tazo
from tazo.streaming import AsyncStreamingSession, StreamingSession
from tazo.types import SessionReady

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "tazo"
SCRIPTS = SKILL / "scripts"


def run_helper(script, *args, cwd=None, key=TEST_KEY):
    env = {**os.environ, "TAZO_API_KEY": key}
    # Credentials for the user's production environment are never needed here.
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


@pytest.fixture
def verification(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("tazo_skill_verify", SCRIPTS / "verify.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setenv("TAZO_API_KEY", TEST_KEY)
    return module


def test_skill_metadata_and_bundled_recording():
    frontmatter = (SKILL / "SKILL.md").read_text().split("---", 2)[1]
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == SKILL.name
    assert 0 < len(metadata["description"]) <= 1024
    assert all(isinstance(v, str) for v in metadata["metadata"].values())
    with wave.open(str(SKILL / "assets" / "weather.wav")) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16000)
        assert audio.getnframes() > 0


def test_setup_without_key_checks_health_without_inference(fake_api, tmp_path):
    result = run_helper("check_setup.py", "--base-url", fake_api.base_url, cwd=tmp_path, key="")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Health: ok" in result.stdout
    assert fake_api.calls == [("GET", "/healthz")]


def test_offline_setup_never_contacts_api(fake_api):
    result = run_helper("check_setup.py", "--offline", "--base-url", fake_api.base_url)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not fake_api.calls
    assert TEST_KEY not in result.stdout + result.stderr


def test_setup_lists_models_without_inference(fake_api):
    result = run_helper("check_setup.py", "--base-url", fake_api.base_url)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "tazo-large" in result.stdout and "tazo-small" in result.stdout
    assert fake_api.calls == [("GET", "/healthz"), ("GET", "/v1/models")]
    assert TEST_KEY not in result.stdout + result.stderr


@pytest.mark.parametrize("failure", ["health", "key", "models"])
def test_setup_failures(fake_api, failure):
    if failure == "health":
        fake_api.health = "unavailable"
    elif failure == "models":
        fake_api.ready = False
    result = run_helper(
        "check_setup.py",
        "--base-url",
        fake_api.base_url,
        key="invalid-test-key" if failure == "key" else TEST_KEY,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert not fake_api.uploads and not fake_api.audio_messages


def test_all_eight_modes_use_installed_sdk_from_unrelated_directory(fake_api, tmp_path):
    report = tmp_path / "report.json"
    result = run_helper(
        "verify.py",
        "--base-url",
        fake_api.base_url,
        "--timeout",
        "5",
        "--expected-choice",
        "get_weather",
        "--output",
        report,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(report.read_text())
    assert data["sdk_version"] == "0.1.2"
    assert data["passed"] == data["total"] == 8
    assert {(case["model"], case["mode"]) for case in data["results"]} == {
        (model, mode)
        for model in ("tazo-large", "tazo-small")
        for mode in ("sync-upload", "sync-stream", "async-upload", "async-stream")
    }
    assert all(
        case["decision"]["answers"]["action"]["choice"] == "get_weather" for case in data["results"]
    )
    assert len(fake_api.uploads) == 4
    assert fake_api.stream_scopes == ["turn"] * 4
    assert all(audio.startswith(b"RIFF") for audio in fake_api.uploads)
    assert fake_api.audio_messages
    assert all(len(frame) <= 998 and len(frame) % 2 == 0 for frame in fake_api.audio_messages)
    assert not any(frame.startswith(b"RIFF") for frame in fake_api.audio_messages)
    assert {path for _, path in fake_api.calls} == {
        "/healthz",
        "/v1/models",
        "/v1/decisions",
        "/v1/decisions/stream",
    }
    assert TEST_KEY not in result.stdout + result.stderr + report.read_text()


@pytest.mark.parametrize("limit", [None, 65000, 30000])
def test_verification_chunks_honor_nullable_and_numeric_duration_limits(verification, limit):
    pcm = b"\x01\x00" * (16000 * 65)
    audio = verification.Audio(filename="long.wav", wav=b"", pcm=pcm)
    ready = SessionReady(
        type="session.ready",
        session_id="sess_test",
        sequence=1,
        model="tazo-large",
        config_revision=1,
        input_audio={"encoding": "pcm_s16le", "sample_rate_hz": 16000, "channels": 1},
        evaluation_interval_ms=1000,
        max_turn_audio_ms=limit,
        max_audio_message_bytes=998,
        audio_scope="chunk" if limit is None else "turn",
    )
    if limit is not None and limit < audio.duration_ms:
        with pytest.raises(ValueError, match="turn limit"):
            list(audio.chunks(ready))
    else:
        chunks = list(audio.chunks(ready))
        assert b"".join(chunks) == pcm
        assert all(0 < len(chunk) <= 998 and len(chunk) % 2 == 0 for chunk in chunks)


@pytest.mark.parametrize("mode", ["sync-upload", "async-upload"])
def test_mode_selection_and_wrong_semantic_answer(fake_api, tmp_path, mode):
    fake_api.choice = "NO_TOOL"
    report = tmp_path / "result.json"
    result = run_helper(
        "verify.py",
        "--base-url",
        fake_api.base_url,
        "--models",
        "tazo-small",
        "--modes",
        mode,
        "--expected-choice",
        "get_weather",
        "--output",
        report,
    )
    assert result.returncode == 1
    data = json.loads(report.read_text())
    assert data["total"] == 1 and data["passed"] == 0
    assert len(fake_api.uploads) == 1 and not fake_api.audio_messages
    assert "Expected get_weather, received NO_TOOL" in data["results"][0]["error"]


@pytest.mark.parametrize("mode", ["sync-stream", "async-stream"])
@pytest.mark.parametrize("failure", ["disconnect", "missing-final"])
def test_stream_requires_final_and_graceful_closure(fake_api, mode, failure):
    fake_api.stream_failure = failure
    result = run_helper(
        "verify.py",
        "--base-url",
        fake_api.base_url,
        "--models",
        "tazo-large",
        "--modes",
        mode,
        "--timeout",
        "5",
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Summary: 0/1 passed" in result.stdout


@pytest.mark.parametrize("status,code", [(429, "rate_limited"), (409, "decision_pending")])
def test_failure_reports_redact_echoed_credentials(fake_api, tmp_path, status, code):
    fake_api.upload_error = (status, code)
    report = tmp_path / "errors.json"
    result = run_helper(
        "verify.py",
        "--base-url",
        fake_api.base_url,
        "--models",
        "tazo-large",
        "--modes",
        "sync-upload",
        "--output",
        report,
    )
    assert result.returncode == 1
    combined = result.stdout + result.stderr + report.read_text()
    assert TEST_KEY not in combined
    assert "[REDACTED]" in combined


def test_bad_audio_and_report_cannot_overwrite_input(tmp_path):
    audio = tmp_path / "bad.wav"
    audio.write_bytes(b"not audio")
    result = run_helper("verify.py", "--audio", audio)
    assert result.returncode == 2
    audio.write_bytes((SKILL / "assets" / "weather.wav").read_bytes())
    before = audio.read_bytes()
    result = run_helper("verify.py", "--audio", audio, "--output", audio)
    assert result.returncode == 2
    assert audio.read_bytes() == before


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@example.com",
        "https://example.com/v1",
        "https://example.com/?secret=value",
    ],
)
def test_invalid_origins_rejected_without_echoing_credentials(url):
    result = run_helper("check_setup.py", "--offline", "--base-url", url)
    assert result.returncode == 2
    assert url not in result.stdout + result.stderr


def test_sync_sender_failure_stops_worker(fake_api, verification, monkeypatch):
    def fail(self, audio):
        raise RuntimeError("producer_failed")

    monkeypatch.setattr(StreamingSession, "send_audio", fail)
    with Tazo(api_key=TEST_KEY, base_url=fake_api.base_url) as client:
        with pytest.raises(RuntimeError, match="producer_failed"):
            verification.sync_stream(
                client, verification.load_audio(verification.SAMPLE_AUDIO), "tazo-large", 2
            )
    assert not any(t.name == "tazo-audio-sender" for t in threading.enumerate())


def test_async_receiver_failure_cancels_sender(fake_api, verification, monkeypatch):
    import asyncio

    async def fail(self):
        raise RuntimeError("receiver_failed")

    monkeypatch.setattr(AsyncStreamingSession, "__anext__", fail)

    async def run():
        async with AsyncTazo(api_key=TEST_KEY, base_url=fake_api.base_url) as client:
            with pytest.raises(ExceptionGroup) as error:
                await verification.async_stream(
                    client, verification.load_audio(verification.SAMPLE_AUDIO), "tazo-large", 2
                )
            assert "receiver_failed" in verification.error_message(error.value)
        assert not [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        ]

    asyncio.run(run())
