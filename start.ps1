<#
.SYNOPSIS
    Start the containerized Retirement Planning app with Podman or Docker (Windows).
.DESCRIPTION
    Windows counterpart of start.sh.
    Usage:  .\start.ps1 [up|down|logs|rebuild|restart]
    If script execution is blocked, use start.bat instead (it bypasses the policy for this one script).

    Runtime selection: set $env:CONTAINER_RUNTIME = "podman" or "docker" to force one.
    Otherwise podman is used when installed, falling back to docker.
#>
param(
    [ValidateSet('up', 'down', 'logs', 'rebuild', 'restart')]
    [string]$Command = 'up'
)

# Native commands report failure through $LASTEXITCODE, which is checked explicitly below.
$ErrorActionPreference = 'Continue'
Set-Location -Path $PSScriptRoot

$Url    = 'http://localhost:8501'   # Streamlit (legacy UI)
$WebUrl = 'http://localhost:8000'   # HTML front end + API

function Fail([string]$Message) {
    Write-Host "Error: $Message" -ForegroundColor Red
    exit 1
}

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

# True when the native command exits 0 (output discarded).
function Test-Native([string]$Exe, [string[]]$CmdArgs) {
    & $Exe @CmdArgs *> $null
    return ($LASTEXITCODE -eq 0)
}

# --- Pick the runtime -------------------------------------------------------
$Runtime = $env:CONTAINER_RUNTIME
if (-not $Runtime) {
    if (Test-Command 'podman')     { $Runtime = 'podman' }
    elseif (Test-Command 'docker') { $Runtime = 'docker' }
    else { Fail 'neither podman nor docker found on PATH. See docs\user\CONTAINER_SETUP.md.' }
}

switch ($Runtime) {
    'podman' {
        if (-not (Test-Command 'podman')) { Fail 'podman not found on PATH.' }
        # `podman compose` otherwise picks the first provider on PATH (e.g. docker-compose).
        $env:PODMAN_COMPOSE_PROVIDER = 'podman-compose'
        $env:PODMAN_COMPOSE_WARNING_LOGS = 'false'
        if (-not (Test-Command 'podman-compose')) {
            Fail 'podman-compose not found (pip install podman-compose, or use Docker Desktop).'
        }
        $ComposeExe  = 'podman'
        $ComposeArgs = @('compose')
        # On Windows, containers run inside a WSL2 VM; start it if needed.
        if (-not (Test-Native 'podman' @('info'))) {
            Write-Host 'Starting Podman machine...'
            & podman machine start
            if ($LASTEXITCODE -ne 0) {
                Fail 'could not start the Podman machine. If none exists yet, run: podman machine init'
            }
        }
    }
    'docker' {
        if (-not (Test-Command 'docker')) { Fail 'docker not found on PATH.' }
        if (Test-Native 'docker' @('compose', 'version')) {
            $ComposeExe  = 'docker'
            $ComposeArgs = @('compose')
        }
        elseif (Test-Command 'docker-compose') {
            $ComposeExe  = 'docker-compose'
            $ComposeArgs = @()
        }
        else { Fail "Docker Compose not found (need the 'docker compose' plugin or docker-compose)." }
        if (-not (Test-Native 'docker' @('info'))) {
            Fail 'the Docker daemon is not running. Start Docker Desktop (or Rancher Desktop) and retry.'
        }
    }
    default { Fail "CONTAINER_RUNTIME must be 'podman' or 'docker' (got '$Runtime')." }
}
Write-Host "Using container runtime: $Runtime ($ComposeExe $($ComposeArgs -join ' '))"

function Invoke-Compose([string[]]$Rest) {
    & $ComposeExe @ComposeArgs @Rest
    return $LASTEXITCODE
}

# --- First start: create .env from the template ----------------------------
# Must exist as a FILE before compose runs, otherwise the bind mount creates a directory named .env.
if (-not (Test-Path -LiteralPath '.env' -PathType Leaf)) {
    if (Test-Path -LiteralPath '.env' -PathType Container) {
        Fail '.env is a directory (created by an earlier compose run). Delete it and run start.ps1 again.'
    }
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host 'Created .env from .env.example. Replace the placeholder values (or import a backup bundle' -ForegroundColor Yellow
    Write-Host 'that contains your .env) and run .\start.ps1 restart for them to take effect.' -ForegroundColor Yellow
}

# --- Commands ----------------------------------------------------------------
switch ($Command) {
    { $_ -in 'up', 'rebuild', 'restart' } {
        if ($Command -eq 'rebuild') {
            if ((Invoke-Compose @('build', '--no-cache')) -ne 0) { Fail 'image build failed.' }
        }
        # --force-recreate on rebuild so a new image replaces the running container;
        # restart recreates the containers without rebuilding, which picks up a changed .env.
        $upArgs = @('up', '-d', '--build')
        if ($Command -in 'rebuild', 'restart') { $upArgs += '--force-recreate' }
        if ((Invoke-Compose $upArgs) -ne 0) { Fail 'compose up failed.' }

        Write-Host -NoNewline 'Waiting for the apps to become healthy'
        for ($i = 0; $i -lt 60; $i++) {
            try {
                Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri "$Url/_stcore/health" | Out-Null
                Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri "$WebUrl/api/health" | Out-Null
                Write-Host ''
                Write-Host 'Ready:'
                Write-Host "  HTML app:      $WebUrl"
                Write-Host "  Streamlit app: $Url"
                Start-Process $WebUrl
                exit 0
            }
            catch {
                Write-Host -NoNewline '.'
                Start-Sleep -Seconds 2
            }
        }
        Write-Host ''
        Write-Host 'App did not become healthy in time. See: .\start.ps1 logs' -ForegroundColor Red
        exit 1
    }
    'down' { exit (Invoke-Compose @('down')) }
    'logs' { exit (Invoke-Compose @('logs', '-f')) }
}
