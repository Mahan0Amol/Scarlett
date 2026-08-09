# Scarlett setup script (Windows / PowerShell)
#
# Usage (remote install):
#   irm https://raw.githubusercontent.com/Mahan0Amol/Scarlett/main/setup.ps1 | iex
#
# Usage (local, already cloned):
#   .\setup.ps1
#
# If your execution policy blocks local scripts, run once:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#
# This script asks before installing anything on your system. Nothing is
# installed silently.

$RepoUrl = "https://github.com/Mahan0Amol/Scarlett.git"
$RepoDir = "Scarlett"
$MinPythonMinor = 11
$MinNodeMajor = 18

function Info($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "OK  $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "!!  $msg" -ForegroundColor Yellow }
function Err($msg)  { Write-Host "XX  $msg" -ForegroundColor Red }

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Ask-YesNo($prompt) {
    $reply = Read-Host "$prompt [y/N]"
    return $reply -match '^[Yy]'
}

# Refreshes $env:Path from the registry so newly-installed tools (e.g. via
# winget) become visible in this same session without reopening the shell.
function Refresh-Path {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user    = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Offer-WingetInstall($name, $wingetId) {
    if (-not (Ask-YesNo "$name was not found. Install it now via winget?")) {
        Warn "Skipping $name install - you'll need to install it yourself before Scarlett will run."
        return $false
    }
    if (-not (Test-Command winget)) {
        Err "winget is not available on this system (needs Windows 10 2004+ / Windows 11)."
        Warn "Install $name manually, then re-run this script."
        return $false
    }
    Info "Running: winget install --id $wingetId -e --silent --accept-package-agreements --accept-source-agreements"
    winget install --id $wingetId -e --silent --accept-package-agreements --accept-source-agreements
    Refresh-Path
    return $true
}

# ---- 1. git ------------------------------------------------------------------
Info "Checking for git..."
if (Test-Command git) {
    Ok "git found"
} else {
    Offer-WingetInstall "git" "Git.Git" | Out-Null
    if (-not (Test-Command git)) {
        Err "git is still not available. Install it manually (https://git-scm.com) and re-run this script."
        exit 1
    }
    Ok "git installed"
}

# ---- 2. python -----------------------------------------------------------------
Info "Checking for Python 3.$MinPythonMinor+..."
function Find-GoodPython {
    foreach ($candidate in @("py", "python", "python3")) {
        if (Test-Command $candidate) {
            try {
                $ver = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($ver) {
                    $parts = $ver.Split(".")
                    if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge $script:MinPythonMinor) {
                        return $candidate
                    }
                }
            } catch {}
        }
    }
    return $null
}

$pythonBin = Find-GoodPython
if ($pythonBin) {
    Ok "Python found ($pythonBin)"
} else {
    Offer-WingetInstall "Python 3.$MinPythonMinor+" "Python.Python.3.12" | Out-Null
    $pythonBin = Find-GoodPython
    if (-not $pythonBin) {
        Err "Python 3.$MinPythonMinor+ still not available."
        Warn "Install it from https://python.org (check 'Add to PATH' during install), then re-run this script."
        Warn "If you just installed it via winget, try closing and reopening this terminal first."
        exit 1
    }
    Ok "Python ready ($pythonBin)"
}

# ---- 3. node -------------------------------------------------------------------
Info "Checking for Node.js $MinNodeMajor+..."
function Node-Ok {
    if (-not (Test-Command node)) { return $false }
    if (-not (Test-Command npm)) { return $false }
    $major = [int]((node -v) -replace "v", "" -split "\.")[0]
    return $major -ge $MinNodeMajor
}

if (Node-Ok) {
    Ok "Node.js $(node -v)"
} else {
    Offer-WingetInstall "Node.js" "OpenJS.NodeJS.LTS" | Out-Null
    if (-not (Node-Ok)) {
        Err "Node.js $MinNodeMajor+ still not available."
        Warn "Install it from https://nodejs.org, then re-run this script."
        Warn "If you just installed it via winget, try closing and reopening this terminal first."
        exit 1
    }
    Ok "Node.js $(node -v)"
}

if (-not (Test-Command npm)) {
    Err "npm not found (usually ships with Node.js)."
    exit 1
}
Ok "npm $(npm -v)"

# ---- 4. clone repo (skip if already inside it) ----------------------------------
if ((Test-Path "backend/server.py") -and (Test-Path "package.json")) {
    Info "Already inside the Scarlett repo - skipping clone."
} else {
    if (Test-Path $RepoDir) {
        Warn "'$RepoDir' already exists - using it instead of re-cloning."
    } else {
        Info "Cloning Scarlett..."
        git clone $RepoUrl $RepoDir
        if ($LASTEXITCODE -ne 0) { Err "Clone failed."; exit 1 }
        Ok "Cloned into .\$RepoDir"
    }
    Set-Location $RepoDir
}

# ---- 5. backend setup -------------------------------------------------------------
Info "Setting up Python virtual environment..."
if (-not (Test-Path "venv")) {
    & $pythonBin -m venv venv
}
& .\venv\Scripts\Activate.ps1
Ok "Virtual environment ready"

Info "Installing Python dependencies (this can take a few minutes)..."
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Err "Python dependency install failed - see the error above."
    deactivate
    exit 1
}
Ok "Python dependencies installed"

Info "Installing Playwright browsers..."
playwright install
Ok "Playwright ready"

deactivate

# ---- 6. env file --------------------------------------------------------------------
if (Test-Path "backend\.env") {
    Ok "backend\.env already exists - leaving it untouched"
} else {
    Copy-Item "backend\.env.example" "backend\.env"
    Ok "Created backend\.env from template"
    Warn "Edit backend\.env (or use the in-app Full Settings screen) to add your GEMINI_API_KEY and other values."
}

# ---- 7. frontend setup ---------------------------------------------------------------
Info "Installing frontend dependencies (npm install)..."
npm install
if ($LASTEXITCODE -ne 0) {
    Err "npm install failed - see the error above."
    exit 1
}
Ok "Frontend dependencies installed"

# ---- done ------------------------------------------------------------------------------
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. cd $RepoDir   (if you're not already there)"
Write-Host "  2. npm run dev"
Write-Host "  3. Click the settings icon in the toolbar -> Full Settings -> .env, and add your GEMINI_API_KEY"
Write-Host "     (get one at https://ai.google.dev)"
Write-Host "  4. Hit the mic button and start talking."
Write-Host ""
Write-Host "Note: this script only wires up voice/text chat. Optional plugins (Gmail, printers,"
Write-Host "smart home, music) need their own setup - see README.md."
