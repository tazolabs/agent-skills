# Streaming with the Python SDK

Streaming uses the same `model`, `state`, and `questions` as uploaded decisions,
but requires **exactly one question per session configuration**. Choose its
type from current model capabilities. The SDK handles WebSocket authentication
and protocol messages; use the public `decisions.stream()` interface.

## Audio and lifecycle

1. Enter the streaming context. The SDK sends `session.start` and waits for
   `session.ready`. Inspect `session.ready` for the accepted format, maximum
   turn duration, maximum bytes per audio message, and evaluation interval.
2. Send binary raw signed little-endian PCM16, mono, 16 kHz. There are 32,000
   bytes per second. Do not send WAV headers, base64, stereo, or encoded MP3.
   Frames must be nonempty, even-length, and within the negotiated limits.
3. Send and receive concurrently: one sender and **one** event consumer. Sync
   applications use a sender thread; async applications use concurrent tasks.
4. `commit()` completes a turn. Consume `decision.finalized` before another
   turn. `decision.updated` is provisional; use its reported audio window.
5. After the last final decision, call `finish()` and keep consuming until
   `session.closed`. Context exit closes the socket even on errors.

`audio_scope="turn"` evaluates cumulative turn audio; `"chunk"` evaluates new
audio windows. Cumulative windows overlap, so do not sum their audio usage as
unique recording duration. Each evaluation may consume account capacity.
Omit `evaluation_interval_ms` for the server default, or use an integer from
100 through 30,000 ms. Respect the accepted ready limits and service feedback;
do not hardcode account quotas.

Between completed turns, `session.update(state=..., questions=...)` replaces
both context and question. Consume `session.updated` before sending more audio.
A session's model stays fixed. Start a new session to change models.

## Working implementations

[../scripts/verify.py](../scripts/verify.py) includes complete `sync_stream`
and `async_stream` implementations with producer/receiver cleanup, pacing,
negotiated chunk limits, final audio coverage, and graceful closure checks.
Use these functions as a reference when creating the user's integration;
their question is specifically a weather-routing smoke test.

For async code, the core pattern is:

```python
import asyncio
from tazo import AsyncTazo
from tazo.types import DecisionEvent, ErrorEvent, SessionClosed


async def stream_pcm(state, questions, pcm_chunks):
    final = None
    closed = False
    async with AsyncTazo() as client:
        async with (
            asyncio.timeout(180),
            client.decisions.stream(
                state=state, questions=questions, audio_scope="turn"
            ) as session,
        ):

            async def send():
                for chunk in pcm_chunks(session.ready):
                    await session.send_audio(chunk)
                    await asyncio.sleep(len(chunk) / 32000)
                await session.commit()

            async def receive():
                nonlocal final, closed
                async for event in session:
                    if isinstance(event, ErrorEvent):
                        raise RuntimeError(event.error.code)
                    if isinstance(event, DecisionEvent) and event.type == "decision.finalized":
                        final = event
                        await session.finish()
                    if isinstance(event, SessionClosed):
                        closed = True
                if final is None or not closed:
                    raise RuntimeError("Incomplete streaming decision")

            async with asyncio.TaskGroup() as group:
                group.create_task(send())
                group.create_task(receive())
    return final
```

The `pcm_chunks` callable receives `session.ready` and must check total duration
and split PCM at even byte boundaries no larger than `max_audio_message_bytes`.
For a WAV source, `tazo.wav_chunks(path, chunk_ms=100)` strips the header and
validates mono 16 kHz PCM16. It does not pace or resample. Ensure its chunks fit
ready limits; the verification helper demonstrates adaptive chunking.

In sync code, the receiver must keep running while the sender thread sends
and commits. On either side's failure, stop the sender, close the session to
unblock the receiver, and join the thread. Keep socket and client lifetimes
inside their context managers. Do not collect unbounded audio/event queues.

## Errors and deadlines

`event_timeout` bounds the wait for each event, not necessarily the entire
session. Use an application deadline as needed. Fatal protocol errors raise
`StreamingError`; recoverable errors arrive as `ErrorEvent`. Handle unknown
additive event types without assuming they are final results.

An interrupted stream is not resumable by the SDK. It never reconnects or
replays audio automatically. Report whether a final result was observed;
starting another session is new inference work and should follow the user's
task and retry policy. See [troubleshooting.md](troubleshooting.md).
