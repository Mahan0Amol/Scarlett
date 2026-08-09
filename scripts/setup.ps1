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
# This script asks before installing (or removing/recreating) anything on
# your system. Nothing happens silently. A full log of everything that ran
# is written to scarlett-setup-<timestamp>.log in the current directory.

$ErrorActionPreference = "Stop"

# PowerShell 7.3+ introduced $PSNativeCommandUseErrorActionPreference, which
# defaults to $true. When enabled, ANY stderr output from a native command
# (git, uv, npm, playwright, winget, ...) is treated as a terminating error
# under $ErrorActionPreference = "Stop" - even when the command succeeded
# and the stderr text was just a normal progress/info message. This is the
# actual cause of the "Setup stopped unexpectedly: <some normal output
# line>" failures, and it applies regardless of any local
# $ErrorActionPreference toggling around individual command calls. Disable
# it globally. This line is a harmless no-op on Windows PowerShell 5.1,
# where the variable doesn't exist.
$PSNativeCommandUseErrorActionPreference = $false

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
$RepoUrl = "https://github.com/Mahan0Amol/Scarlett.git"
$RepoDir = "Scarlett"
$MinPythonMinor = 11
$MinNodeMajor = 18
$TotalSteps = 11
$script:StepNum = 0

$LogFile = "scarlett-setup-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
"Scarlett setup log - started $(Get-Date)" | Out-File -FilePath $LogFile -Encoding utf8

# Symbols are built from code points, not typed as literal characters, so the
# script source stays plain ASCII. That avoids the classic PowerShell 5.1
# problem where a non-UTF8 console codepage mangles literal unicode saved in
# the .ps1 file into mojibake.
$script:SymOk    = [char]0x2713   # check mark
$script:SymCross = [char]0x2717   # cross mark
$script:SymWarn  = [char]0x26A0   # warning triangle
$script:SymArrow = ">"

function Log($msg)  { "[$(Get-Date -Format 'HH:mm:ss')] $msg" | Out-File -FilePath $LogFile -Append -Encoding utf8 }
function Info($msg) { Write-Host "  $script:SymArrow $msg" -ForegroundColor Cyan; Log "INFO  $msg" }
function Ok($msg)   { Write-Host "  $script:SymOk $msg" -ForegroundColor Green; Log "OK    $msg" }
function Warn($msg) { Write-Host "  $script:SymWarn $msg" -ForegroundColor Yellow; Log "WARN  $msg" }
function Err($msg)  { Write-Host "  $script:SymCross $msg" -ForegroundColor Red; Log "ERROR $msg" }

# Every `catch {}` in this script logs before deciding what to do next -
# a silently swallowed exception is the one thing the Hermes review flagged
# and it's cheap to avoid. Call this from any catch block instead of a bare
# empty body.
function Log-Exception($context, $err) {
    Log "EXCEPTION [$context] $($err.Exception.Message)"
    Log "$($err.ScriptStackTrace)"
}

# Runs a native command (exe + args) without letting $ErrorActionPreference =
# "Stop" turn its normal stderr output (progress messages, version banners,
# npm/uv warnings, etc.) into a terminating error. Merges stdout+stderr,
# writes everything to the log file, optionally echoes it to the console,
# and returns the process's real exit code (from $LASTEXITCODE) instead of
# throwing. Use this for every external tool invocation whose output gets
# piped/merged - that's the pattern that was silently aborting the script.
#
# Also captures the merged output into $script:LastInvokeOutput so callers
# can inspect it afterwards (cert-error detection, debug-log lookup, etc.)
# without re-running the command or buffering twice.
function Invoke-Logged {
    param(
        [Parameter(Mandatory)][string]$Command,
        [string[]]$Arguments = @(),
        [switch]$Quiet
    )
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    $captured = New-Object System.Collections.Generic.List[string]

    # Stream each line to the console and the log file as it arrives,
    # instead of buffering into a variable (which would only show output
    # after the whole command finishes).
    & $Command @Arguments 2>&1 | ForEach-Object {
        $line = $_.ToString()
        $captured.Add($line)
        $line | Out-File -FilePath $LogFile -Append -Encoding utf8
        if (-not $Quiet) { Write-Host $line }
    }
    $exitCode = $LASTEXITCODE

    $ErrorActionPreference = $prevEAP
    $script:LastInvokeOutput = $captured -join "`n"

    return $exitCode
}

# Inspect the output of a failed pip/npm/uv command for the classic
# corporate-proxy / missing-root-CA signature and print a fix instead of
# leaving the user to decode "unable to get local issuer certificate"
# themselves. Returns $true when it recognized (and explained) the failure.
function Show-CertHint($output) {
    if (-not $output) { return $false }
    $isCertError = $output -match "unable to get local issuer certificate" `
        -or $output -match "self.signed certificate" `
        -or $output -match "CERTIFICATE_VERIFY_FAILED" `
        -or $output -match "UNABLE_TO_GET_ISSUER_CERT_LOCALLY" `
        -or $output -match "SELF_SIGNED_CERT_IN_CHAIN"
    if (-not $isCertError) { return $false }
    Warn "This looks like a TLS certificate-trust failure, not a real install problem."
    Info "  A corporate proxy or antivirus is likely intercepting HTTPS and presenting a"
    Info "  certificate your tools don't trust. To fix, point them at your org's root CA:"
    Info "    1. Get the corporate root CA as a .pem/.crt from your IT team."
    Info "    2. For Node/npm:   setx NODE_EXTRA_CA_CERTS `"C:\path\to\corp-ca.pem`""
    Info "    3. For pip/uv:     setx SSL_CERT_FILE `"C:\path\to\corp-ca.pem`""
    Info "    4. Open a NEW terminal (so the env var takes effect) and re-run this script."
    Info "  Quick (less secure) alternative for npm only:"
    Info "    npm config set strict-ssl false   (re-enable afterwards: npm config set strict-ssl true)"
    return $true
}

# On failure, npm prints only a terse summary; the real evidence lives in
# npm's own debug log. Locate and tail it so the console/log file is a
# self-contained diagnosis instead of "exit 1, details somewhere in a cache
# folder nobody will find."
function Show-NpmDebugLogTail([int]$TailLines = 100) {
    $output = $script:LastInvokeOutput
    $logPath = $null
    if ($output -and $output -match "A complete log of this run can be found in:\s*(?<path>[^\r\n]+)") {
        $candidate = $Matches['path'].Trim()
        if (Test-Path -LiteralPath $candidate) { $logPath = $candidate }
    }
    if (-not $logPath -and (Test-Command npm)) {
        try {
            $prevEAP = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            $cacheDir = (npm config get cache 2>$null | Select-Object -Last 1)
            $ErrorActionPreference = $prevEAP
            if ($cacheDir) {
                $logsDir = Join-Path ($cacheDir.Trim()) "_logs"
                if (Test-Path -LiteralPath $logsDir) {
                    $newest = Get-ChildItem -LiteralPath $logsDir -Filter "*-debug-*.log" -ErrorAction SilentlyContinue |
                        Sort-Object LastWriteTime -Descending | Select-Object -First 1
                    if ($newest) { $logPath = $newest.FullName }
                }
            }
        } catch { Log-Exception "Show-NpmDebugLogTail:cache-lookup" $_ }
    }
    if (-not $logPath) {
        Warn "npm debug log could not be located - see $LogFile for what npm printed."
        return
    }
    try {
        $tail = Get-Content -LiteralPath $logPath -Tail $TailLines -ErrorAction Stop
        Log "---- npm debug log tail: $logPath ----"
        $tail | Out-File -FilePath $LogFile -Append -Encoding utf8
        Log "---- end npm debug log ----"
        Warn "npm debug log tail written to $LogFile ($logPath)"
    } catch {
        Log-Exception "Show-NpmDebugLogTail:read" $_
        Warn "Could not read npm debug log at $logPath - see $LogFile"
    }
}

function Show-Banner {
    Write-Host ""
    Write-Host "   +-----------------------------+" -ForegroundColor Magenta
    Write-Host "   |          SCARLETT           |" -ForegroundColor Magenta
    Write-Host "   |         setup script        |" -ForegroundColor Magenta
    Write-Host "   +-----------------------------+" -ForegroundColor Magenta
    Write-Host ""
}

function Show-Step($title) {
    $script:StepNum += 1
    Write-Host ""
    Write-Host "[$($script:StepNum)/$TotalSteps] " -ForegroundColor DarkGray -NoNewline
    Write-Host $title -ForegroundColor White
}

function Show-Divider { Write-Host "  --------------------------------" -ForegroundColor DarkGray }

# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
# Everything below runs inside one try/catch so any unexpected failure ends
# with a clear message and a pointer to the log, instead of a raw stack trace.
function Invoke-Main {

Show-Banner
Info "Logging full output to: $LogFile"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# Ask a yes/no question.
#   Confirm "question" "yes"  -> shows [Y/n], empty answer = yes
#   Confirm "question" "no"   -> shows [y/N], empty answer = no  (default)
function Confirm($prompt, $default = "no") {
    $suffix = if ($default -eq "yes") { "[Y/n]" } else { "[y/N]" }
    $reply = Read-Host "  $prompt $suffix"
    Log "PROMPT $prompt -> $(if ($reply) { $reply } else { "<default:$default>" })"
    if ([string]::IsNullOrWhiteSpace($reply)) {
        return ($default -eq "yes")
    }
    return ($reply -match '^[Yy]')
}

# Ask for confirmation before a *mandatory* step. If declined, Scarlett
# cannot continue, so we explain why and exit cleanly.
function Require-Confirm($prompt) {
    if (-not (Confirm $prompt "yes")) {
        Err "Can't continue without this - Scarlett needs it to run."
        exit 1
    }
}

# Refreshes $env:Path from the registry so newly-installed tools (e.g. via
# winget) become visible in this same session without reopening the shell.
function Refresh-Path {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user    = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Offer-WingetInstall($name, $wingetId) {
    if (-not (Confirm "$name was not found. Install it now via winget?" "yes")) {
        Warn "Skipping $name install - you'll need to install it yourself before Scarlett will run."
        return $false
    }
    if (-not (Test-Command winget)) {
        Err "winget is not available on this system (needs Windows 10 2004+ / Windows 11)."
        Warn "Install $name manually, then re-run this script."
        return $false
    }
    Info "Installing $name via winget (id: $wingetId) - full output is being logged."
    Log "COMMAND winget install --id $wingetId -e --silent --accept-package-agreements --accept-source-agreements"
    $exitCode = Invoke-Logged -Command "winget" -Arguments @(
        "install", "--id", $wingetId, "-e", "--silent",
        "--accept-package-agreements", "--accept-source-agreements"
    )
    # 0x8A15002B / -1978335189 = APPINSTALLER_CLI_ERROR_UPDATE_NOT_APPLICABLE.
    # winget treats a re-`install` of a package it already has registered as
    # an upgrade, finds no newer version, and bails with this code - even
    # when the binary is missing from PATH (stale registration, files
    # removed outside winget, or a missing shim). Since we're only here
    # because the tool was NOT found, a plain install dead-ends forever;
    # retry once with --force to repair the registration.
    if ($exitCode -eq -1978335189) {
        Warn "winget reports $name already registered but not newer - retrying with --force to repair it."
        Log "COMMAND winget install --id $wingetId -e --silent --force --accept-package-agreements --accept-source-agreements"
        $exitCode = Invoke-Logged -Command "winget" -Arguments @(
            "install", "--id", $wingetId, "-e", "--silent", "--force",
            "--accept-package-agreements", "--accept-source-agreements"
        )
    }
    $success = $exitCode -eq 0
    if ($success) { Ok "$name installed" } else { Err "$name install failed (exit $exitCode) - see $LogFile" }
    Refresh-Path
    return $success
}

# ---- 1. git ------------------------------------------------------------------
Show-Step "git"
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
Show-Step "Python $MinPythonMinor+"
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
            } catch { Log-Exception "Find-GoodPython:$candidate" $_ }
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
Show-Step "Node.js $MinNodeMajor+"
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

# ---- 4. ffmpeg -------------------------------------------------------------------
Show-Step "ffmpeg"
$HasFfmpeg = $false
if (Test-Command ffmpeg) {
    Ok "ffmpeg found"
    $HasFfmpeg = $true
} else {
    if (Offer-WingetInstall "ffmpeg" "Gyan.FFmpeg") {
        if (Test-Command ffmpeg) { $HasFfmpeg = $true }
    }
    if (-not $HasFfmpeg) {
        Warn "Continuing without ffmpeg - voice features that rely on audio conversion may not work."
        Warn "Install it later: https://ffmpeg.org/download.html"
    }
}

# ---- 5. uv (fast Python package installer) ---------------------------------------
Show-Step "uv (Python package installer)"
$script:UvCmd = $null
function Find-Uv {
    if (Test-Command uv) { return (Get-Command uv).Source }
    $candidate = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path $candidate) { return $candidate }
    return $null
}

$found = Find-Uv
if ($found) {
    $script:UvCmd = $found
    Ok "uv found ($(& $found --version))"
} else {
    Warn "uv was not found (used to install Python packages quickly)"
    Require-Confirm "Install uv now?"
    Info "Installing uv..."
    Log "COMMAND irm https://astral.sh/uv/install.ps1 | iex"
    try {
        $installScript = Invoke-RestMethod -Uri "https://astral.sh/uv/install.ps1"
        $installScript | Out-File -FilePath $LogFile -Append -Encoding utf8

        # The astral install script writes normal progress/info lines to
        # stderr. Relax $ErrorActionPreference while it runs so those
        # lines aren't treated as terminating errors (same issue as the
        # other external tools below), and stream each line as it arrives.
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        Invoke-Expression $installScript 2>&1 | ForEach-Object {
            $line = $_.ToString()
            $line | Out-File -FilePath $LogFile -Append -Encoding utf8
            Write-Host $line
        }
        $ErrorActionPreference = $prevEAP
    } catch {
        Log-Exception "uv-install" $_
        Err "uv installer failed: $($_.Exception.Message)"
        Warn "See $LogFile for details. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    }
    Refresh-Path
    $found = Find-Uv
    if (-not $found) {
        Err "uv installer finished but the binary could not be found."
        Warn "Install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    }
    $script:UvCmd = $found
    Ok "uv installed ($(& $found --version))"
}

# ---- 6. clone repo (skip if already inside it) ----------------------------------
Show-Step "Scarlett repository"

# A directory that merely contains a `.git` folder is not necessarily a
# usable repository - an interrupted clone can leave a `.git` with no
# resolvable HEAD, which later breaks `git pull`/`git checkout` in ways
# that look nothing like "clone failed." Verify with git itself rather
# than trusting Test-Path.
function Test-ValidGitRepo($path) {
    if (-not (Test-Path (Join-Path $path ".git"))) { return $false }
    Push-Location $path
    try {
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = 0
        $null = git rev-parse --is-inside-work-tree 2>$null
        $revParseOk = ($LASTEXITCODE -eq 0)
        $global:LASTEXITCODE = 0
        $null = git rev-parse --verify HEAD 2>$null
        $hasCommit = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $prevEAP
        return ($revParseOk -and $hasCommit)
    } catch {
        Log-Exception "Test-ValidGitRepo" $_
        return $false
    } finally {
        Pop-Location
    }
}

# Clones $RepoUrl into $RepoDir. Tries `git clone` first; if that fails
# (network hiccup, corporate proxy blocking the git protocol, etc.) falls
# back to downloading the branch as a ZIP so a flaky connection doesn't
# hard-block setup. The ZIP path re-inits git so later `git pull`-style
# updates still work.
function Install-ScarlettRepo {
    Info "Cloning Scarlett..."
    Log "COMMAND git clone $RepoUrl $RepoDir"
    $cloneExitCode = Invoke-Logged -Command "git" -Arguments @("clone", $RepoUrl, $RepoDir)

    if ($cloneExitCode -eq 0 -and (Test-ValidGitRepo $RepoDir)) {
        Ok "Cloned into .\$RepoDir"
        return $true
    }

    if (Test-Path $RepoDir) {
        Remove-Item -Recurse -Force $RepoDir -ErrorAction SilentlyContinue
    }

    Warn "git clone failed (exit $cloneExitCode) - trying a ZIP download instead."
    Show-CertHint $script:LastInvokeOutput | Out-Null
    try {
        $zipUrl = "https://github.com/Mahan0Amol/Scarlett/archive/refs/heads/main.zip"
        $zipPath = Join-Path $env:TEMP "scarlett-setup-download.zip"
        $extractPath = Join-Path $env:TEMP "scarlett-setup-extract"

        Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
        if (Test-Path $extractPath) { Remove-Item -Recurse -Force $extractPath }
        Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

        $extractedDir = Get-ChildItem $extractPath -Directory | Select-Object -First 1
        if (-not $extractedDir) { throw "ZIP archive did not contain a top-level folder." }

        Move-Item $extractedDir.FullName $RepoDir -Force
        Ok "Downloaded and extracted ZIP into .\$RepoDir"

        # Re-init git so `git pull` works on a future re-run of this script.
        Push-Location $RepoDir
        try {
            git init 2>$null | Out-Null
            git remote add origin $RepoUrl 2>$null | Out-Null
            $prevEAP = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            git fetch --depth 1 origin main 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                git checkout -f -B main FETCH_HEAD 2>&1 | Out-Null
            } else {
                Warn "Repo initialized from ZIP, but couldn't re-attach it to origin/main for future updates."
            }
            $ErrorActionPreference = $prevEAP
        } finally {
            Pop-Location
        }

        Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force $extractPath -ErrorAction SilentlyContinue
        return $true
    } catch {
        Log-Exception "Install-ScarlettRepo:zip-fallback" $_
        Err "ZIP download also failed: $($_.Exception.Message)"
        Err "See $LogFile for details."
        return $false
    }
}

if ((Test-Path "backend/server.py") -and (Test-Path "package.json")) {
    Ok "Already inside the Scarlett repo - skipping clone."
}
elseif (Test-ValidGitRepo $RepoDir) {
    Warn "'$RepoDir' is already a Scarlett repository - using it."
    Set-Location $RepoDir
}
elseif (Test-Path $RepoDir) {
    # Present but broken (interrupted clone, corrupted .git, or not a repo
    # at all). Move it aside rather than deleting outright - never destroy
    # something the user might still want without asking first.
    Warn "'$RepoDir' already exists but is not a valid, complete git repository."
    if (Confirm "Move it aside and re-clone into a fresh .\$RepoDir?" "yes") {
        $backupDir = "$RepoDir.broken-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        try {
            Move-Item -LiteralPath $RepoDir -Destination $backupDir -ErrorAction Stop
            Warn "Moved the old folder to .\$backupDir"
        } catch {
            Log-Exception "repo-move-aside" $_
            Err "Could not move '$RepoDir' aside: $($_.Exception.Message)"
            Err "Close any programs using files in it (editors, terminals) and try again."
            exit 1
        }
        if (-not (Install-ScarlettRepo)) { exit 1 }
        Set-Location $RepoDir
    } else {
        Err "Please remove or rename '$RepoDir' yourself, then run setup again."
        exit 1
    }
}
else {
    Require-Confirm "Clone the Scarlett repository into .\$RepoDir?"
    if (-not (Install-ScarlettRepo)) { exit 1 }
    Set-Location $RepoDir
}

# ---- 7. virtual environment --------------------------------------------------------
Show-Step "Python virtual environment"
$VenvPy = "venv\Scripts\python.exe"

# Creates .\venv and verifies it actually worked - the previous version of
# this script never checked `python -m venv`'s exit code, so a failure
# (e.g. antivirus locking a file mid-write) looked like success until the
# next step failed with a confusing "python.exe not found."
function New-ScarlettVenv {
    Info "Creating virtual environment..."
    Log "COMMAND $pythonBin -m venv venv"
    $exitCode = Invoke-Logged -Command $pythonBin -Arguments @("-m", "venv", "venv")
    if ($exitCode -ne 0 -or -not (Test-Path $VenvPy)) {
        Err "Virtual environment creation failed (exit $exitCode) - see $LogFile for details"
        exit 1
    }
    Ok "Virtual environment ready ($(& $VenvPy --version))"
}

if (Test-Path "venv") {
    if (Test-Path $VenvPy) {
        Ok "Virtual environment already exists ($(& $VenvPy --version))"
    } else {
        Warn "A 'venv' folder exists but looks broken."
        Require-Confirm "Remove it and create a fresh virtual environment?"
        # On Windows, a still-running Scarlett process (backend server left
        # open in another terminal) holds venv's .pyd files open and turns
        # a plain delete into "Access to the path is denied." Rename-then-
        # delete works even while a handle is held (renames don't require
        # the target to be unmapped, only in-place delete/replace does),
        # so the fresh venv can be created immediately either way.
        $staleName = "venv.stale.$(Get-Date -Format 'yyyyMMddHHmmss')"
        $removed = $false
        try {
            Rename-Item -Path "venv" -NewName $staleName -ErrorAction Stop
            Remove-Item -Recurse -Force $staleName -ErrorAction SilentlyContinue
            $removed = $true
            if (Test-Path $staleName) {
                Warn "Old venv parked at .\$staleName (something still has it open); safe to delete manually later."
            }
        } catch {
            Log-Exception "venv-rename-aside" $_
            Warn "Could not rename the old venv aside ($($_.Exception.Message)) - trying a direct delete."
        }
        if (-not $removed) {
            Remove-Item -Recurse -Force "venv" -ErrorAction SilentlyContinue
            if (Test-Path "venv") {
                Start-Sleep -Seconds 2
                try {
                    Remove-Item -Recurse -Force "venv" -ErrorAction Stop
                } catch {
                    Log-Exception "venv-delete-retry" $_
                    Err "Could not remove the old 'venv' folder: $($_.Exception.Message)"
                    Err "Close any running Scarlett/Python processes using it and try again."
                    exit 1
                }
            }
        }
        New-ScarlettVenv
    }
} else {
    Require-Confirm "Create a Python virtual environment in .\venv?"
    New-ScarlettVenv
}

# ---- 8. python dependencies (installed with uv, into the venv above) -------------
Show-Step "Python dependencies"
Require-Confirm "Install Python dependencies from requirements.txt (via uv)?"
Info "Installing Python dependencies - this can take a few minutes."
Info "Full output is being logged to $LogFile ..."
Log "COMMAND $($script:UvCmd) pip install --python $VenvPy -r requirements.txt"
$exitCode = Invoke-Logged -Command $script:UvCmd -Arguments @(
    "pip", "install", "--python", $VenvPy, "-r", "requirements.txt"
)
if ($exitCode -ne 0) {
    Err "Python dependency install failed (exit $exitCode) - see $LogFile for details"
    if (-not (Show-CertHint $script:LastInvokeOutput)) {
        Warn "Common fixes: check your internet connection, or re-run with a VPN/proxy disabled."
    }
    exit 1
}

$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$installedPkgs = & $script:UvCmd pip list --python $VenvPy 2>$null
$ErrorActionPreference = $prevEAP

"" | Out-File -FilePath $LogFile -Append
"----- Python packages after install -----" | Out-File -FilePath $LogFile -Append
$installedPkgs | Out-File -FilePath $LogFile -Append
"------------------------------------------" | Out-File -FilePath $LogFile -Append
Ok "Python dependencies installed - full list in $LogFile"

# ---- 9. playwright browsers ---------------------------------------------------------
Show-Step "Playwright browsers"
if (Confirm "Install Playwright browser binaries (needed for browser automation features)?" "yes") {
    Info "Installing Playwright browsers..."
    Log "COMMAND $VenvPy -m playwright install"
    $exitCode = Invoke-Logged -Command $VenvPy -Arguments @("-m", "playwright", "install")
    if ($exitCode -ne 0) {
        Warn "Playwright browser install failed - see $LogFile for details."
        Show-CertHint $script:LastInvokeOutput | Out-Null
        Warn "You can retry later with: $VenvPy -m playwright install"
    } else {
        Ok "Playwright ready"
    }
} else {
    Warn "Skipping Playwright - browser automation features won't work until you run:"
    Warn "  $VenvPy -m playwright install"
}

# ---- 10. env file --------------------------------------------------------------------
Show-Step ".env configuration"
if (Test-Path "backend\.env") {
    Ok "backend\.env already exists - leaving it untouched"
} else {
    Copy-Item "backend\.env.example" "backend\.env"
    Ok "Created backend\.env from template"

    Write-Host ""
    Write-Host "Gemini API Key setup" -ForegroundColor Cyan
    Write-Host "You can also set this later from Full Settings or manually in backend\.env."
    Write-Host ""

    $geminiApiKey = Read-Host "Enter your GEMINI_API_KEY (leave empty to skip)"

    if (-not [string]::IsNullOrWhiteSpace($geminiApiKey)) {
        Add-Content -Path "backend\.env" -Value "`nGEMINI_API_KEY=$geminiApiKey"
        Ok "GEMINI_API_KEY saved to backend\.env"
    } else {
        Warn "Skipped GEMINI_API_KEY. You can configure it later from Full Settings or manually in backend\.env."
    }
}

# ---- 11. frontend setup ---------------------------------------------------------------
Show-Step "Frontend dependencies"
Require-Confirm "Install frontend dependencies (npm install)?"
Info "Installing frontend dependencies - full output is being logged."
Log "COMMAND npm install"
$exitCode = Invoke-Logged -Command "npm" -Arguments @("install")
if ($exitCode -ne 0) {
    Err "npm install failed (exit $exitCode) - see $LogFile for details"
    if (-not (Show-CertHint $script:LastInvokeOutput)) {
        Show-NpmDebugLogTail
    }
    exit 1
}
"" | Out-File -FilePath $LogFile -Append
"----- Top-level npm packages installed -----" | Out-File -FilePath $LogFile -Append
Invoke-Logged -Command "npm" -Arguments @("list", "--depth=0") -Quiet | Out-Null
"----------------------------------------------" | Out-File -FilePath $LogFile -Append
Ok "Frontend dependencies installed - top-level package list in $LogFile"

# ---- done ------------------------------------------------------------------------------
Log "Setup finished successfully."
Show-Divider
Write-Host "  Setup complete." -ForegroundColor Green
Write-Host "  Full log: $LogFile" -ForegroundColor DarkGray
Show-Divider
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. cd $RepoDir   (if you're not already there)"
Write-Host "  2. npm run dev"
Write-Host "  3. Click the settings icon in the toolbar -> Full Settings -> .env, and add your GEMINI_API_KEY"
Write-Host "     (get one at https://ai.google.dev)"
Write-Host "  4. Hit the mic button and start talking."
Write-Host ""
if (-not $HasFfmpeg) {
    Write-Host "Note: ffmpeg was not installed. Some voice features may not work until you install it." -ForegroundColor Yellow
    Write-Host ""
}
Write-Host "Note: this script only wires up voice/text chat. Optional plugins (Gmail, printers,"
Write-Host "smart home, music) need their own setup - see README.md."

}

try {
    Invoke-Main
} catch {
    Write-Host ""
    Write-Host "  $([char]0x2717) Setup stopped unexpectedly: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  $([char]0x2717) Full details were logged to: $LogFile" -ForegroundColor Red
    "[$(Get-Date -Format 'HH:mm:ss')] FATAL $($_.Exception.Message)" | Out-File -FilePath $LogFile -Append -Encoding utf8
    "$($_.ScriptStackTrace)" | Out-File -FilePath $LogFile -Append -Encoding utf8
    exit 1
}