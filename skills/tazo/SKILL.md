---
name: tazo
description: >-
  Build, run, and troubleshoot integrations with Tazo audio decision models using
  the Tazo Python SDK. Use for Tazo setup, decisions from uploaded audio,
  WebSocket streaming decisions, model discovery, and sync or async verification.
license: Apache-2.0
metadata:
  author: tazolabs
  version: "1.0.1"
  sdk-version: "0.1.2"
  api-version: "v1"
---

# Tazo audio decisions

Tazo uses audio plus text context and questions to return structured decisions.
Use the public Python package `tazo-sdk` (import `tazo`). This skill covers only:

| Operation | SDK call | Public API |
| --- | --- | --- |
| Uploaded audio decision | `client.decisions.create(...)` | `POST /v1/decisions` |
| Streaming decision | `client.decisions.stream(...)` | WebSocket `/v1/decisions/stream` |
| Model discovery | `client.models.list()` | `GET /v1/models` |
| Health | `client.health.check()` | `GET /healthz` |

## Work from the user's request

Determine the recording or audio source, the decision to make, and whether the
integration needs uploads or streaming and sync or async execution. Preserve the
user's project environment, model, API origin, and question IDs. For unspecified
choices, a synchronous upload is a useful starting point for a recorded file;
prefer async streaming in an existing async application.

Read [references/python-sdk.md](references/python-sdk.md) for installation,
authentication, uploaded decisions, capabilities, and result handling. Read
[references/streaming.md](references/streaming.md) when implementing streaming.
Use [references/troubleshooting.md](references/troubleshooting.md) for errors,
idempotency recovery, and verification failures.

## Set up and discover

- Use Python 3.11+ and the project's dependency manager or virtual environment.
  The examples and helpers are tested with `tazo-sdk==0.1.2`.
- Read the raw key from `TAZO_API_KEY`; the SDK adds `Bearer`. Keys are created
  by the user in the [Tazo console](https://app.tazolabs.com). If missing, have
  the user set it in their terminal or secret store. Do not request a key in chat,
  embed it in source, or print its value.
- Default origin: `https://api.tazolabs.com`. Pass a user-supplied API origin as
  `base_url` without appending `/v1`; the SDK derives the WebSocket URL.
- Check health and discover models before choosing capabilities. Check readiness,
  supported question types, question/choice counts, audio limits, and whether
  `NO_TOOL` is required. Use `noul` only when the model advertises it.
- Health needs no key. Model discovery and decisions need a key. Account and key
  management happen in the console; they are outside this public SDK.

## Execute and verify

Use `Tazo` or `AsyncTazo` as a context manager. For a decision, supply `state`
(shared text context) and a `questions` map keyed by stable question IDs. Return
the typed answer and useful request metadata; preserve the distinction between
choice confidence and a `noul` probability. Model outputs are decisions, not
transcripts or executions of tools named in the choices.

For streaming, send raw mono 16 kHz signed little-endian PCM16, consume events
concurrently with sending, obey `session.ready` limits, and observe
`decision.finalized` followed by `session.closed` for a completed verification.
SDK 0.1.2 defaults to `audio_scope="chunk"`: results cover new audio windows,
and `max_turn_audio_ms=None` means no cumulative duration cap. Choose
`audio_scope="turn"` explicitly for a final decision over the whole recording;
obey any numeric duration limit. Continue pacing audio and respecting the
per-message limit in either mode.
Never replay a disconnected stream automatically.

Resolve the helpers relative to **this installed skill directory**, not the
user's working directory. Use its absolute path with the project's Python:

```sh
python /absolute/path/to/tazo/scripts/check_setup.py
python /absolute/path/to/tazo/scripts/verify.py --models tazo-large --expected-choice get_weather
```

`check_setup.py` checks the local installation, key presence, health, and model
discovery without submitting audio. `--offline` checks only local prerequisites.
`verify.py` uses the bundled weather recording by default and runs sync upload,
sync streaming, async upload, and async streaming for both `tazo-large` and
`tazo-small`. `--models tazo-large` limits it to four cases. `--modes sync-upload`
limits it to one mode per selected model. `--help` lists all options, including
custom audio, API origin, expected choice, and a JSON report.
The helper explicitly uses turn mode to check final coverage of the full sample.

Run the operations that satisfy the user's request. Use the full verification
suite when the user asks to check all modes; each case submits real inference
and streaming can evaluate multiple windows. For an ordinary single decision,
make that decision without automatically running the verification suite.

Check the expected answer only when the recording's meaning is known. The
bundled sample says “What is the weather today?” and should select `get_weather`
for the helper's weather question. A successful transport and valid response
alone do not establish that a model understood arbitrary audio correctly.

Authoritative customer documentation: [Python SDK](https://docs.tazolabs.com/sdk/python/overview).
