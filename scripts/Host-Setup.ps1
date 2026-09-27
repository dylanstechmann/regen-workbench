# Host-Setup.ps1 — Run on the LAPTOP (not inside a container). GPU checks are optional.
# Usage: .\scripts\Host-Setup.ps1 [-Gpu]
param(
    [switch]$Gpu,
    [switch]$Help
)

if ($Help) {
    Write-Host "Usage: .\scripts\Host-Setup.ps1 [-Gpu]"
    exit 0
}

$exitCode = 0

function Pass($msg) { Write-Host "OK    $msg" }
function Warn($msg) { Write-Host "WARN  $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "FAIL  $msg" -ForegroundColor Red; $script:exitCode = 1 }

Write-Host "== Regen workbench host checks =="

# Docker
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    $version = & docker --version 2>&1
    Pass "docker $version"
} else {
    Fail "Install Docker Engine or Docker Desktop"
}

# Docker Compose v2
try {
    $composeVersion = & docker compose version --short 2>&1
    Pass "docker compose $composeVersion"
} catch {
    Fail "Need Docker Compose v2 (docker compose)"
}

# GPU checks
if ($Gpu) {
    $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($nvidiaSmi) {
        Pass "nvidia-smi present"
        & nvidia-smi -L 2>&1 | Write-Host
    } else {
        Fail "nvidia-smi missing — install an NVIDIA driver for GPU workloads"
    }

    # nvidia-container-toolkit check (Windows/WSL2 typically uses Docker Desktop GPU support)
    $nvidiaCtk = Get-Command nvidia-ctk -ErrorAction SilentlyContinue
    if ($nvidiaCtk) {
        Pass "nvidia-container-toolkit looks installed"
    } else {
        Warn "NVIDIA Container Toolkit may not be installed."
        Write-Host "  Docker Desktop for Windows includes GPU support via WSL2."
        Write-Host "  Ensure WSL2 backend is enabled in Docker Desktop settings."
    }

    # GPU container test
    try {
        $gpuTest = & docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi 2>&1
        if ($LASTEXITCODE -eq 0) {
            Pass "GPU visible inside a CUDA container"
        } else {
            Fail "Could not run a GPU test container"
        }
    } catch {
        Fail "Could not run a GPU test container"
    }
}

Write-Host ""
Write-Host "RAM / disk snapshot:"

# RAM
$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
Write-Host "  RAM: ${totalGB} GB total, ${freeGB} GB free"

# Disk
$drive = (Get-Item .).PSDrive
$freeSpaceGB = [math]::Round($drive.Free / 1GB, 1)
$usedSpaceGB = [math]::Round($drive.Used / 1GB, 1)
Write-Host "  Disk ($($drive.Name):): ${usedSpaceGB} GB used, ${freeSpaceGB} GB free"

exit $exitCode
