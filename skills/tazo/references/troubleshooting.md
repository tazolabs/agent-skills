# Troubleshooting and verification

Use `scripts/check_setup.py --offline` for local prerequisites, then
`scripts/check_setup.py` for health and authenticated model discovery. Neither
submits audio. Resolve script paths relative to the installed skill directory.

| Symptom | What to check or do |
| --- | --- |
| `ModuleNotFoundError: tazo` | Use the project's Python; install `tazo-sdk` in that environment. `python -m pip show tazo-sdk` helps identify a mismatch. |
| Missing key / `AuthenticationError` | Have the user set raw `TAZO_API_KEY` from the console, without `Bearer `. Never ask them to paste it into chat. |
| `PermissionDeniedError` | Check the account/key's access in the console. |
| Health `unavailable` | Wait or investigate service availability before inference. Health success alone does not establish model readiness. |
| `NotFoundError` / model not ready | Rediscover via `models.list()` and inspect readiness and capabilities. |
| `InvalidRequestError` | Check question IDs/types/counts, choice options, required `NO_TOOL`, and audio format/duration. |
| `RequestTooLargeError` | Keep uploads within 16 MiB and the model's audio limit. Use shorter input or an appropriate streaming design. |
| `RateLimitError` | Honor `retry_after`; reduce concurrency/evaluation frequency. Keep retries bounded. Limits apply to the target account and model. |
| `DecisionPendingError` | Retain `idempotency_key` and the exact original request. Retry that operation later within a bounded policy. |
| `IdempotencyConflictError` | A key was reused with different input. Recover the original request; use a new key only for a genuinely new operation. |
| `ConnectionError` / `TimeoutError` | Check origin/network/time budgets. An upload may have been accepted; recover using its retained key and original input. |
| `StreamingError` / early disconnect | Inspect code/close code and whether a final result arrived. Do not automatically replay audio. |
| `ProtocolError` | Capture sanitized request metadata and SDK version; compare the supported contract and report the mismatch. |
| Old SDK rejects `max_turn_audio_ms: null`, or helper compares `None` with a number | Upgrade to SDK 0.1.4 and update the skill. A `None` streaming duration limit means no cumulative cap; retain numeric limit checks. |
| Final streaming decision covers only the latest window | SDK 0.1.4 defaults to chunk mode. Use `audio_scope="turn"` for a whole-recording decision. |
| `commit()` rejects sample bounds or manual stream arguments | Upgrade the project's Python dependency to SDK 0.1.4+ and update the skill separately. Manual mode requires turn scope and no interval. |
| Manual stream sends no decisions | This is expected until an explicit sample-range commit. `finish()` does not evaluate an uncommitted manual tail. |
| `audio_range_not_received` / `audio_range_expired` | Use absolute source sample bounds within audio already sent and still retained; inspect `audio_retention_ms`. Never reset the source clock after a final. |
| `invalid_audio_range` / `turn_finalizing` | Use ordered, nonoverlapping ranges and wait for `decision.finalized` before the next commit. Audio may continue while inference runs. |
| Private package index returns 401 | Test with a command-scoped clean pip configuration below; preserve the user's global configuration. |

```sh
env -u PIP_EXTRA_INDEX_URL -u PIP_INDEX_URL PIP_CONFIG_FILE=/dev/null \
  python -m pip install --index-url https://pypi.org/simple/ 'tazo-sdk==0.1.4'
```

For SDK exceptions, retain class, `code`, `status_code`, `request_id`,
`idempotency_key`, `retryable`, and `retry_after` when useful. `StreamingError`
also has `close_code`. Avoid logging keys, authorization payloads, or audio.
Share decisions/prompts only when appropriate to the user's task.

## Verify all four client modes

From the project's Python, with `TAZO_API_KEY` already configured:

```sh
python /absolute/path/to/tazo/scripts/verify.py \
  --expected-choice get_weather \
  --output ./tazo-verification.json
```

This uses the bundled 1.27-second weather WAV and runs four modes for every
discovered ready model supporting choice questions, sequentially. Production
currently exposes `tazo-large`, so a successful default run prints
`Summary: 4/4 passed`. A deployment with two suitable models runs eight cases.
It validates health/discovery, response IDs/options,
streaming final audio coverage, closure, and the expected choice. It submits
real inference work. Do not run it automatically for every integration edit.
Streaming cases explicitly select turn mode for full-recording coverage;
they do not use the SDK's default chunk mode.

To check manual triggers as well, run with
`--modes sync-manual-stream async-manual-stream`. This adds two optional modes
per model; it does not change the default four modes per model. The manual checks
also validate the final `input_audio_range` and reject periodic decisions.

For a smaller or custom check:

```sh
python /absolute/path/to/tazo/scripts/verify.py \
  --models tazo-large --modes sync-upload --expected-choice get_weather

python /absolute/path/to/tazo/scripts/verify.py \
  --audio ./my-recording.wav --models tazo-large \
  --base-url https://api.tazolabs.com
```

The helper's question always routes weather requests to `get_weather` and
other input to `NO_TOOL`. Omitting `--expected-choice` checks the API flow,
not semantic correctness. Supply an expected choice only when justified by
the input. Probabilities may vary across models and runs.

The helper requires nonempty, uncompressed mono 16 kHz PCM16 WAV, within
16 MiB and advertised model/turn limits. Convert a recording separately when
needed; keep the original. The bundled sample is synthesized speech saying
“What is the weather today?”.

Exit codes: `0` all requested cases passed, `1` setup/API/verification failure,
`2` invalid CLI/local input. A JSON report contains decisions, timings, sanitized
errors, installed SDK details, and pass counts; it excludes key and audio bytes.
Keep reports local or in the user's chosen output location. If a setup check
fails before inference, resolve that failure and rerun the chosen cases.
