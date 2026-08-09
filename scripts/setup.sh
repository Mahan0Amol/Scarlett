#!/usr/bin/env bash
# Scarlett setup script (Linux / macOS)
#
# Usage (remote install):
#   curl -fsSL https://raw.githubusercontent.com/Mahan0Amol/Scarlett/main/scripts/setup.sh | bash
#
# Usage (local, already cloned):
#   ./scripts/setup.sh
#
# This script asks before installing (or removing/recreating) anything on
# your system. Nothing happens silently. A full log of everything that ran
# is written to scarlett-setup-<timestamp>.log in the current directory.

set -euo pipefail

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
CYAN='\033[0;36m'; MAGENTA='\033[0;35m'
DIM='\033[2m'; BOLD='\033[1m'; NC='\033[0m'

REPO_URL="https://github.com/Mahan0Amol/Scarlett.git"
REPO_DIR="Scarlett"
MIN_PYTHON_MINOR=11
MIN_NODE_MAJOR=18
TOTAL_STEPS=12
STEP_NUM=0

LOG_FILE="scarlett-setup-$(date +%Y%m%d-%H%M%S).log"
echo "Scarlett setup log — started $(date)" > "$LOG_FILE"

log_line() { echo "[$(date +%H:%M:%S)] $1" >> "$LOG_FILE"; }
info()  { echo -e "  ${CYAN}›${NC} $1"; log_line "INFO  $1"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; log_line "OK    $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; log_line "WARN  $1"; }
err()   { echo -e "  ${RED}✗${NC} $1"; log_line "ERROR $1"; }

banner() {
    echo -e "${MAGENTA}${BOLD}"
    echo "   ┌─────────────────────────────┐"
    echo "   │          SCARLETT           │"
    echo "   │         setup script        │"
    echo "   └─────────────────────────────┘"
    echo -e "${NC}"
}

step() {
    STEP_NUM=$((STEP_NUM + 1))
    echo ""
    echo -e "${DIM}[$STEP_NUM/$TOTAL_STEPS]${NC} ${BOLD}$1${NC}"
}

finish_line() { echo -e "  ${DIM}────────────────────────────────${NC}"; }

# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
# Any command that fails and isn't explicitly guarded by an `if` bubbles up
# here instead of leaving the terminal in a half-finished, confusing state.
on_error() {
    local exit_code=$? line=$1
    echo ""
    err "Setup stopped unexpectedly (line $line, exit code $exit_code)."
    err "Full details were logged to: $LOG_FILE"
    exit "$exit_code"
}
trap 'on_error $LINENO' ERR
trap 'echo ""; warn "Interrupted by user."; exit 130' INT TERM

banner
info "Logging full output to: $LOG_FILE"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
have() { command -v "$1" >/dev/null 2>&1; }

# Ask a yes/no question. Reads from /dev/tty so it still works when this
# script is being read from a pipe (curl ... | bash).
#   confirm "question" "yes"   -> prompt shows [Y/n], empty answer = yes
#   confirm "question" "no"    -> prompt shows [y/N], empty answer = no  (default)
confirm() {
    local prompt="$1" default="${2:-no}" reply suffix
    if [ "$default" = "yes" ]; then suffix="[Y/n]"; else suffix="[y/N]"; fi
    if [ -r /dev/tty ]; then
        read -r -p "  $prompt $suffix " reply < /dev/tty
    else
        warn "No interactive terminal detected — assuming 'no' for: $prompt"
        reply="n"
    fi
    log_line "PROMPT $prompt -> ${reply:-<default:$default>}"
    if [ -z "$reply" ]; then
        [ "$default" = "yes" ]
        return $?
    fi
    case "$reply" in
        [yY][eE][sS]|[yY]) return 0 ;;
        *) return 1 ;;
    esac
}

# Ask for confirmation before a *mandatory* step. If declined, Scarlett
# cannot continue, so we explain why and exit cleanly.
require_confirm() {
    local prompt="$1"
    if ! confirm "$prompt" "yes"; then
        err "Can't continue without this — Scarlett needs it to run."
        exit 1
    fi
}

os_name() {
    case "$(uname -s)" in
        Darwin) echo "macos" ;;
        Linux)  echo "linux" ;;
        *)      echo "unknown" ;;
    esac
}

# Detects a usable system package manager.
detect_pkg_manager() {
    if have brew; then echo "brew";
    elif have apt-get; then echo "apt";
    elif have dnf; then echo "dnf";
    elif have yum; then echo "yum";
    elif have pacman; then echo "pacman";
    elif have zypper; then echo "zypper";
    else echo "none"; fi
}

PKG_MGR=$(detect_pkg_manager)

# Runs an install command for the detected package manager, streaming and
# logging its full output. Usage: pkg_install "label" apt:pkgs dnf:pkgs ...
pkg_install() {
    local label="$1"; shift
    local cmd="" pkgs=""
    for pair in "$@"; do
        local mgr="${pair%%:*}"
        pkgs="${pair#*:}"
        if [ "$mgr" = "$PKG_MGR" ]; then
            case "$PKG_MGR" in
                apt)    cmd="sudo apt-get update -y && sudo apt-get install -y $pkgs" ;;
                dnf)    cmd="sudo dnf install -y $pkgs" ;;
                yum)    cmd="sudo yum install -y $pkgs" ;;
                pacman) cmd="sudo pacman -Sy --noconfirm $pkgs" ;;
                zypper) cmd="sudo zypper install -y $pkgs" ;;
                brew)   cmd="brew install $pkgs" ;;
            esac
            break
        fi
    done
    if [ -z "$cmd" ]; then
        err "Don't know how to install $label on this system (no supported package manager found)."
        return 1
    fi
    info "Installing $label via $PKG_MGR ($pkgs)..."
    log_line "COMMAND $cmd"
    if eval "$cmd" 2>&1 | tee -a "$LOG_FILE"; then
        ok "$label installed"
        return 0
    fi
    err "$label install failed — see $LOG_FILE for details"
    return 1
}

# Ask permission, then install. Returns 1 if the user declined or install failed.
offer_install() {
    local name="$1" label="$2"; shift 2
    if ! confirm "$name was not found. Install it now?" "yes"; then
        warn "Skipping $name install — you'll need to install it yourself before Scarlett will run."
        return 1
    fi
    if [ "$PKG_MGR" = "none" ]; then
        err "No supported package manager detected (looked for brew/apt/dnf/yum/pacman/zypper)."
        warn "Please install $name manually, then re-run this script."
        return 1
    fi
    pkg_install "$label" "$@"
}

CURRENT_OS=$(os_name)
info "Detected OS: $CURRENT_OS  (package manager: $PKG_MGR)"

# ---- 1. git -------------------------------------------------------------------
step "git"
if have git; then
    ok "git found ($(git --version))"
else
    offer_install "git" "git" apt:git dnf:git yum:git pacman:git zypper:git brew:git || true
    if ! have git; then
        err "git is still not available. Install it manually (https://git-scm.com) and re-run this script."
        exit 1
    fi
fi

# ---- 2. python ------------------------------------------------------------------
step "Python $MIN_PYTHON_MINOR+"
PYTHON_BIN=""
find_python() {
    for candidate in python3.13 python3.12 python3.11 python3; do
        if have "$candidate"; then
            local ver major minor
            ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
            major=${ver%%.*}; minor=${ver##*.}
            if [ -n "$ver" ] && [ "$major" = "3" ] && [ "$minor" -ge "$MIN_PYTHON_MINOR" ] 2>/dev/null; then
                PYTHON_BIN="$candidate"
                return 0
            fi
        fi
    done
    return 1
}

if find_python; then
    ok "Python $($PYTHON_BIN -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")') found ($PYTHON_BIN)"
else
    offer_install "Python 3.$MIN_PYTHON_MINOR+" "python3" \
        apt:"python3 python3-venv python3-pip" \
        dnf:"python3 python3-pip" \
        yum:"python3 python3-pip" \
        pacman:"python python-pip" \
        zypper:"python3 python3-pip" \
        brew:"python@3.12" || true
    find_python || true
    if [ -z "$PYTHON_BIN" ]; then
        err "Python 3.$MIN_PYTHON_MINOR+ still not available."
        warn "Your package manager's default Python may be older than 3.$MIN_PYTHON_MINOR."
        warn "Try https://python.org, or on Ubuntu the deadsnakes PPA, or pyenv, then re-run this script."
        exit 1
    fi
fi

# ---- 3. node --------------------------------------------------------------------
step "Node.js $MIN_NODE_MAJOR+"
node_ok() {
    have node && have npm && [ "$(node -e 'console.log(process.versions.node.split(".")[0])')" -ge "$MIN_NODE_MAJOR" ]
}

if node_ok; then
    ok "Node.js $(node -v) found"
else
    installed=false
    if [ "$PKG_MGR" = "apt" ] && confirm "Node.js $MIN_NODE_MAJOR+ was not found. Install it now via NodeSource (recommended, gets a current version)?" "yes"; then
        info "Setting up NodeSource repo for Node 20.x..."
        log_line "COMMAND curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
        if curl -fsSL https://deb.nodesource.com/setup_20.x 2>&1 | tee -a "$LOG_FILE" | sudo -E bash -; then
            info "Installing nodejs package..."
            if sudo apt-get install -y nodejs 2>&1 | tee -a "$LOG_FILE"; then installed=true; fi
        fi
    elif [ "$PKG_MGR" != "none" ]; then
        if offer_install "Node.js" "node" \
            apt:"nodejs npm" dnf:"nodejs npm" yum:"nodejs npm" \
            pacman:"nodejs npm" zypper:"nodejs npm" brew:"node"; then
            installed=true
        fi
    else
        confirm "No package manager found to install Node.js automatically. Continue anyway (you'll install it manually)?" "no" || exit 1
    fi

    if ! node_ok; then
        if [ "$installed" = true ]; then
            warn "Node.js was installed but is older than v$MIN_NODE_MAJOR."
            warn "Consider using nvm (https://github.com/nvm-sh/nvm) to install a current version, then re-run this script."
        else
            err "Node.js $MIN_NODE_MAJOR+ is required. Install it from https://nodejs.org and re-run this script."
        fi
        exit 1
    fi
    ok "Node.js $(node -v) installed"
fi

# ---- 4. ffmpeg ------------------------------------------------------------------
step "ffmpeg"
HAS_FFMPEG=false
if have ffmpeg; then
    ok "ffmpeg found ($(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}'))"
    HAS_FFMPEG=true
else
    if offer_install "ffmpeg" "ffmpeg" apt:ffmpeg dnf:ffmpeg yum:ffmpeg pacman:ffmpeg zypper:ffmpeg brew:ffmpeg; then
        HAS_FFMPEG=true
    else
        warn "Continuing without ffmpeg — voice features that rely on audio conversion may not work."
        warn "Install it later: https://ffmpeg.org/download.html"
    fi
fi

# ---- 5. uv (fast Python package installer) --------------------------------------
step "uv (Python package installer)"
UV_CMD=""
find_uv() {
    if have uv; then UV_CMD="uv"; return 0; fi
    if [ -x "$HOME/.local/bin/uv" ]; then UV_CMD="$HOME/.local/bin/uv"; return 0; fi
    if [ -x "$HOME/.cargo/bin/uv" ]; then UV_CMD="$HOME/.cargo/bin/uv"; return 0; fi
    return 1
}

if find_uv; then
    export PATH="$HOME/.local/bin:$PATH"
    ok "uv found ($($UV_CMD --version))"
else
    warn "uv was not found (used to install Python packages quickly)"
    require_confirm "Install uv now?"
    info "Installing uv..."
    UV_INSTALLER="$(mktemp)"
    log_line "COMMAND curl -LsSf https://astral.sh/uv/install.sh -o $UV_INSTALLER"
    if ! curl -LsSf https://astral.sh/uv/install.sh -o "$UV_INSTALLER" 2>>"$LOG_FILE"; then
        err "Failed to download the uv installer. Check your internet connection and try again."
        rm -f "$UV_INSTALLER"
        exit 1
    fi
    if ! sh "$UV_INSTALLER" 2>&1 | tee -a "$LOG_FILE"; then
        err "uv installation failed — see $LOG_FILE for details"
        rm -f "$UV_INSTALLER"
        exit 1
    fi
    rm -f "$UV_INSTALLER"
    export PATH="$HOME/.local/bin:$PATH"
    if ! find_uv; then
        err "uv installer finished but the binary could not be found."
        warn "Install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
    ok "uv installed ($($UV_CMD --version))"
fi

# ---- 6. clone repo (skip if already inside it) -----------------------------------
step "Scarlett repository"
if [ -f "backend/server.py" ] && [ -f "package.json" ]; then
    ok "Already inside the Scarlett repo — skipping clone."
elif [ -d "$REPO_DIR" ]; then
    warn "'$REPO_DIR' already exists — using it instead of re-cloning."
    cd "$REPO_DIR"
else
    require_confirm "Clone the Scarlett repository into ./$REPO_DIR?"
    info "Cloning Scarlett..."
    log_line "COMMAND git clone $REPO_URL $REPO_DIR"
    if ! git clone "$REPO_URL" "$REPO_DIR" 2>&1 | tee -a "$LOG_FILE"; then
        err "Clone failed. See $LOG_FILE for details."
        exit 1
    fi
    ok "Cloned into ./$REPO_DIR"
    cd "$REPO_DIR"
fi

# ---- 7. portaudio (needed to build pyaudio) --------------------------------------
step "portaudio (build dependency for pyaudio)"
if [ "$CURRENT_OS" = "macos" ]; then
    if have brew && brew list portaudio >/dev/null 2>&1; then
        ok "portaudio already installed"
    else
        if confirm "portaudio (required to build pyaudio) was not found. Install it now via Homebrew?" "yes"; then
            info "Installing portaudio..."
            if ! brew install portaudio 2>&1 | tee -a "$LOG_FILE"; then
                warn "portaudio install failed — pyaudio may fail to build below."
            fi
        else
            warn "Skipping portaudio — 'uv pip install pyaudio' may fail without it."
        fi
    fi
elif [ "$CURRENT_OS" = "linux" ] && [ "$PKG_MGR" = "apt" ]; then
    if dpkg -s portaudio19-dev >/dev/null 2>&1; then
        ok "portaudio19-dev already installed"
    else
        if confirm "portaudio19-dev (required to build pyaudio) was not found. Install it now?" "yes"; then
            info "Installing portaudio19-dev..."
            if ! { sudo apt-get update -y && sudo apt-get install -y portaudio19-dev python3-dev; } 2>&1 | tee -a "$LOG_FILE"; then
                warn "portaudio19-dev install failed — pyaudio may fail to build below."
            fi
        else
            warn "Skipping portaudio19-dev — 'uv pip install pyaudio' may fail without it."
        fi
    fi
else
    info "Nothing to do for this OS/package manager."
fi

# ---- 8. virtual environment -------------------------------------------------------
step "Python virtual environment"
VENV_PY="venv/bin/python"
if [ -d "venv" ]; then
    if [ -x "$VENV_PY" ]; then
        ok "Virtual environment already exists ($($VENV_PY --version))"
    else
        warn "A 'venv' folder exists but looks broken."
        require_confirm "Remove it and create a fresh virtual environment?"
        rm -rf venv
        info "Creating virtual environment..."
        "$PYTHON_BIN" -m venv venv
        ok "Virtual environment ready ($($VENV_PY --version))"
    fi
else
    require_confirm "Create a Python virtual environment in ./venv?"
    info "Creating virtual environment..."
    "$PYTHON_BIN" -m venv venv
    ok "Virtual environment ready ($($VENV_PY --version))"
fi

# ---- 9. python dependencies (installed with uv, into the venv above) -------------
step "Python dependencies"
require_confirm "Install Python dependencies from requirements.txt (via uv)?"
info "Installing Python dependencies — this can take a few minutes."
info "Full output is being logged to $LOG_FILE ..."
BEFORE_PY_PKGS=$("$UV_CMD" pip list --python "$VENV_PY" 2>/dev/null || true)
if ! "$UV_CMD" pip install --python "$VENV_PY" -r requirements.txt 2>&1 | tee -a "$LOG_FILE"; then
    err "Python dependency install failed — see $LOG_FILE for details"
    exit 1
fi
AFTER_PY_PKGS=$("$UV_CMD" pip list --python "$VENV_PY" 2>/dev/null || true)
{
    echo ""
    echo "----- Python packages after install -----"
    echo "$AFTER_PY_PKGS"
    echo "------------------------------------------"
} >> "$LOG_FILE"
ok "Python dependencies installed — full list in $LOG_FILE"

# ---- 10. playwright browsers -------------------------------------------------------
step "Playwright browsers"
if confirm "Install Playwright browser binaries (needed for browser automation features)?" "yes"; then
    info "Installing Playwright browsers..."
    log_line "COMMAND $VENV_PY -m playwright install"
    if ! "$VENV_PY" -m playwright install 2>&1 | tee -a "$LOG_FILE"; then
        warn "Playwright browser install failed — see $LOG_FILE for details."
    else
        ok "Playwright ready"
    fi
    if [ "$CURRENT_OS" = "linux" ]; then
        if confirm "Install Playwright's system dependencies too (needs sudo, recommended)?" "yes"; then
            if ! "$VENV_PY" -m playwright install-deps 2>&1 | tee -a "$LOG_FILE"; then
                warn "playwright install-deps failed — you may need to run it manually."
            fi
        fi
    fi
else
    warn "Skipping Playwright — browser automation features won't work until you run:"
    warn "  $VENV_PY -m playwright install"
fi

# ---- 11. env file --------------------------------------------------------------------
step ".env configuration"
if [ -f "backend/.env" ]; then
    ok "backend/.env already exists — leaving it untouched"
else
    cp backend/.env.example backend/.env
    ok "Created backend/.env from template"

    echo
    echo "Gemini API Key setup"
    echo "You can also configure it later from the in-app Full Settings screen"
    echo "or manually in backend/.env."
    echo

    gemini_api_key=""
    if [ -r /dev/tty ]; then
        read -r -p "Enter your GEMINI_API_KEY (leave empty to skip): " gemini_api_key < /dev/tty
    fi

    if [ -n "$gemini_api_key" ]; then
        if grep -q '^GEMINI_API_KEY=' backend/.env; then
            sed -i.bak "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$gemini_api_key|" backend/.env && rm -f backend/.env.bak
        else
            printf '\nGEMINI_API_KEY=%s\n' "$gemini_api_key" >> backend/.env
        fi
        ok "GEMINI_API_KEY saved to backend/.env"
    else
        warn "Skipped GEMINI_API_KEY — you can configure it later from Full Settings or manually in backend/.env."
    fi
fi
# API keys live in this file — keep it readable only by you.
chmod 600 backend/.env 2>/dev/null || true

# ---- 12. frontend setup ----------------------------------------------------------------
step "Frontend dependencies"
require_confirm "Install frontend dependencies (npm install)?"
info "Installing frontend dependencies — full output is being logged."
log_line "COMMAND npm install"
if ! npm install 2>&1 | tee -a "$LOG_FILE"; then
    err "npm install failed — see $LOG_FILE for details"
    exit 1
fi
{
    echo ""
    echo "----- Top-level npm packages installed -----"
    npm list --depth=0 2>&1
    echo "----------------------------------------------"
} >> "$LOG_FILE"
ok "Frontend dependencies installed — top-level package list in $LOG_FILE"

# ---- done -----------------------------------------------------------------------------
log_line "Setup finished successfully."
finish_line
echo -e "  ${GREEN}${BOLD}Setup complete.${NC}"
echo -e "  ${DIM}Full log:${NC} $LOG_FILE"
finish_line
echo ""
echo "Next steps:"
echo "  1. cd into the Scarlett folder (if you're not already there)"
echo "  2. npm run dev"
echo "  3. Click the settings icon in the toolbar -> Full Settings -> .env, and add your GEMINI_API_KEY"
echo "     (get one at https://ai.google.dev)"
echo "  4. Hit the mic button and start talking."
echo ""
if [ "$HAS_FFMPEG" = false ]; then
    echo -e "${YELLOW}Note: ffmpeg was not installed. Some voice features may not work until you install it.${NC}"
    echo ""
fi
echo "Note: this script only wires up voice/text chat. Optional plugins (Gmail, printers,"
echo "smart home, music) need their own setup — see README.md."