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
