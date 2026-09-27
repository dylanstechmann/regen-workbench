# MCP setup for Regen Workbench

The workbench includes a local stdio MCP server at
`tools/regen_mcp.py`. It exposes a deliberately limited set of research
operations backed by the existing `regen` CLI. It does **not** expose an
arbitrary shell, arbitrary Python, GitHub API, host filesystem browsing, or a
Docker socket.

## Exposed capabilities

- PubMed, EuropePMC, and OpenAlex literature search; UniProt, InterPro, and
  Ensembl metadata; AlphaFold DB structure and RCSB PDB fetches
- STRING interaction lookup; ChEMBL and PubChem public data lookup
- Local MSA; RDKit SMILES validation/descriptors; headless PyMOL PNG rendering
- Fold routing guidance and workbench diagnostics

Network tools access the respective public databases and write downloaded
artifacts plus provenance under `/lab/data`. They do not run de novo folding.
For folding, fetch experimental/AFDB entries first; jobs that exceed the
laptop's actual GPU/RAM budget need an explicitly chosen overflow provider.

## Start the services

From `regen-workbench` on the laptop:

```bash
./scripts/host-setup.sh
./scripts/bootstrap.sh
docker compose exec workbench regen doctor
```

The startup script starts `workbench` and a persistent `mcp` service. The MCP
client launches the protocol process through the host's Docker CLI:

```text
docker compose -f <absolute-path-to-regen-workbench/docker-compose.yml> exec --interactive --no-TTY mcp python /lab/workbench/tools/regen_mcp.py
```

Compose `exec` normally allocates a TTY. `--interactive --no-TTY` is important:
it keeps the MCP stdio stream open while ensuring JSON-RPC isn't mangled by a
terminal. Docker stays on the host; the agent-facing container has no Docker
socket mount. The MCP service has no published network ports.

## Codex desktop / Codex CLI / Codex IDE

Add this to `~/.codex/config.toml` on the laptop. Codex desktop, CLI, and its
IDE integration share this host configuration. Replace the Compose file path
if the project is stored elsewhere.

```toml
[mcp_servers.regen_workbench]
command = "docker.exe"
args = [
  "compose",
  "--project-directory",
  "C:/Users/AyeBayBay/Projects/other5/workspace/regen-workbench",
  "-f",
  "C:/Users/AyeBayBay/Projects/other5/workspace/regen-workbench/docker-compose.yml",
  "exec",
  "--interactive",
  "--no-TTY",
  "mcp",
  "python",
  "/lab/workbench/tools/regen_mcp.py",
]
startup_timeout_sec = 30
tool_timeout_sec = 660
enabled = true
default_tools_approval_mode = "prompt"
```

On a non-Windows host, use `docker` and a POSIX absolute Compose-file path.
The `docker.exe` value assumes Docker Desktop's CLI is on the desktop app's
PATH; if not, put its full executable path in `command`.

## Cline in VS Code

Use the MCP Servers panel → **Configure MCP Servers**, or edit Cline's MCP
JSON (`~/.cline/mcp.json` for Cline CLI; the IDE panel opens the extension's
actual config file). Merge this entry into the existing `mcpServers` object:

```json
{
  "mcpServers": {
    "regen-workbench": {
      "command": "docker.exe",
      "args": [
        "compose",
        "--project-directory",
        "C:/Users/AyeBayBay/Projects/other5/workspace/regen-workbench",
        "-f",
        "C:/Users/AyeBayBay/Projects/other5/workspace/regen-workbench/docker-compose.yml",
        "exec",
        "--interactive",
        "--no-TTY",
        "mcp",
        "python",
        "/lab/workbench/tools/regen_mcp.py"
      ],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

Keep `autoApprove` empty initially so calls require review. If the desktop
application cannot locate Docker, use its full `docker.exe` path for `command`.

## Antigravity

Antigravity IDE supports custom MCP servers. Open Settings → **Customizations**
→ **Installed MCP Servers** → **Add MCP**. The documented config file is
`~/.gemini/config/mcp_config.json` globally, or `.agents/mcp_config.json` in
the active workspace. For Windows, the global path is under your user profile
(for example, `C:/Users/AyeBayBay/.gemini/config/mcp_config.json`). Add/merge:

```json
{
  "mcpServers": {
    "regen-workbench": {
      "command": "docker.exe",
      "args": [
        "compose",
        "--project-directory",
        "C:/Users/AyeBayBay/Projects/other5/workspace/regen-workbench",
        "-f",
        "C:/Users/AyeBayBay/Projects/other5/workspace/regen-workbench/docker-compose.yml",
        "exec",
        "--interactive",
        "--no-TTY",
        "mcp",
        "python",
        "/lab/workbench/tools/regen_mcp.py"
      ],
      "cwd": "C:/Users/AyeBayBay/Projects/other5/workspace/regen-workbench"
    }
  }
}
```

The IDE settings UI is also available at Settings → **Customizations** →
**Installed MCP Servers**. Keep the MCP tool permission policy at **Ask** while
evaluating the server. Antigravity's configuration supports local stdio
`command`, `args`, and `cwd`; its remote-server field is `serverUrl` (not
`url`). The Antigravity CLI additionally provides `/mcp` and the same dedicated
global/workspace config paths.

If Antigravity is running inside a separate Docker container, it cannot launch
the host's `docker.exe` command using this stdio configuration. Do not solve
that by mounting `/var/run/docker.sock` into the workbench. Use the laptop-host
Antigravity app/CLI for this stdio connection; a cross-container MCP network
bridge would require its own authenticated, narrowly scoped setup.

## Test MCP without an agent

From the workspace root, run the tests in the existing `dev` container (the
current minimal workspace shell does not include Python's full stdlib):

```bash
docker compose run --rm dev bash -lc 'cd /workspace/regen-workbench && python3 -m unittest discover -s tests -v'
```

The MCP server itself has no third-party Python dependency.

After connecting a client, its MCP server tool list should show the `regen_*`
tools. For a low-level stdio smoke test from Git Bash:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"smoke-test","version":"1"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | docker compose exec --interactive --no-TTY mcp python /lab/workbench/tools/regen_mcp.py
```

The MCP process itself uses stdio and is started by the MCP client, not as a
long-running daemon. Local stdio MCP requires a desktop/CLI agent process that
can launch commands on the laptop; a provider's remote cloud-only sandbox
cannot directly spawn this host Docker command unless that product explicitly
supports a local bridge.

This is a local MCP integration for Codex desktop/CLI, Cline running in the
laptop's VS Code, or a laptop-host Antigravity client. It is not automatically
available to Grok Build's hosted cloud sandbox or to a Grok CLI running in the
separate `grok` container. Check that client's current local-MCP support before
expecting it to use the tools; do not expose the Docker socket or unauthenticated
MCP port as a shortcut.

## Data, credentials, and safety

- Revoke the GitHub token that was pasted into the earlier conversation. Do
  not put a replacement in `.env`, MCP config, the container, or chat. Use the
  host's GitHub CLI/device login or host SSH agent for Git push/pull.
- `.env` is read by Compose to provide optional NCBI API key/contact settings
  to the workbench containers. It is ignored by Git. Only put database API
  keys there; do not place agent-provider or GitHub credentials there. Keep
  the Windows file ACL restricted to your account; this workspace mount does
  not permit changing `.env` permissions from this Linux session.
- Do not mount host `~/.ssh`, host Git config, or the Docker socket in the
  workbench. Start/manage sibling containers and push/pull Git repositories
  from the laptop host.
- Jupyter is published only on `127.0.0.1:8888` and uses its default token
  protection. Do not remove the token or change the bind address casually.
- MCP tools can make network requests and write fetched files/provenance under
  `data/`. Review each tool call and its output; no command runs a treatment,
  clinical protocol, or wet-lab operation.