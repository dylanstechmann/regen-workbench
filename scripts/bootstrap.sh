#!/usr/bin/env bash
# Build and start the workbench. Run on the laptop from the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."

GPU=0
PULL_COLAB=0
for arg in "$@"; do
  case "$arg" in
    --gpu) GPU=1 ; PULL_COLAB=1 ;;
    --pull-colabfold) PULL_COLAB=1 ;;
    -h|--help)
      echo "Usage: $0 [--gpu] [--pull-colabfold]"
      exit 0
      ;;
  esac
done

mkdir -p projects data cache/colabfold cache/boltz cache/huggingface cache/torch
touch data/.gitkeep projects/.gitkeep

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Wrote .env from .env.example — edit EMAIL and NCBI_API_KEY."
fi

echo "== building workbench image (first time is slow) =="
docker compose build workbench

echo "== starting workbench and MCP service =="
if [[ "$GPU" == "1" ]]; then
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d workbench mcp
else
  docker compose up -d workbench mcp
fi

if [[ "$PULL_COLAB" == "1" ]]; then
  echo "== pulling ColabFold GPU image =="
  docker compose --profile gpu pull colabfold || docker pull ghcr.io/sokrypton/colabfold:1.6.3-cuda12
fi

echo
echo "Workbench is up."
echo "  shell:    docker compose exec workbench bash"
echo "  doctor:   docker compose exec workbench regen doctor"
echo "  jupyter:  http://127.0.0.1:8888  (loopback only; token required)"
echo "  MCP:      service is ready for a local MCP client (see MCP_SETUP.md)"
echo
echo "Configure MCP clients with the local Docker Compose command; see MCP_SETUP.md."
echo "Keep API keys in .env only; never put provider/GitHub credentials in chat."
