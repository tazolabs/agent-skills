# Python SDK: setup and uploaded decisions

Use the existing project's environment and dependency manager. For a new project:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'tazo-sdk==0.1.1'
```

On Windows activate `.venv\Scripts\Activate.ps1`. Python 3.11+ is required.
The package is `tazo-sdk`; the import is `tazo`. Reuse a compatible installed
version rather than replacing a project's lockfile without reason.

The user creates a key at <https://app.tazolabs.com> and sets `TAZO_API_KEY`
outside chat. Bash or Zsh can read it without terminal echo or putting
the secret in command history:

```sh
printf 'Tazo API key: '
read -r -s TAZO_API_KEY
printf '\n'
export TAZO_API_KEY
```

Use the raw key, without a `Bearer ` prefix. Prefer the environment or the
application's secret store over constructor literals. The default API origin
is `https://api.tazolabs.com`; a custom `base_url` must not end in `/v1`.
TestPyPI is a package index, not an API deployment.

## Discovery and health

```python
from tazo import Tazo

with Tazo() as client:
    print(client.health.check().status)
    for model in client.models.list().models:
        print(model.id, model.ready, model.capabilities.model_dump())
```

`health.check()` also returns `status="unavailable"` for the expected HTTP 503
health response. Treat it as an unavailable service. Health alone does not prove
that an authenticated inference request will work.

Choose a ready model and inspect `capabilities.question_types`, `max_questions`,
`max_choice_options`, `requires_no_tool_choice`, `max_audio_seconds`, and
`required_sample_rate_hz`. Do not infer capabilities from the model's name.
The bundled verification targets `tazo-large` and `tazo-small`; general
integrations should use current discovery results.

## Choice decision: sync and async

`state` is shared context (a string, object, or list of strings). `questions`
maps stable question IDs to instructions and answer criteria. Choice criteria
map stable option IDs to descriptions; include `NO_TOOL` when required.

```python
from pathlib import Path

from tazo import AsyncTazo, Tazo
from tazo.types import QuestionsInput

questions: QuestionsInput = {
    "action": {
        "type": "choice",
        "instructions": "Select get_weather for weather requests; otherwise NO_TOOL.",
        "criteria": {
            "get_weather": "The speaker requests weather information.",
            "NO_TOOL": "The speaker is not requesting weather information.",
        },
    }
}
state = "Route the spoken request to the appropriate action."

with Tazo() as client:
    result = client.decisions.create(
        audio=Path("request.wav"),
        model="tazo-large",  # Verify readiness and capabilities with models.list().
        state=state,
        questions=questions,
    )
    print(result.answers["action"].model_dump())
    print(result.request_id, result.idempotency_key)


async def decide():
    async with AsyncTazo() as client:
        return await client.decisions.create(
            audio=Path("request.wav"),
            model="tazo-large",
            state=state,
            questions=questions,
        )
```

Call `await decide()` inside an existing event loop, or `asyncio.run(decide())`
from a standalone script. Do not call `asyncio.run()` inside an active loop.

Uploaded audio accepts a `Path`, bytes, or a binary file. For bytes, set
`filename="request.wav"` and `content_type="audio/wav"`. A file is read from its
current position; seekable files have their position restored and stay open.
The SDK snapshots at most 16 MiB for a stable upload across retries. The server
and chosen model also impose duration and format limits. Mono 16 kHz PCM16 WAV
is a useful common input for testing both upload and streaming. The helper is
intentionally limited to this format; it does not transcode a user's recording.

A choice answer has `choice`, `probabilities`, and `confidence`. The confidence
is the selected choice's probability, not a separate calibrated guarantee.
`result.model_dump(mode="json")` serializes the wire result. `request_id` and
`idempotency_key` are SDK metadata excluded from that dump; capture them
explicitly when needed. The SDK preserves additive response fields.

## Noul: supported models only

When discovery advertises `noul`, ask for the probability that a statement is true:

```python
questions = {
    "weather_requested": {
        "type": "noul",
        "instructions": "The speaker requests weather information.",
    }
}
```

The answer's `noul` field is a number in [0, 1]. Optional criteria must have
exactly the IDs `true` and `false`. Do not silently turn this probability into
a yes/no answer without choosing a threshold appropriate to the user's task.

## Operation recovery

The SDK reuses one generated idempotency key and audio snapshot for its bounded
HTTP retries. To survive process interruption or recover a pending upload,
generate and persist a caller-supplied key **before** submitting; reuse it with
identical audio, model, state, and questions for that same operation.

`DecisionPendingError` means accepted work may still complete. Retain the key
and original input, honor `retry_after`, and resume within a bounded recovery
policy. Do not start a new operation key for the same uncertain request or
reuse a key with changed input. Cancellation is not cancellation of durable
server work. See [troubleshooting.md](troubleshooting.md).

Full reference: <https://docs.tazolabs.com/sdk/python/overview>.
