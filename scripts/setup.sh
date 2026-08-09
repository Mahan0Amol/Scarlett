#!/usr/bin/env bash
# Scarlett setup script (Linux / macOS)
# Enhanced with Hermes-Agent features (uv, ffmpeg, zip fallback, lockfile churn fix)

set -uo pipefail

REPO_URL="https://github.com/Mahan0Amol/Scarlett.git"
REPO_DIR="Scarlett"
BRANCH="main"
MIN_PYTHON_MINOR=11
MIN_NODE_MAJOR=18

LOG_FILE="scarlett-setup-$(date +%Y%m%d-%H%M%S).log"
echo "Scarlett setup log — started $(date)" > "$LOG_FILE"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log_line() { echo "[$(date +%H:%M:%S)] $1" >> "$LOG_FILE"; }
info()  { echo -e "${BLUE}==>${NC} $1"; log_line "INFO  $1"; }
ok()    { echo -e "${GREEN}OK${NC}  $1"; log_line "OK    $1"; }
warn()  { echo -e "${YELLOW}!!${NC}  $1"; log_line "WARN  $1"; }
err()   { echo -e "${RED}XX${NC}  $1"; log_line "ERROR $1"; }

have() { command -v "$1" >/dev/null 2>&1; }

ask_yes_no() {
    local prompt="$1"
    local reply
    if [ -r /dev/tty ]; then
        read -r -p "$prompt [y/N] " reply < /dev/tty
    else
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
        err "Don't know how to install $label on this system."
        return 1
    fi
    info "Installing $label via $PKG_MGR ($pkgs)..."
    eval "$cmd" 2>&1 | tee -a "$LOG_FILE"
    return $?
}

offer_install() {
    local name="$1" label="$2"; shift 2
    if ! ask_yes_no "$name was not found. Install it now?"; then
        warn "Skipping $name install."
        return 1
    fi
    if [ "$PKG_MGR" = "none" ]; then
        err "No supported package manager detected."
        return 1
    fi
    pkg_install "$label" "$@"
}

CURRENT_OS=$(os_name)
info "Detected OS: $CURRENT_OS  (package manager: $PKG_MGR)"

# 1. git
info "Checking for git..."
if have git; then
    ok "git found ($(git --version))"
else
    offer_install "git" "git" apt:git dnf:git yum:git pacman:git zypper:git brew:git || exit 1
fi

# 2. python
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
    ok "Python found ($PYTHON_BIN)"
else
    if offer_install "Python 3.$MIN_PYTHON_MINOR+" "python3" \
        apt:"python3 python3-venv python3-pip" \
        dnf:"python3 python3-pip" \
        pacman:"python python-pip" \
        brew:"python@3.12"; then
        PYTHON_BIN="python3"
    else
        err "Python 3.$MIN_PYTHON_MINOR+ not available."
        exit 1
    fi
fi

# 3. node
info "Checking for Node.js $MIN_NODE_MAJOR+..."
node_ok() {
    have node && have npm && [ "$(node -e 'console.log(process.versions.node.split(".")[0])')" -ge "$MIN_NODE_MAJOR" ]
}

if node_ok; then
    ok "Node.js $(node -v) found"
else
    if [ "$PKG_MGR" = "apt" ] && ask_yes_no "Node.js not found. Install via NodeSource?"; then
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - | tee -a "$LOG_FILE"
        sudo apt-get install -y nodejs | tee -a "$LOG_FILE" || exit 1
    else
        offer_install "Node.js" "node" apt:nodejs npm dnf:nodejs npm pacman:nodejs npm brew:node || exit 1
    fi
fi

# 4. System Packages (ffmpeg & ripgrep)
info "Checking for optional system tools (ffmpeg, ripgrep)..."
if ! have ffmpeg; then
    warn "ffmpeg not found (required for audio processing)."
    offer_install "ffmpeg" "ffmpeg" apt:ffmpeg dnf:ffmpeg pacman:ffmpeg brew:ffmpeg || true
else
    ok "ffmpeg found"
fi

if ! have rg; then
    warn "ripgrep not found (recommended for fast searches)."
    offer_install "ripgrep" "ripgrep" apt:ripgrep dnf:ripgrep pacman:ripgrep brew:ripgrep || true
else
    ok "ripgrep found"
fi

# 5. Portaudio (for pyaudio on linux/mac)
if [ "$CURRENT_OS" = "macos" ]; then
    if have brew && ! brew list portaudio >/dev/null 2>&1; then
        if ask_yes_no "portaudio (for pyaudio) not found. Install now?"; then
            brew install portaudio 2>&1 | tee -a "$LOG_FILE" || warn "portaudio install failed."
        fi
    fi
elif [ "$CURRENT_OS" = "linux" ] && [ "$PKG_MGR" = "apt" ]; then
    if ! dpkg -s portaudio19-dev >/dev/null 2>&1; then
        if ask_yes_no "portaudio19-dev not found. Install now?"; then
            sudo apt-get update -y && sudo apt-get install -y portaudio19-dev python3-dev 2>&1 | tee -a "$LOG_FILE"
        fi
    fi
fi

# 6. clone repo (with ZIP Fallback)
if [ -f "backend/server.py" ] && [ -f "package.json" ]; then
    info "Already inside the Scarlett repo — skipping clone."
else
    if [ -d "$REPO_DIR" ]; then
        warn "'$REPO_DIR' already exists — using it."
    else
        info "Cloning Scarlett..."
        if ! git clone "$REPO_URL" "$REPO_DIR" 2>&1 | tee -a "$LOG_FILE"; then
            warn "Git clone failed. Falling back to ZIP download..."
            curl -fsSL "https://github.com/Mahan0Amol/Scarlett/archive/refs/heads/$BRANCH.zip" -o /tmp/scarlett.zip
            mkdir -p /tmp/scarlett-extract
            unzip -q /tmp/scarlett.zip -d /tmp/scarlett-extract
            mv /tmp/scarlett-extract/Scarlett-* "$REPO_DIR"
            rm -rf /tmp/scarlett.zip /tmp/scarlett-extract
            
            cd "$REPO_DIR" || exit 1
            git init 2>&1 | tee -a "$LOG_FILE"
            git remote add origin "$REPO_URL" 2>&1 | tee -a "$LOG_FILE"
            git fetch origin "$BRANCH" 2>&1 | tee -a "$LOG_FILE"
            git checkout -f -B "$BRANCH" "origin/$BRANCH" 2>&1 | tee -a "$LOG_FILE"
            ok "Downloaded and extracted via ZIP fallback"
        else
            ok "Cloned into ./$REPO_DIR"
        fi
    fi
    cd "$REPO_DIR" || exit 1
fi

# 7. uv installation (for fast pip installs)
info "Setting up uv package manager for high-speed installs..."
export UV_INSTALL_DIR="$HOME/.scarlett/bin"
if [ "$CURRENT_OS" = "macos" ] || [ "$CURRENT_OS" = "linux" ]; then
    if ! have uv && [ ! -x "$UV_INSTALL_DIR/uv" ]; then
        curl -LsSf https://astral.sh/uv/install.sh | sh 2>&1 | tee -a "$LOG_FILE"
    fi
    export PATH="$UV_INSTALL_DIR:$PATH"
fi
UV_CMD="uv"
ok "uv is ready"

# 8. backend setup (venv with standard pip, packages with uv)
info "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    "$PYTHON_BIN" -m venv venv
fi
source venv/bin/activate
ok "Virtual environment ready ($(python --version))"

info "Installing Python dependencies using uv (10x-100x faster than pip)..."
 $UV_CMD pip install --upgrade pip 2>&1 | tee -a "$LOG_FILE"
 $UV_CMD pip install -r requirements.txt 2>&1 | tee -a "$LOG_FILE"
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    err "Python dependency install failed — see $LOG_FILE"
    deactivate
    exit 1
fi

info "Installing Playwright browsers..."
playwright install 2>&1 | tee -a "$LOG_FILE"
if [ "$CURRENT_OS" = "linux" ]; then
    if ask_yes_no "Install Playwright system dependencies (needs sudo, recommended)?"; then
        playwright install-deps 2>&1 | tee -a "$LOG_FILE" || warn "playwright install-deps failed."
    fi
fi
ok "Playwright ready"

deactivate

# 9. env file
if [ -f "backend/.env" ]; then
    ok "backend/.env already exists — leaving it untouched"
else
    cp backend/.env.example backend/.env
    ok "Created backend/.env from template"
    
    read -r -p "Enter your GEMINI_API_KEY (leave empty to skip): " gemini_api_key
    if [ -n "$gemini_api_key" ]; then
        if grep -q '^GEMINI_API_KEY=' backend/.env; then
            sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$gemini_api_key|" backend/.env
        else
            printf '\nGEMINI_API_KEY=%s\n' "$gemini_api_key" >> backend/.env
        fi
        ok "GEMINI_API_KEY saved"
    else
        warn "Skipped GEMINI_API_KEY."
    fi
fi

# 10. frontend setup
info "Installing frontend dependencies (npm install)..."
npm install 2>&1 | tee -a "$LOG_FILE"
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    err "npm install failed — see $LOG_FILE"
    exit 1
fi

# Lockfile churn fix: restore package-lock.json if package.json wasn't modified
if [ -d ".git" ]; then
    DIRTY_DIFF=$(git diff --name-only 2>/dev/null)
    if echo "$DIRTY_DIFF" | grep -q "package-lock.json" && ! echo "$DIRTY_DIFF" | grep -q "package.json"; then
        git checkout -- package-lock.json 2>/dev/null
        info "Discarded unnecessary npm lockfile churn"
    fi
fi

ok "Frontend dependencies installed"

# Done
echo -e "${GREEN}Setup complete.${NC}"
echo "Next steps:"
echo "  1. npm run dev"
echo "  2. Add your GEMINI_API_KEY in backend/.env if you skipped it."