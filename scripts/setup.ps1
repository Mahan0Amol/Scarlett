# Scarlett setup script (Windows / PowerShell)
# Enhanced with Hermes-Agent features (uv, ffmpeg, zip fallback, lockfile churn fix)
#
# Usage (remote install):
#   irm https://raw.githubusercontent.com/Mahan0Amol/Scarlett/main/scripts/setup.ps1 | iex
#
# Usage (local, already cloned):
#   .\scripts\setup.ps1

 $RepoUrl = "https://github.com/Mahan0Amol/Scarlett.git"
 $RepoDir = "Scarlett"
 $Branch = "main"
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
        Err "winget is not available on this system."
        return $false
    }
    Info "Installing $name via winget (id: $wingetId) — full output is being logged."
    winget install --id $wingetId -e --silent --accept-package-agreements --accept-source-agreements 2>&1 | Tee-Object -FilePath $LogFile -Append
    $success = $LASTEXITCODE -eq 0
    if ($success) { Ok "$name installed" } else { Err "$name install failed" }
    Refresh-Path
    return $success
}

# Fix Windows 8.3 Short Path issue (e.g. C:\Users\FIRST~1.LAS)
function ConvertTo-LongPath {
    param([string]$Path)
    if ($Path -notmatch '~\d') { return $Path }
    try {
        $fso = New-Object -ComObject Scripting.FileSystemObject
        if ($fso.FolderExists($Path)) { return $fso.GetFolder($Path).Path }
        if ($fso.FileExists($Path)) { return $fso.GetFile($Path).Path }
    } catch {}
    return $Path
}

# 1. git
Info "Checking for git..."
if (Test-Command git) {
    Ok "git found ($(git --version))"
} else {
    Offer-WingetInstall "git" "Git.Git" | Out-Null
    if (-not (Test-Command git)) {
        Err "git is still not available. Install it manually and re-run."
        exit 1
    }
}

# 2. python
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
        exit 1
    }
}

# 3. node
Info "Checking for Node.js $MinNodeMajor+..."
function Node-Ok {
    if (-not (Test-Command node)) { return $false }
    $major = [int]((node -v) -replace "v", "" -split "\.")[0]
    return $major -ge $MinNodeMajor
}

if (Node-Ok) {
    Ok "Node.js $(node -v) found"
} else {
    Offer-WingetInstall "Node.js" "OpenJS.NodeJS.LTS" | Out-Null
    if (-not (Node-Ok)) {
        Err "Node.js $MinNodeMajor+ still not available."
        exit 1
    }
}
Ok "npm $(npm -v) found"

# 4. System Packages (ffmpeg & ripgrep)
Info "Checking for optional system tools (ffmpeg, ripgrep)..."
if (-not (Test-Command ffmpeg)) {
    Warn "ffmpeg not found. Required for advanced audio processing."
    Offer-WingetInstall "ffmpeg" "Gyan.FFmpeg" | Out-Null
} else { Ok "ffmpeg found" }

if (-not (Test-Command rg)) {
    Warn "ripgrep not found. Recommended for fast file searches."
    Offer-WingetInstall "ripgrep" "BurntSushi.ripgrep.MSVC" | Out-Null
} else { Ok "ripgrep found" }

# 5. clone repo (with ZIP Fallback)
if ((Test-Path "backend/server.py") -and (Test-Path "package.json")) {
    Info "Already inside the Scarlett repo - skipping clone."
} else {
    if (Test-Path $RepoDir) {
        Warn "'$RepoDir' already exists - using it."
    } else {
        Info "Cloning Scarlett..."
        git clone $RepoUrl $RepoDir 2>&1 | Tee-Object -FilePath $LogFile -Append
        if ($LASTEXITCODE -ne 0) { 
            Warn "Git clone failed (network/firewall?). Falling back to ZIP download..."
            $zipUrl = "https://github.com/Mahan0Amol/Scarlett/archive/refs/heads/$Branch.zip"
            $tmpZip = "$env:TEMP\scarlett-$Branch.zip"
            try {
                Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing
                Expand-Archive -Path $tmpZip -DestinationPath "$env:TEMP\scarlett-extract" -Force
                $extractedDir = Get-ChildItem "$env:TEMP\scarlett-extract" -Directory | Select-Object -First 1
                Move-Item $extractedDir.FullName $RepoDir
                Remove-Item $tmpZip, "$env:TEMP\scarlett-extract" -Recurse -Force -ErrorAction SilentlyContinue
                
                # Init git for future updates
                Push-Location $RepoDir
                git init 2>&1 | Out-Null
                git remote add origin $RepoUrl 2>&1 | Out-Null
                git fetch origin $Branch 2>&1 | Out-Null
                git checkout -f -B $Branch "origin/$Branch" 2>&1 | Out-Null
                Pop-Location
                Ok "Downloaded and extracted via ZIP fallback"
            } catch {
                Err "ZIP download also failed: $_"
                exit 1
            }
        }
    }
    Set-Location $RepoDir
}

# 6. uv installation (for fast pip installs)
Info "Setting up uv package manager for high-speed installs..."
 $uvCmd = "$env:USERPROFILE\.scarlett\bin\uv.exe"
if (-not (Test-Path $uvCmd)) {
    Info "Installing uv..."
    $env:UV_INSTALL_DIR = "$env:USERPROFILE\.scarlett\bin"
    $installScript = irm https://astral.sh/uv/install.ps1
    & $installScript 2>&1 | Tee-Object -FilePath $LogFile -Append
}
Ok "uv is ready"

# 7. backend setup (venv with standard pip, packages with uv)
Info "Setting up Python virtual environment..."
 $venvPath = ConvertTo-LongPath (Join-Path (Get-Location) "venv")
if (Test-Path $venvPath) {
    # Windows venv lock fix: rename stale venv if files are locked
    Warn "Existing venv found. Cleaning up..."
    $staleName = "venv.stale.$(Get-Date -Format 'yyyyMMddHHmmss')"
    try {
        Rename-Item -Path "venv" -NewName $staleName -ErrorAction Stop
        Remove-Item -Recurse -Force $staleName -ErrorAction SilentlyContinue
    } catch {
        Warn "Could not remove old venv (files locked). It will be cleaned up later."
    }
}

& $pythonBin -m venv venv
& .\venv\Scripts\Activate.ps1
Ok "Virtual environment ready ($(python --version))"

Info "Installing Python dependencies using uv (10x-100x faster than pip)..."
& $uvCmd pip install --upgrade pip 2>&1 | Tee-Object -FilePath $LogFile -Append
& $uvCmd pip install -r requirements.txt 2>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    Err "Python dependency install failed - see $LogFile"
    deactivate
    exit 1
}
Ok "Python dependencies installed"

Info "Installing Playwright browsers..."
playwright install 2>&1 | Tee-Object -FilePath $LogFile -Append
Ok "Playwright ready"

deactivate

# 8. env file
if (Test-Path "backend\.env") {
    Ok "backend\.env already exists - leaving it untouched"
} else {
    Copy-Item "backend\.env.example" "backend\.env"
    Ok "Created backend\.env from template"
    
    $geminiApiKey = Read-Host "Enter your GEMINI_API_KEY (leave empty to skip)"
    if (-not [string]::IsNullOrWhiteSpace($geminiApiKey)) {
        Add-Content -Path "backend\.env" -Value "`nGEMINI_API_KEY=$geminiApiKey"
        Ok "GEMINI_API_KEY saved"
    } else {
        Warn "Skipped GEMINI_API_KEY. Configure it later in backend\.env."
    }
}

# 9. frontend setup
Info "Installing frontend dependencies (npm install)..."
npm install 2>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    Err "npm install failed - see $LogFile"
    exit 1
}

# Lockfile churn fix: restore package-lock.json if package.json wasn't modified
if (Test-Path ".git") {
    $dirtyDiff = git diff --name-only 2>$null
    if ($dirtyDiff -contains "package-lock.json" -and $dirtyDiff -notcontains "package.json") {
        git checkout -- package-lock.json 2>$null
        Info "Discarded unnecessary npm lockfile churn"
    }
}

Ok "Frontend dependencies installed"

# Done
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  1. npm run dev"
Write-Host "  2. Add your GEMINI_API_KEY in backend\.env if you skipped it."