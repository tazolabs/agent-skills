# Installing and updating the Tazo skill

The skill and the Python SDK are separate installations:

| Component | Source | Update mechanism |
| --- | --- | --- |
| Agent instructions, references, helpers, and sample | `tazolabs/agent-skills` on GitHub | `npx skills@latest update tazo` |
| Python SDK used by application code | `tazo-sdk` on PyPI | The project's Python dependency manager |

Skill **1.3.0** adds multiple-question guidance and is tested with SDK **0.1.5**.
It retains native hosted MCP installation and sign-in.
MCP installation uses Tazo browser sign-in; SDK/API-key setup below applies
only to application development. Updating the skill does not install
or upgrade a Python dependency. Updating the SDK does not replace an installed
skill. Preserve the user's dependency and lockfile workflow.

## New installations

Run from the user's project with Node.js 22.20+:

```sh
npx skills@latest add tazolabs/agent-skills --skill tazo
```

This resolves the public repository's default branch at installation time.
Add `--global` for a user-wide installation; otherwise the installation is
project-local. The full skill folder is needed, including references, scripts,
license, and the audio asset. Reload the agent session after installing.

For a new Python application environment, install the tested SDK:

```sh
python -m pip install 'tazo-sdk==0.1.5'
```

For an existing project, upgrade an older SDK through its dependency manager
when the requested feature requires it. Manual streaming needs SDK 0.1.4+.

## Existing installations

The skills CLI does not install a background updater. A push to GitHub, a new
Git tag, or changing `metadata.version` cannot push files to another person's
computer. `@latest` in the command selects the latest **CLI**; it does not keep
installed skill files continuously synchronized.

Inspect and check installed skills:

```sh
npx skills@latest list
npx skills@latest list --global
npx skills@latest check
```

Update only Tazo in the scope where it was installed:

```sh
# Run in the project containing the project installation and skills-lock.json.
npx --yes skills@latest update tazo --project --yes

# Or update the user-wide installation.
npx --yes skills@latest update tazo --global --yes
```

The first `--yes` belongs to `npx` (allow downloading the CLI); the second
belongs to `skills` (skip its scope prompt). Scope flags make unattended
commands independent of automatic scope detection. Reload the agent session
after the update so it reads the new instructions. Review local modifications
before replacing a customized skill; keep customizations outside the upstream
skill folder where practical.

If a manual copy or an older installation has no usable source/lock record,
reinstall it with the original `add` command and the same scope and agent
selection. A plain copied folder is not automatically tracked by the CLI.
Installing from a Git tag or commit pins that source; choose the moving
default branch when the user wants to follow future releases.

## Opt-in automatic updates

For a personal global installation, the user can configure their own scheduler
to run the global update command above daily or before starting their agent.
Use launchd on macOS, Task Scheduler on Windows, or systemd/cron on Linux.
Ensure the scheduled process can find both Node.js and `npx`, can reach GitHub
and npm, and saves its output to a user-readable log. No Tazo API key is needed
for updating the skill. Run the exact command once manually to check it first.
Scheduling limits how stale the on-disk skill can be; an already-running agent
may retain old instructions until its next session.

An alternative for Codex CLI users is an explicit startup wrapper. After the
global installation, the user can add this function to their shell config:

```sh
tazo_codex() {
  npx --yes skills@latest update tazo --global --yes || return
  codex "$@"
}
```

Run `tazo_codex` to update before starting a fresh Codex process. The wrapper
stops if the update command fails. It only covers launches through this
function and global installations; a project-local copy can take precedence.
For a project installation, use `--project` and run from that project instead.
Other agents need an equivalent entrypoint or the scheduled command.

For a shared repository, prefer an update PR: run the project update command
in a scheduled CI job, include changed skill files and `skills-lock.json` in a
PR, then run checks before merging. Teammates receive it on their next pull;
they may need the CLI's restore command to recreate local agent links. This
keeps the team's skill content and lockfile consistent.

Do not install a background job or change an agent startup configuration
merely because someone invokes the Tazo skill. Set up automation only when the
user requests that change. A skill cannot retrofit automation into previously
downloaded copies; those users need a one-time update or opt-in setup.

The official [skills CLI reference](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)
documents update scopes, source references, lockfiles, and restore commands.
