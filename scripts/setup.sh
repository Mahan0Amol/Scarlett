#!/usr/bin/env bash
# Scarlett setup script (Linux / macOS)
#
# Usage (remote install):
#   curl -fsSL https://raw.githubusercontent.com/Mahan0Amol/Scarlett/main/scripts/setup.sh | bash
#
# Usage (local, already cloned):
#   ./scripts/setup.sh
#
# This script asks before installing anything on your system. Nothing is
# installed silently. A full log of everything installed is written to
# scarlett-setup-<timestamp>.log in the current directory.

set -uo pipefail

REPO_URL="https://github.com/Mahan0Amol/Scarlett.git"
REPO_DIR="Scarlett"
MIN_PYTHON_MINOR=11
MIN_NODE_MAJOR=18

LOG_FILE="scarlett-setup-$(date +%Y%m%d-%H%M%S).log"
echo "Scarlett setup log — started $(date)" > "$LOG_FILE"

# ---- colors -----------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log_line() { echo "[$(date +%H:%M:%S)] $1" >> "$LOG_FILE"; }
info()  { echo -e "${BLUE}==>${NC} $1"; log_line "INFO  $1"; }
ok()    { echo -e "${GREEN}OK${NC}  $1"; log_line "OK    $1"; }
warn()  { echo -e "${YELLOW}!!${NC}  $1"; log_line "WARN  $1"; }
err()   { echo -e "${RED}XX${NC}  $1"; log_line "ERROR $1"; }

info "Logging full install output to: $LOG_FILE"

# ---- helpers ------------------------------------------------------------------
have() { command -v "$1" >/dev/null 2>&1; }

# Ask a yes/no question. Reads from /dev/tty so it still works when this
# script is being read from a pipe (curl ... | bash). Defaults to "no" if
# there's no real terminal to read from (e.g. running in CI).
ask_yes_no() {
    local prompt="$1"
    local reply
    if [ -r /dev/tty ]; then
        read -r -p "$prompt [y/N] " reply < /dev/tty
    else
        warn "No interactive terminal detected — assuming 'no' for: $prompt"
        reply="n"
    fi
    log_line "PROMPT $prompt -> $reply"
    case "$reply" in
        [yY][eE][sS]|[yY]) return 0 ;;
        *) return 1 ;;
    esac
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
    local cmd=""
    for pair in "$@"; do
        local mgr="${pair%%:*}"
        local pkgs="${pair#*:}"
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
    eval "$cmd" 2>&1 | tee -a "$LOG_FILE"
    local status=$?
    if [ $status -eq 0 ]; then
        ok "$label installed"
    else
        err "$label install failed (exit $status) — see $LOG_FILE for details"
    fi
    return $status
}

# Ask permission, then install. Returns 1 if the user declined or install failed.
offer_install() {
    local name="$1" label="$2"; shift 2
    if ! ask_yes_no "$name was not found. Install it now?"; then
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
info "Checking for git..."
if have git; then
    ok "git found ($(git --version))"
else
    offer_install "git" "git" apt:git dnf:git yum:git pacman:git zypper:git brew:git
    if ! have git; then
        err "git is still not available. Install it manually (https://git-scm.com) and re-run this script."
        exit 1
    fi
fi

# ---- 2. python ------------------------------------------------------------------
info "Checking for Python 3.$MIN_PYTHON_MINOR+..."
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if have "$candidate"; then
        ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
        major=${ver%%.*}; minor=${ver##*.}
        if [ -n "$ver" ] && [ "$major" -eq 3 ] && [ "$minor" -ge "$MIN_PYTHON_MINOR" ]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -n "$PYTHON_BIN" ]; then
    ok "Python $($PYTHON_BIN -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")') found ($PYTHON_BIN)"
else
    if offer_install "Python 3.$MIN_PYTHON_MINOR+" "python3" \
        apt:"python3 python3-venv python3-pip" \
        dnf:"python3 python3-pip" \
        yum:"python3 python3-pip" \
        pacman:"python python-pip" \
        zypper:"python3 python3-pip" \
        brew:"python@3.12"; then
        for candidate in python3.13 python3.12 python3.11 python3; do
            if have "$candidate"; then
                ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
                major=${ver%%.*}; minor=${ver##*.}
                if [ -n "$ver" ] && [ "$major" -eq 3 ] && [ "$minor" -ge "$MIN_PYTHON_MINOR" ]; then
                    PYTHON_BIN="$candidate"; break
                fi
            fi
        done
    fi
    if [ -z "$PYTHON_BIN" ]; then
        err "Python 3.$MIN_PYTHON_MINOR+ still not available."
        warn "Your package manager's default Python may be older than 3.$MIN_PYTHON_MINOR."
        warn "Try https://python.org, or on Ubuntu the deadsnakes PPA, or pyenv, then re-run this script."
        exit 1
    fi
fi

# ---- 3. node --------------------------------------------------------------------
info "Checking for Node.js $MIN_NODE_MAJOR+..."
node_ok() {
    have node && have npm && [ "$(node -e 'console.log(process.versions.node.split(".")[0])')" -ge "$MIN_NODE_MAJOR" ]
}

if node_ok; then
    ok "Node.js $(node -v) found"
else
    installed=false
    if [ "$PKG_MGR" = "apt" ] && ask_yes_no "Node.js $MIN_NODE_MAJOR+ was not found. Install it now via NodeSource (recommended, gets a current version)?"; then
        info "Setting up NodeSource repo for Node 20.x..."
        log_line "COMMAND curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
        if curl -fsSL https://deb.nodesource.com/setup_20.x 2>&1 | tee -a "$LOG_FILE" | sudo -E bash - ; then
            info "Installing nodejs package..."
            sudo apt-get install -y nodejs 2>&1 | tee -a "$LOG_FILE" && installed=true
        fi
    elif [ "$PKG_MGR" != "none" ]; then
        if offer_install "Node.js" "node" \
            apt:"nodejs npm" dnf:"nodejs npm" yum:"nodejs npm" \
            pacman:"nodejs npm" zypper:"nodejs npm" brew:"node"; then
            installed=true
        fi
    else
        ask_yes_no "No package manager found to install Node.js automatically. Continue anyway (you'll install it manually)?" || exit 1
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

# ---- 4. clone repo (skip if already inside it) -----------------------------------
if [ -f "backend/server.py" ] && [ -f "package.json" ]; then
    info "Already inside the Scarlett repo — skipping clone."
else
    if [ -d "$REPO_DIR" ]; then
        warn "'$REPO_DIR' already exists — using it instead of re-cloning."
    else
        info "Cloning Scarlett..."
        log_line "COMMAND git clone $REPO_URL $REPO_DIR"
        git clone "$REPO_URL" "$REPO_DIR" 2>&1 | tee -a "$LOG_FILE"
        [ ${PIPESTATUS[0]} -eq 0 ] || { err "Clone failed."; exit 1; }
        ok "Cloned into ./$REPO_DIR"
    fi
    cd "$REPO_DIR" || exit 1
fi

# ---- 5. portaudio (needed to build pyaudio) --------------------------------------
if [ "$CURRENT_OS" = "macos" ]; then
    if have brew && brew list portaudio >/dev/null 2>&1; then
        ok "portaudio already installed"
    else
        if ask_yes_no "portaudio (required to build pyaudio) was not found. Install it now via Homebrew?"; then
            info "Installing portaudio..."
            brew install portaudio 2>&1 | tee -a "$LOG_FILE" || warn "portaudio install failed — pyaudio may fail to build below."
        else
            warn "Skipping portaudio — 'pip install pyaudio' may fail without it."
        fi
    fi
elif [ "$CURRENT_OS" = "linux" ] && [ "$PKG_MGR" = "apt" ]; then
    if dpkg -s portaudio19-dev >/dev/null 2>&1; then
        ok "portaudio19-dev already installed"
    else
        if ask_yes_no "portaudio19-dev (required to build pyaudio) was not found. Install it now?"; then
            info "Installing portaudio19-dev..."
            sudo apt-get update -y && sudo apt-get install -y portaudio19-dev python3-dev 2>&1 | tee -a "$LOG_FILE"
        else
            warn "Skipping portaudio19-dev — 'pip install pyaudio' may fail without it."
        fi
    fi
fi

# ---- 6. backend setup -------------------------------------------------------------
info "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    "$PYTHON_BIN" -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
ok "Virtual environment ready ($(python --version))"

info "Installing Python dependencies from requirements.txt — this can take a few minutes."
info "Full output is being logged to $LOG_FILE ..."
BEFORE_PY_PKGS=$(pip freeze 2>/dev/null || true)
pip install --upgrade pip 2>&1 | tee -a "$LOG_FILE" >/dev/null
pip install -r requirements.txt 2>&1 | tee -a "$LOG_FILE"
PIP_STATUS=${PIPESTATUS[0]}
if [ $PIP_STATUS -ne 0 ]; then
    err "Python dependency install failed (exit $PIP_STATUS) — see $LOG_FILE for details"
    deactivate
    exit 1
fi
AFTER_PY_PKGS=$(pip freeze 2>/dev/null || true)
NEW_PY_PKGS=$(comm -13 <(echo "$BEFORE_PY_PKGS" | sort) <(echo "$AFTER_PY_PKGS" | sort))
{
    echo ""
    echo "----- Newly installed/updated Python packages -----"
    if [ -n "$NEW_PY_PKGS" ]; then echo "$NEW_PY_PKGS"; else echo "(none — everything already satisfied)"; fi
    echo "-----------------------------------------------------"
} >> "$LOG_FILE"
if [ -n "$NEW_PY_PKGS" ]; then
    NEW_COUNT=$(echo "$NEW_PY_PKGS" | wc -l | tr -d ' ')
    ok "Installed $NEW_COUNT Python package(s) — full list in $LOG_FILE"
else
    ok "Python dependencies already satisfied — nothing new installed"
fi

info "Installing Playwright browsers..."
log_line "COMMAND playwright install"
playwright install 2>&1 | tee -a "$LOG_FILE"
if [ "$CURRENT_OS" = "linux" ]; then
    if ask_yes_no "Install Playwright's system dependencies too (needs sudo, recommended)?"; then
        playwright install-deps 2>&1 | tee -a "$LOG_FILE" || warn "playwright install-deps failed — you may need to run it manually."
    fi
fi
ok "Playwright ready"

deactivate

# ---- 7. env file --------------------------------------------------------------------
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

    read -r -p "Enter your GEMINI_API_KEY (leave empty to skip): " gemini_api_key

    if [ -n "$gemini_api_key" ]; then
        if grep -q '^GEMINI_API_KEY=' backend/.env; then
            sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$gemini_api_key|" backend/.env
        else
            printf '\nGEMINI_API_KEY=%s\n' "$gemini_api_key" >> backend/.env
        fi

        ok "GEMINI_API_KEY saved to backend/.env"
    else
        warn "Skipped GEMINI_API_KEY — you can configure it later from Full Settings or manually in backend/.env."
    fi
fi

# ---- 8. frontend setup ----------------------------------------------------------------
info "Installing frontend dependencies (npm install) — full output is being logged."
log_line "COMMAND npm install"
npm install 2>&1 | tee -a "$LOG_FILE"
NPM_STATUS=${PIPESTATUS[0]}
if [ $NPM_STATUS -ne 0 ]; then
    err "npm install failed (exit $NPM_STATUS) — see $LOG_FILE for details"
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
echo ""
echo -e "${GREEN}Setup complete.${NC}"
echo -e "Full install log saved to: ${BLUE}$LOG_FILE${NC}"
echo ""
echo "Next steps:"
echo "  1. cd into the Scarlett folder (if you're not already there)"
echo "  2. npm run dev"
echo "  3. Click the settings icon in the toolbar -> Full Settings -> .env, and add your GEMINI_API_KEY"
echo "     (get one at https://ai.google.dev)"
echo "  4. Hit the mic button and start talking."
echo ""
echo "Note: this script only wires up voice/text chat. Optional plugins (Gmail, printers,"
echo "smart home, music) need their own setup — see README.md."