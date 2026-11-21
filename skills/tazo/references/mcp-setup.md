# Install and use Tazo-MCP

Use this reference when the user asks to install the MCP, including requests
that supply only its URL. Handle configuration for the user, then let the
application's native authorization flow take them to Tazo sign-in.

- Name: **Tazo-MCP**
- Production endpoint: **https://mcp.tazolabs.com/mcp**
- Transport: **Streamable HTTP** (`http` in client settings)
- Public setup guide: **https://mcp.tazolabs.com/setup**

An unauthenticated 401 is the expected OAuth challenge. Production supports
automatic client registration and native loopback callbacks. The application
discovers authorization endpoints and permissions; users supply no client
credentials or API keys. Email, Google, and an existing signed-in Tazo session
all use the platform's normal sign-in flow.

## Finish the install in the requested app

Reuse an existing connection to the same endpoint when possible. Default to
user scope for a personal installation; use project scope when requested.
Preserve other servers and settings. Keep an explicitly requested staging or
custom URL rather than replacing it with production.
When moving to production, add a fresh production entry and retain the staging
connection. Do not carry over its manually configured OAuth IDs or headers.

### Claude Code

Use the native CLI, with the name and endpoint above:

```sh
claude mcp add --transport http --scope user Tazo-MCP https://mcp.tazolabs.com/mcp
```

For an existing entry, `claude mcp get Tazo-MCP` shows its configuration. Use
`--scope project` if requested. Open Claude Code's `/mcp` menu and authenticate
Tazo-MCP through its normal browser flow. A new session may be needed before
the current agent receives the tools. Adding the CLI entry does not add a
Claude web/Desktop account connector.

Reference: [Claude Code MCP](https://code.claude.com/docs/en/mcp).

### Claude web, Desktop, and Cowork

Use **Customize → Connectors → + Add → Add custom connector**. Enter the name
and endpoint, choose **Sign in now**, and choose **Register automatically**
if OAuth client selection is shown. Complete Tazo sign-in and enable the
connector for the conversation using **+ → Connectors**. An organization owner
may need to add a managed connector first.

An agent with control of this settings UI can fill the connector details and
hand over for sign-in. If the agent cannot control account settings, give this
short UI path; do not claim a shell command installed the account connector.
The user never needs to edit a configuration file.

Reference: [Claude custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

### ZCode: agent installation

If Python 3 is available, run the bundled installer by its actual installed
path, from any working directory:

```sh
python3 /absolute/path/to/tazo/scripts/install_zcode_mcp.py
```

It adds the production HTTP entry to the user-level ZCode settings, preserving
other settings and making a private backup before a change. It also preserves
servers from an active `.agents/mcp.json` fallback when adding the first native
entry. `--dry-run` previews without writing; `--url` preserves a user-specified
endpoint; `--name` resolves a name collision. It configures the connection,
not OAuth credentials or an authenticated session.

If the helper is unavailable, an agent with file tools can make the same
limited merge at `~/.zcode/cli/config.json` under `mcp.servers.Tazo-MCP`:

```json
{"type": "http", "url": "https://mcp.tazolabs.com/mcp"}
```

Preserve existing content and an active user `.agents/mcp.json` fallback.
Native `.zcode` MCP settings take precedence over that fallback. For project
scope use `<project>/.zcode/config.json` and its project `.agents` fallback.
Do not replace the whole settings file or ask the user to paste JSON.

Refresh **Settings → MCP Servers** (called **MCP** in some versions) or start
a new session. Use the server's **Open authorization** control. ZCode opens
the system browser when that control is activated; let the user complete Tazo
sign-in. If this client version exposes an **OAuth** switch, enable it. The
installed form inspected on 2026-11-21 generates the HTTP entry above without
extra OAuth fields; do not invent schema keys or preconfigure OAuth IDs.

The UI equivalent is **Settings → MCP Servers → New**, **User**, **HTTP**,
then the name and URL above. Use this path if a desktop-managed server list
overrides the file. Do not repeatedly rewrite a file the app is ignoring.

Reference: [ZCode MCP](https://zcode.z.ai/en/docs/mcp-services).

## Verify before reporting success

In that application's connected chat, call `tazo_check_health` and
`tazo_list_models`. Expect `status: ok` and read model readiness and limits
from the actual response. These checks submit no inference. Report separately
whether the server was configured, sign-in finished, and native tool calls
passed. If tools load only at session start, ask for a new session and continue
verification there; do not substitute a custom protocol client and call the
target application verified.

If authorization fails, retry once through the client's normal sign-in
controls, then report its version, endpoint, failing stage, and redacted error.
Use the 401 discovery metadata and this setup guide rather than searching for
credentials, inspecting application bundles, creating custom OAuth listeners,
writing token caches, or changing Tazo infrastructure. Do not run the SDK
API-key setup or inference verification suite for an MCP installation.

## Audio after connection

Call `tazo_list_models` first. For a WAV accessible to the agent, compute its
SHA-256 and byte count, call `tazo_prepare_audio_upload`, then PUT the original
bytes with every returned header using file-capable tools. Keep the upload URL,
tokens, and raw audio out of model-generated text. Use the returned `audio_id`
with `tazo_decide_audio`, the user's state and questions, a ready model, and a
new idempotency key retained for identical retries. Analysis consumes the
signed-in account's Tazo credits.

Claude web can analyze an `audio_id` already uploaded by the same Tazo account.
A local path alone is not an upload. Use a file-capable client for a new local
file; microphone capture needs the local Tazo companion.

For WAV replay, `tazo_analyze_audio_stream` accepts mono 16 kHz PCM16 WAVs up to
30 seconds. `evaluation_interval_ms=1000` requests decisions each second. Show
the provisional timeline and the finalized whole-recording decision; live
progress presentation depends on the client. Never replay a failed stream
automatically. A selected action classifies intent; it does not execute it.
