---
name: tazo
description: >-
  Install and sign in to Tazo-MCP in Claude or ZCode, use its audio decision
  tools, or build integrations with the Tazo Python SDK. Use for Tazo MCP setup,
  uploaded audio decisions, multiple questions, streaming, model discovery, and verification.
license: Apache-2.0
metadata:
  author: tazolabs
  version: "1.3.0"
  sdk-version: "0.1.5"
  api-version: "v1"
---

# Tazo audio decisions

Tazo uses audio plus text context and questions to return structured decisions.

## Choose the requested connection

- **Install, connect, or sign in to the MCP:** use
  [the MCP setup reference](references/mcp-setup.md). Production is
  `https://mcp.tazolabs.com/mcp`, named **Tazo-MCP**, using Streamable HTTP.
  Add the server for the requested client, let its native OAuth flow open Tazo
  sign-in, then check health and models through that client's tools. Email,
  Google, and existing platform sessions use the normal Tazo sign-in.
  The user completes sign-in; the agent handles installation. Do not ask the
  user to edit configuration or obtain an API key, client ID, or client secret.
- **Use an already connected MCP:** discover models with its native tools.
  Hosted audio tools take an account-owned `audio_id`; a file-capable agent can
  prepare and upload a WAV before analysis. Read the MCP reference for that flow.
- **Build application code with the SDK:** follow the SDK sections below.
  SDK API-key setup and verification helpers apply to this mode only.

Preserve a user-supplied endpoint and the selected application. Claude Code
uses its CLI; Claude web/Desktop connectors use account settings; ZCode uses
its MCP settings or the bundled agent installer. These are separate client
registrations. A healthy HTTP endpoint alone is not a verified installation.

## Python SDK integration

Use the public Python package `tazo-sdk` (import `tazo`) for application code:

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
Read [references/multiple-questions.md](references/multiple-questions.md) when
several decisions use the same audio, including mixed choice/noul answers.
Use [references/troubleshooting.md](references/troubleshooting.md) for errors,
idempotency recovery, and verification failures.
Read [references/updates.md](references/updates.md) when installing or updating
the skill, or when the user asks about automatic updates.

## Set up and discover

- Use Python 3.11+ and the project's dependency manager or virtual environment.
  The examples and helpers are tested with the published `tazo-sdk==0.1.5`.
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

For several independent decisions about the same audio, send one `questions`
map in one upload or session, within the discovered `max_questions`. Production
Tazo Large currently supports up to ten mixed `choice`/`noul` questions. Inspect
every returned answer by question ID and type; do not read only `action` or
assume every answer has `choice`. Questions share state, the audio window, and
streaming evaluation timing. One manual commit evaluates all questions on its
selected range. Use separate sessions for different scopes/timing, or a later
request when a question depends on an earlier answer. Text budgets apply across
all questions; adding questions does not multiply the audio usage charge.

For streaming, send raw mono 16 kHz signed little-endian PCM16, consume events
concurrently with sending, obey `session.ready` limits, and observe
`decision.finalized` followed by `session.closed` for a completed verification.
SDK 0.1.4 defaults to `audio_scope="chunk"`: results cover new audio windows,
and `max_turn_audio_ms=None` means no cumulative duration cap. Choose
`audio_scope="turn"` explicitly for a final decision over the whole recording;
obey any numeric duration limit. Continue pacing audio and respecting the
per-message limit in either mode.
Never replay a disconnected stream automatically.

For VAD, utterance boundaries, or custom triggers, use SDK 0.1.4+ with
`audio_scope="turn", evaluation_mode="manual"` and omit the interval. Trigger
`commit(audio_start_sample=..., audio_end_sample=...)` only for audio already
sent. Bounds are absolute source samples from connection start, end exclusive;
at 16 kHz, multiply seconds by 16,000. Keep receiving while audio continues,
wait for `decision.finalized` before the next ordered, nonoverlapping commit,
and respect `session.ready.audio_retention_ms` and the selected-range duration
limit. Manual `finish()` does not evaluate uncommitted audio. See the streaming
reference for sync/async examples and error handling.

Resolve the helpers relative to **this installed skill directory**, not the
user's working directory. Use its absolute path with the project's Python:

```sh
python /absolute/path/to/tazo/scripts/check_setup.py
python /absolute/path/to/tazo/scripts/verify.py --models tazo-large --expected-choice get_weather
```

`check_setup.py` checks the local installation, key presence, health, and model
discovery without submitting audio. `--offline` checks only local prerequisites.
`verify.py` uses the bundled weather recording by default and runs sync upload,
sync streaming, async upload, and async streaming for ready models advertising
choice support. It discovers models by default; production currently exposes
`tazo-large`. `--models tazo-large` explicitly selects that model and four cases. `--modes sync-upload`
limits it to one mode per selected model. `--help` lists all options, including
custom audio, API origin, expected choice, and a JSON report.
The helper explicitly uses turn mode to check final coverage of the full sample.
To check custom triggers, select `--modes sync-manual-stream async-manual-stream`.
These additional modes check the returned source sample range and reject
periodic decisions; the default four modes stay unchanged.
These helpers ask one weather-routing question. For multiple-question
verification, use the reference's mixed-question example and check every answer;
a passing single-question helper run does not verify multiple-question behavior.

Run the operations that satisfy the user's request. Use the full verification
suite when the user asks to check all modes; each case submits real inference
and streaming can evaluate multiple windows. For an ordinary single decision,
make that decision without automatically running the verification suite.

Check the expected answer only when the recording's meaning is known. The
bundled sample says “What is the weather today?” and should select `get_weather`
for the helper's weather question. A successful transport and valid response
alone do not establish that a model understood arbitrary audio correctly.

Authoritative customer documentation: [Python SDK](https://docs.tazolabs.com/sdk/python/overview).
