# Agent instructions — regen-workbench

Work only in this repository unless the user pointed at a sibling. This repo is the Docker/MCP sidecar, not the science.

Also read [agent/AGENT_BRIEFING.md](agent/AGENT_BRIEFING.md), [agent/PROJECT_SEEDS.md](agent/PROJECT_SEEDS.md), [agent/LAPTOP_SESSION.md](agent/LAPTOP_SESSION.md), and [RESEARCH_PHILOSOPHY.md](RESEARCH_PHILOSOPHY.md). The parent-folder script to copy onto the laptop is [agent/PARENT_AGENTS.md](agent/PARENT_AGENTS.md). For a new Cline or Grok CLI session, `agent/LAPTOP_SESSION.md` is the brief.

## Do not

- Mount the Docker socket into the workbench image.
- Put GitHub, NCBI, OpenAlex, Modal, ORCID, or any other credential in git, MCP config, or chat. Host `.env` only, gitignored.
- Add a new methods package inside this repo. Those are sibling checkouts.
- Claim `regen doctor` passing means a biological result.

## First commands

From the laptop host, not from a cloud sandbox:

```bash
docker compose exec workbench regen doctor
python -m unittest discover -s tests -v
```

## Improve, in this order

1. If a documented MCP command does not match `docker-compose.yml` or `tools/regen_mcp.py`, fix the doc or the command and smoke-test `tools/list`.
2. Keep the tool allowlist narrow. Do not add an arbitrary shell tool.
3. Provenance files under `data/provenance/` only when a real fetch happened.

## Done when

Unit tests pass, or you report that Docker is not running. Do not fake `regen doctor`.

## Agent tooling (portable across harnesses)

<!-- agent-toolbox:installed -->

This repo vendors its agent tooling (no secrets inside) so Claude Code,
Cline, Codex, OpenCode, Kilo Code, Kimi Code and Grok share one setup:

- `.mcp.json` — project MCP servers:
  `scholar` (PubMed, OpenAlex, Semantic Scholar, CORE, ORCID, Crossref),
  `web` (Exa, Brave, Jina, Firecrawl), `github` (read-only, token via
  `gh auth token`), `context7` (library docs), `playwright` (browser).
- `opencode.json` — the same servers for OpenCode;
  `AGENT_TOOLS.md` has merge snippets for Codex / Cline / Kilo Code and
  CLI fallbacks for Kimi / Grok.
- `.claude/skills/` — project skills: citation-check, literature-search, web-research, secrets-guard, regen-guardrails, fold-providers.
- Keys: `~/.config/ai-keys.env` via the `agentkeys` loader — never in git,
  MCP config or chat. Run `secrets-guard` (`--staged`) before committing.
