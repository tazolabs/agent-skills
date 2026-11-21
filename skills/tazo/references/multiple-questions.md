# Several decisions from one audio input

Use one upload or streaming session for independent questions about the same
audio and shared state. Discover readiness, `max_questions`, `question_types`,
and choice limits first. Production Tazo Large currently supports ten questions
with mixed `choice` and `noul` types in India and the US. The tested Python SDK
is **0.1.5**; 0.1.4 already supports this request shape. Preserve a compatible
project environment and its dependency manager.

## One question map, two answer types

The following two upload examples share this setup:

```python
from pathlib import Path

from tazo import AsyncTazo, Tazo
from tazo.types import ChoiceAnswer, NoulAnswer, QuestionsInput

state = "Listen to the spoken request."
questions: QuestionsInput = {
    "action": {
        "type": "choice",
        "instructions": "Select the appropriate action.",
        "criteria": {
            "get_weather": "The speaker requests weather information.",
            "NO_TOOL": "No weather tool is needed.",
        },
    },
    "asking_question": {
        "type": "noul",
        "instructions": "The speaker is asking a question.",
    },
}


def check_model(models):
    model = next((m for m in models.models if m.id == "tazo-large"), None)
    if model is None or not model.ready:
        raise RuntimeError("Tazo Large is not ready on this deployment.")
    caps = model.capabilities
    if caps.max_questions < len(questions) or not {"choice", "noul"}.issubset(caps.question_types):
        raise RuntimeError("This deployment does not support these questions.")
    if caps.max_choice_options is not None and caps.max_choice_options < 2:
        raise RuntimeError("This deployment does not support the requested choices.")


def show_answers(result):
    if set(result.answers) != set(questions):
        raise RuntimeError("The result is missing a requested answer.")
    for question_id, answer in result.answers.items():
        if isinstance(answer, ChoiceAnswer):
            print(question_id, answer.choice, answer.confidence, answer.probabilities)
        elif isinstance(answer, NoulAnswer):
            print(question_id, "probability of true:", answer.noul)
```

Synchronous upload:

```python
with Tazo() as client:
    check_model(client.models.list())
    result = client.decisions.create(
        audio=Path("request.wav"),
        model="tazo-large",
        state=state,
        questions=questions,
    )
    show_answers(result)
```

Or asynchronous upload, using the same setup:

```python
async def decide():
    async with AsyncTazo() as client:
        check_model(await client.models.list())
        result = await client.decisions.create(
            audio=Path("request.wav"),
            model="tazo-large",
            state=state,
            questions=questions,
        )
        show_answers(result)
        return result
```

Use `asyncio.run(decide())` in a standalone script or `await decide()` in an
existing loop. A noul answer is a probability, not a selected choice or an
automatically thresholded boolean. Confidence is the chosen option's
probability, not an additional calibrated guarantee.

## Streaming and custom triggers

Pass this complete question map to either client's `decisions.stream()`.
Use the concurrent sending/receiving pattern in [streaming.md](streaming.md).
For each `decision.updated` or `decision.finalized`, call `show_answers(event)`;
each event contains the complete answer map for its audio window. Keep a single
event consumer. Only treat a finalized event as the final decision.

All questions in that session share the same scope and evaluation timing.
To evaluate cumulative audio, explicitly select `audio_scope="turn"`.
For manual triggers, additionally set `evaluation_mode="manual"`, omit the
interval, and commit an already-sent source-sample range. One accepted commit
returns one finalized event with all answers for that range. Keep receiving
while audio arrives, wait for the final event before another ordered,
nonoverlapping commit, and obey numeric duration and rolling retention limits.
`finish()` does not infer on an uncommitted manual tail.

Use separate sessions for different scopes or timing. Use a later request for
a question that depends on an earlier answer; simultaneous questions do not
receive each other's outputs as context.

## Limits and verification

All questions share one request-text budget, including state, instructions and
criteria across the map. Adding questions does not multiply the audio charge.
Never silently drop questions, truncate input or split work to bypass a limit.
One operation key applies to the entire uploaded request; reuse it only with
identical input. Disconnected streams are not automatically replayed.

With the bundled weather recording, expect `action` to select `get_weather` and
inspect `asking_question.noul` as a probability. Arbitrary audio needs its own
semantic expectations. The one-question verification helper does not check
multiple-question behavior.

For a complete runnable sync/async upload and streaming check, use
[`examples/multiple_questions.py` in the public SDK](https://github.com/tazolabs/tazo-sdk/blob/main/examples/multiple_questions.py)
from a checkout matching the tested release (`sdk-v0.1.5`). Its `--mode stream`
and `--async-client` flags cover the four combinations. Each run submits real
inference. The [Mintlify guide](https://docs.tazolabs.com/sdk/python/multiple-questions)
documents the same request and complete response map.
