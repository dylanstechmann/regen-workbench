#!/usr/bin/env bash
# Run on the LAPTOP (not inside a container). GPU checks are optional.
set -euo pipefail

ok=0
gpu=0
for arg in "$@"; do
  case "$arg" in
    --gpu) gpu=1 ;;
    -h|--help) echo "Usage: $0 [--gpu]"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
warn() { printf "WARN  %s\n" "$*"; }
pass() { printf "OK    %s\n" "$*"; }
fail() { printf "FAIL  %s\n" "$*"; ok=1; }

echo "== Regen workbench host checks =="

if command -v docker >/dev/null; then
  pass "docker $(docker --version | tr -d '\n')"
else
  fail "Install Docker Engine or Docker Desktop"
fi

if docker compose version >/dev/null 2>&1; then
  pass "docker compose $(docker compose version --short 2>/dev/null || true)"
else
  fail "Need Docker Compose v2 (docker compose)"
fi

if [[ "$gpu" == "1" ]]; then
  if command -v nvidia-smi >/dev/null; then
    pass "nvidia-smi present"
    nvidia-smi -L || true
  else
    fail "nvidia-smi missing — install an NVIDIA driver for GPU workloads"
  fi

  if command -v nvidia-ctk >/dev/null || { command -v dpkg >/dev/null && dpkg -l nvidia-container-toolkit >/dev/null 2>&1; }; then
    pass "nvidia-container-toolkit looks installed"
  else
    warn "Install NVIDIA Container Toolkit:"
    echo "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html"
  fi

  if docker info 2>/dev/null | grep -qi 'Runtimes:.*nvidia\|nvidia'; then
    pass "docker advertises nvidia runtime"
  else
    warn "Docker may not be configured for GPUs yet. After installing the toolkit:"
    echo "  sudo nvidia-ctk runtime configure --runtime=docker"
    echo "  sudo systemctl restart docker"
  fi

  if docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
    pass "GPU visible inside a CUDA container"
  else
    fail "Could not run a GPU test container"
  fi
fi

echo
echo "RAM / disk snapshot:"
free -h | head -2 || true
df -h . | tail -1 || true

exit $ok
