# Bootstrap.ps1 — Build and start the workbench. Run on the laptop from the repo root.
# Usage: .\scripts\Bootstrap.ps1 [-Gpu] [-PullColabfold]
param(
    [switch]$Gpu,
    [switch]$PullColabfold,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: .\scripts\Bootstrap.ps1 [-Gpu] [-PullColabfold]"
    exit 0
}

# Navigate to repo root (parent of scripts/)
Push-Location (Split-Path -Parent $PSScriptRoot)
try {

# If -Gpu is set, also pull ColabFold
if ($Gpu) { $PullColabfold = $true }

# Ensure directories exist
$dirs = @("projects", "data", "cache\colabfold", "cache\boltz", "cache\huggingface", "cache\torch")
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
}
# Touch gitkeep files
foreach ($f in @("data\.gitkeep", "projects\.gitkeep")) {
    if (-not (Test-Path $f)) {
        New-Item -ItemType File -Path $f -Force | Out-Null
    }
}

# Create .env from example if missing
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Wrote .env from .env.example — edit EMAIL and NCBI_API_KEY."
}

# Build the workbench image
Write-Host "== building workbench image (first time is slow) =="
& docker compose build workbench
if ($LASTEXITCODE -ne 0) { throw "docker compose build failed" }

# Start services
Write-Host "== starting workbench and MCP service =="
if ($Gpu) {
    & docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d workbench mcp
} else {
    & docker compose up -d workbench mcp
}
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

# Pull ColabFold if requested
if ($PullColabfold) {
    Write-Host "== pulling ColabFold GPU image =="
    & docker compose --profile gpu pull colabfold
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Compose pull failed; trying direct pull..."
        & docker pull ghcr.io/sokrypton/colabfold:1.6.3-cuda12
    }
}

Write-Host ""
Write-Host "Workbench is up."
Write-Host "  shell:    docker compose exec workbench bash"
Write-Host "  doctor:   docker compose exec workbench regen doctor"
Write-Host "  jupyter:  http://127.0.0.1:8888  (loopback only; token required)"
Write-Host "  MCP:      service is ready for a local MCP client (see MCP_SETUP.md)"
Write-Host ""
Write-Host "Configure MCP clients with the local Docker Compose command; see MCP_SETUP.md."
Write-Host "Keep API keys in .env only; never put provider/GitHub credentials in chat."

} finally {
    Pop-Location
}
