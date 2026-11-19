# Tazo agent skills

Teach your coding agent to build and test integrations with Tazo audio decision
models. The `tazo` skill uses the public [Tazo Python SDK](https://pypi.org/project/tazo-sdk/)
for uploaded audio, WebSocket streaming, model discovery, and health checks.
It supports synchronous and asynchronous applications.

## Install in your project

With [Node.js 22.20+](https://github.com/vercel-labs/skills), run from the project
where you want to use Tazo:

```sh
npx skills@latest add tazolabs/agent-skills --skill tazo
```

Select your agent when prompted. To choose explicitly:

```sh
npx skills@latest add tazolabs/agent-skills --skill tazo --agent codex
npx skills@latest add tazolabs/agent-skills --skill tazo --agent claude-code
npx skills@latest add tazolabs/agent-skills --skill tazo --agent cursor
```

Add `--global` to install for your user across projects. Reload the agent's
session if it does not discover the newly installed skill. Agent-specific
invocation varies; Codex supports `$tazo`. The default permits automatic skill
selection for relevant Tazo requests.

There is no separate Tazo npm package to publish or install. `npx` runs the
existing `skills` CLI, which downloads this public GitHub repository. To
manually share the skill, share the entire [`skills/tazo`](skills/tazo) folder
so references, scripts, license, and audio remain available.

## Ask your agent

> Use the Tazo skill to set up this Python project and make a decision from
> `request.wav`. Route weather requests to `get_weather`, otherwise `NO_TOOL`.

> Use Tazo to add async streaming decisions to this application. Discover the
> available models and respect their capabilities and streaming audio limits.

> Use the Tazo skill to verify sync upload, async upload, sync streaming, and
> async streaming with the bundled sample. Save a JSON report locally.

> Use Tazo manual streaming to trigger decisions at VAD utterance boundaries.
> Keep sending audio while inference runs and use absolute sample ranges.

The agent can install the SDK and create integration code in your project. For
live decisions, you need Python 3.11+, network access, and a Tazo API key from
the [Tazo console](https://app.tazolabs.com). Configure the raw key as
`TAZO_API_KEY` in your terminal or secret store; do not paste it into the chat.
The default target is `https://api.tazolabs.com`.

## Run the helpers directly

In your Python 3.11+ environment:

```sh
python -m pip install 'tazo-sdk==0.1.4'
```

For a repository checkout, run from its root:

```sh
python skills/tazo/scripts/check_setup.py --offline
python skills/tazo/scripts/check_setup.py
python skills/tazo/scripts/verify.py \
  --expected-choice get_weather \
  --output ./tazo-verification.json
```

For an installed skill, replace `skills/tazo` with its actual installed path.
The scripts can run from any working directory and find bundled resources
relative to their own location. Use `--help` for all options.

`check_setup.py` checks prerequisites, health, and models; it submits no audio.
With no key, it can still check health. `--offline` makes no network requests
and reports a missing key as an incomplete setup.

`verify.py` discovers ready models supporting choice questions and sends the
bundled weather WAV through four modes for each. Production currently advertises
`tazo-large`, so expect `Summary: 4/4 passed` there with the expected weather
decision. A deployment advertising two suitable models runs eight cases. Cases
run sequentially and submit real inference work; streaming can evaluate multiple
windows. Narrow a run:

```sh
python skills/tazo/scripts/verify.py \
  --models tazo-large --modes sync-upload --expected-choice get_weather
```

Skill version **1.1.1** targets SDK **0.1.4**. The SDK now defaults to chunk
streaming with no cumulative duration cap (`max_turn_audio_ms=None`). Choose
`audio_scope="turn"` explicitly for a final decision over the whole recording;
the verification helper does this. Numeric duration limits, message-size limits,
and real-time pacing still apply where advertised.

SDK 0.1.4 also supports custom triggers: open a stream with
`audio_scope="turn", evaluation_mode="manual"`, omit the evaluation interval,
and commit an explicit source sample range. See the
[streaming reference](skills/tazo/references/streaming.md). Check both clients:

```sh
python skills/tazo/scripts/verify.py --models tazo-large \
  --modes sync-manual-stream async-manual-stream \
  --expected-choice get_weather --output ./tazo-manual-verification.json
```

These two optional modes check committed sample bounds, absence of periodic
decisions, and closure. The default verification remains four modes per
discovered model. To test all six modes, pass all six names to `--modes`. Use
`--models` to select
specific models only when that deployment advertises them.

For your own mono 16 kHz PCM16 WAV, use `--audio ./request.wav`. The helper's
question always tests weather routing. Omit `--expected-choice` for a contract
check with unknown audio, or specify `get_weather`/`NO_TOOL` when the expected
answer is known. To target another deployment, pass `--base-url` with its API
origin and a key valid there. TestPyPI does not provide an API deployment.

Exit codes: `0` passed, `1` prerequisite/API/verification failure, `2` invalid
input. Reports contain decisions, timings, errors, and SDK metadata. Keep them
local or share them according to your data requirements. Credentials and raw
audio are excluded from reports.

## Contents and public scope

```text
skills/tazo/
  SKILL.md                     Agent entrypoint and capability routing
  LICENSE                      License retained when the skill is installed
  references/python-sdk.md     Setup, sync/async uploads, typed results
  references/streaming.md      PCM format, concurrency, lifecycle, cleanup
  references/troubleshooting.md
  references/updates.md        Skill/SDK updates and opt-in automation
  scripts/check_setup.py       Local prerequisites, health, and discovery
  scripts/verify.py            Four default modes plus two manual trigger modes
  scripts/_support.py          URL validation and credential redaction
  assets/weather.wav           Bundled weather-request recording
tests/                         Local HTTP/WebSocket tests; no live key needed
```

The skill covers only `POST /v1/decisions`, WebSocket `/v1/decisions/stream`,
`GET /v1/models`, and `GET /healthz`. Account/key administration uses the
console. Tazo returns decisions; it does not execute tools named in a choice.

The sample says “What is the weather today?”. It was synthesized with macOS
`say` and converted to uncompressed mono 16 kHz PCM16 WAV. The verification
helper was adapted from Tazo's SDK example. Repository code, documentation,
and bundled sample are provided under [Apache-2.0](LICENSE).

## Update or remove

```sh
npx skills@latest list
npx skills@latest check
# Choose the scope where Tazo was installed:
npx --yes skills@latest update tazo --project --yes
# Or:
npx --yes skills@latest update tazo --global --yes
npx skills@latest remove tazo
```

**Updates are pulled, not pushed to users' computers.** New installations get
the default branch's current skill. Existing installations stay as they are
until the user runs an update, or opts into a scheduled update on their own
machine. `@latest` updates the CLI used for the command; it is not a background
skill updater. Reload the agent session after updating.

For automatic updates of a personal global installation, configure the user's
scheduler to run the global command above daily or before agent startup. Set
up Node.js/`npx` on the scheduler's PATH and retain logs. For team projects,
prefer scheduled update PRs that change the skill and `skills-lock.json`
together. No automatic job is installed by this repository. See
[the update guide](skills/tazo/references/updates.md) for details, untracked
manual installs, and the separate Python dependency update.

See the [skills CLI reference](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)
for installation scope, supported agents, and pinned Git sources. For a
reproducible installation, use a reviewed Git tag's direct skill URL instead
of the moving default branch.

## Develop and release

The root Python project is development tooling, not another SDK or a package
that needs publication on PyPI. Development dependencies are locked in
`uv.lock`; customers only need the SDK to run the helpers.

```sh
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
npx skills@latest add . --list
```

CI runs these checks with Python 3.11 and 3.14 and validates CLI discovery.
Tests exercise the published `tazo-sdk==0.1.4` against a local public-API double,
including single-model production discovery, eight cases on a two-model API,
semantic failures, missing/invalid keys, streaming
disconnects, manual sample-range commits, periodic-event rejection, cleanup,
and error redaction. They do not establish live model quality or provider
availability. Before a release, run the live verification
with a dedicated key from your own terminal and review the report.

Validate the frontmatter with the official
[skills-ref validator](https://github.com/agentskills/agentskills/tree/main/skills-ref)
when editing the skill format: `skills-ref validate ./skills/tazo`. Test a
local install in a separate scratch project to ensure all resources are copied:

```sh
npx skills@latest add /absolute/path/to/agent-skills --skill tazo --agent codex
```

Keep the skill's `metadata.version` independent of the SDK version. When
updating behavior, update that skill version, record the SDK version tested in
`metadata.sdk-version`, run checks, and push reviewed changes to `main`.
Optionally create a Git tag such as `v1.1.1` after the release checks pass.
The normal install command works as soon as the files are on the public default
branch; an npm account, npm token, and `npm publish` are unnecessary.
The CLI compares source/content state when checking for changes; bumping the
skill's metadata version alone is not an update delivery mechanism. Merging
the release updates future installations. Existing users then run `update` or
receive it through their own opt-in automation.

## Link from Mintlify

Add a page such as `guides/agent-skill.mdx` to the customer documentation, add
it to the navigation in `docs.json`, and show the install command above along
with Python/key prerequisites, example prompts, and a link to this repository.
Use the documentation's preview/build checks before deploying. Updating this
repository does not deploy the separate Mintlify site.

The [skills.sh FAQ](https://skills.sh/docs/faq) describes automatic directory
discovery through eligible CLI installation telemetry. Installing from GitHub
works independently of when a directory entry appears. No separate registry
submission is required for the GitHub installation command.

[Tazo SDK documentation](https://docs.tazolabs.com/sdk/python/overview) ·
[Agent Skills specification](https://agentskills.io/specification)
