# Scarlett setup script (Windows / PowerShell)
#
# Usage (remote install):
#   irm https://raw.githubusercontent.com/Mahan0Amol/Scarlett/main/scripts/setup.ps1 | iex
#
# Usage (local, already cloned):
#   .\scripts\setup.ps1
#
# If your execution policy blocks local scripts, run once:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#
# This script asks before installing anything on your system. Nothing is
# installed silently. A full log of everything installed is written to
# scarlett-setup-<timestamp>.log in the current directory.

$RepoUrl = "https://github.com/Mahan0Amol/Scarlett.git"
$RepoDir = "Scarlett"
$MinPythonMinor = 11
$MinNodeMajor = 18

$LogFile = "scarlett-setup-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
"Scarlett setup log - started $(Get-Date)" | Out-File -FilePath $LogFile -Encoding utf8

function Log($msg) { "[$(Get-Date -Format 'HH:mm:ss')] $msg" | Out-File -FilePath $LogFile -Append -Encoding utf8 }
function Info($msg) { Write-Host "==> $msg" -ForegroundColor Cyan; Log "INFO  $msg" }
function Ok($msg)   { Write-Host "OK  $msg" -ForegroundColor Green; Log "OK    $msg" }
function Warn($msg) { Write-Host "!!  $msg" -ForegroundColor Yellow; Log "WARN  $msg" }
function Err($msg)  { Write-Host "XX  $msg" -ForegroundColor Red; Log "ERROR $msg" }

Info "Logging full install output to: $LogFile"

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Ask-YesNo($prompt) {
    $reply = Read-Host "$prompt [y/N]"
    Log "PROMPT $prompt -> $reply"
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
    Info "Installing $name via winget (id: $wingetId) — full output is being logged."
    Log "COMMAND winget install --id $wingetId -e --silent --accept-package-agreements --accept-source-agreements"
    winget install --id $wingetId -e --silent --accept-package-agreements --accept-source-agreements 2>&1 |
        Tee-Object -FilePath $LogFile -Append
    $success = $LASTEXITCODE -eq 0
    if ($success) { Ok "$name installed" } else { Err "$name install failed (exit $LASTEXITCODE) - see $LogFile" }
    Refresh-Path
    return $success
}

# ---- 1. git ------------------------------------------------------------------
Info "Checking for git..."
if (Test-Command git) {
    Ok "git found ($(git --version))"
} else {
    Offer-WingetInstall "git" "Git.Git" | Out-Null
    if (-not (Test-Command git)) {
        Err "git is still not available. Install it manually (https://git-scm.com) and re-run this script."
        exit 1
    }
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
    $pyVer = & $pythonBin -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    Ok "Python $pyVer found ($pythonBin)"
} else {
    Offer-WingetInstall "Python 3.$MinPythonMinor+" "Python.Python.3.12" | Out-Null
    $pythonBin = Find-GoodPython
    if (-not $pythonBin) {
        Err "Python 3.$MinPythonMinor+ still not available."
        Warn "Install it from https://python.org (check 'Add to PATH' during install), then re-run this script."
        Warn "If you just installed it via winget, try closing and reopening this terminal first."
        exit 1
    }
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
    Ok "Node.js $(node -v) found"
} else {
    Offer-WingetInstall "Node.js" "OpenJS.NodeJS.LTS" | Out-Null
    if (-not (Node-Ok)) {
        Err "Node.js $MinNodeMajor+ still not available."
        Warn "Install it from https://nodejs.org, then re-run this script."
        Warn "If you just installed it via winget, try closing and reopening this terminal first."
        exit 1
    }
}

if (-not (Test-Command npm)) {
    Err "npm not found (usually ships with Node.js)."
    exit 1
}
Ok "npm $(npm -v) found"

# ---- 4. clone repo (skip if already inside it) ----------------------------------
if ((Test-Path "backend/server.py") -and (Test-Path "package.json")) {
    Info "Already inside the Scarlett repo - skipping clone."
} else {
    if (Test-Path $RepoDir) {
        Warn "'$RepoDir' already exists - using it instead of re-cloning."
    } else {
        Info "Cloning Scarlett..."
        Log "COMMAND git clone $RepoUrl $RepoDir"
        git clone $RepoUrl $RepoDir 2>&1 | Tee-Object -FilePath $LogFile -Append
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
Ok "Virtual environment ready ($(python --version))"

Info "Installing Python dependencies from requirements.txt - this can take a few minutes."
Info "Full output is being logged to $LogFile ..."
$beforePyPkgs = (pip freeze 2>$null)
python -m pip install --upgrade pip 2>&1 | Tee-Object -FilePath $LogFile -Append | Out-Null
pip install -r requirements.txt 2>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    Err "Python dependency install failed (exit $LASTEXITCODE) - see $LogFile for details"
    deactivate
    exit 1
}
$afterPyPkgs = (pip freeze 2>$null)
$newPyPkgs = Compare-Object -ReferenceObject $beforePyPkgs -DifferenceObject $afterPyPkgs -PassThru |
    Where-Object { $_ -notin $beforePyPkgs }
"" | Out-File -FilePath $LogFile -Append
"----- Newly installed/updated Python packages -----" | Out-File -FilePath $LogFile -Append
if ($newPyPkgs) {
    $newPyPkgs | Out-File -FilePath $LogFile -Append
    Ok "Installed $($newPyPkgs.Count) Python package(s) - full list in $LogFile"
} else {
    "(none - everything already satisfied)" | Out-File -FilePath $LogFile -Append
    Ok "Python dependencies already satisfied - nothing new installed"
}
"-----------------------------------------------------" | Out-File -FilePath $LogFile -Append

Info "Installing Playwright browsers..."
Log "COMMAND playwright install"
playwright install 2>&1 | Tee-Object -FilePath $LogFile -Append
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
Info "Installing frontend dependencies (npm install) - full output is being logged."
Log "COMMAND npm install"
npm install 2>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    Err "npm install failed (exit $LASTEXITCODE) - see $LogFile for details"
    exit 1
}
"" | Out-File -FilePath $LogFile -Append
"----- Top-level npm packages installed -----" | Out-File -FilePath $LogFile -Append
npm list --depth=0 2>&1 | Out-File -FilePath $LogFile -Append
"----------------------------------------------" | Out-File -FilePath $LogFile -Append
Ok "Frontend dependencies installed - top-level package list in $LogFile"

# ---- done ------------------------------------------------------------------------------
Log "Setup finished successfully."
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Full install log saved to: $LogFile" -ForegroundColor Cyan
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