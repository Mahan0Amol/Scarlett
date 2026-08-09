# Scarlett

**S**mart **C**onversational **A**ssistant for **R**eal-time **L**earning, **E**xecution & **T**ask **T**racking

A personal, Jarvis-style voice assistant with a real-time avatar UI, a live video feed, and a plugin system that lets it actually *do* things on your computer and around your home — not just talk about them.

Scarlett runs as a small **Electron desktop app** (React frontend) talking to a **Python backend** that streams your mic and webcam to **Google's Gemini Live API** and gets back a natural, interruptible voice conversation — with full function-calling access to a growing set of tools.

> ⚠️ **This is a personal project, published as-is.** It's built around one person's setup (their PC, their printer, their smart home devices). Read [Before You Run This Yourself](#before-you-run-this-yourself) before you push it publicly or hand it to someone else.

[![demo placeholder](https://github.com/Mahan0Amol/Scarlett/raw/main/docs/demo.png)](docs/demo.png)

---

## Table of Contents

- [What it can do](#what-it-can-do)
- [Architecture](#architecture)
- [Plugin System](#plugin-system)
- [Getting Started](#getting-started)
  - [Quick Install (recommended)](#quick-install-recommended)
  - [Manual Install](#manual-Install)
  - [1. Clone the repo](#1-clone-the-repo)
  - [2. Backend setup](#2-backend-setup)
  - [3. Frontend setup](#3-frontend-setup)
  - [4. Configure environment variables](#4-configure-environment-variables)
  - [5. Run it](#5-run-it)
- [Google OAuth Setup (Gmail)](#google-oauth-setup-gmail)
- [Project Structure](#project-structure)
- [Writing Your Own Plugin](#writing-your-own-plugin)
- [Platform Support](#platform-support)
- [Troubleshooting](#troubleshooting)
- [Before You Run This Yourself](#before-you-run-this-yourself)
- [Contributing](#contributing)
- [Credits](#credits)
- [License](#license)

---

## What it can do

Scarlett talks like a person (via Gemini's native-audio model), not a script — she interrupts, jokes, pushes back, and remembers things about you across the conversation. On top of that, she can:

- 🗣️ **Real-time voice conversation** — full-duplex audio in/out, live transcription of both sides, camera + screen-share vision so she can see what you see.
- 🧠 **Persistent memory** — a category-based information store she reads/writes herself (contacts, preferences, directories, "things I've learned about you") using a documented recall → match → update decision process baked into her system prompt.
- 🖥️ **Computer control** — keyboard/shortcut control, running terminal commands, reading/writing files inside project folders.
- 🌐 **Web agent** — drives a real browser (Playwright) to complete multi-step tasks, streaming a live view of the page to the UI.
- 🧊 **CAD generation** — generates and iterates parametric 3D models from natural language (via `build123d`) and shows them in an interactive viewer.
- 🖨️ **3D printing** — discovers OctoPrint/Moonraker/PrusaLink printers on the network, slices, starts prints, reports progress.
- 💡 **Smart home** — discovers and controls Kasa smart lights and smart door locks.
- 📧 **Email** — drafts and sends email in your voice/personality, from just a stated reason (no dictating subject/body).
- ♟️ **Games** — full interactive chess and backgammon matches against Scarlett, on-screen boards.
- 🎵 **Music** — search/play/control a local music library with a synced player UI.
- 🔒 **Optional face authentication** — lock/unlock the assistant with on-device face recognition (MediaPipe), off by default.
- 🧩 **A real plugin system** — every feature above is a self-contained plugin. Adding a new tool means adding a folder; nothing else in the app needs to change. Plugins can be packaged (`.splugin`), shared, and installed through a UI, similar to a tiny extension marketplace.

## Architecture

```
┌──────────────────────────┐        Socket.IO / REST        ┌───────────────────────────┐        Gemini Live API
│   Electron + React UI    │ <────────────────────────────> │   Python backend          │ <────────────────────>  (audio, video,
│   (src/)                 │                                 │   FastAPI + python-       │                          function calling,
│   - avatar / audio bars  │                                 │   socketio (backend/)     │                          google_search)
│   - chat, tool windows   │                                 │   - AudioLoop (core loop) │
│   - per-plugin UI panels │                                 │   - ToolDispatcher        │
└──────────────────────────┘                                 └─────────────┬─────────────┘
                                                                             │
                                                               ┌─────────────▼─────────────┐
                                                               │   Plugin registry          │
                                                               │   backend/plugins/*        │
                                                               │   (auto-discovered)        │
                                                               └────────────────────────────┘
```

- **`backend/Scarlett.py`** owns the `AudioLoop` — the core session with Gemini Live: mic/camera capture, audio playback, transcription, and Scarlett's full system prompt/personality.
- **`backend/server.py`** is the process entry point: a FastAPI app wrapped in a Socket.IO server. It owns app-wide settings, the plugin manager REST API, and every Socket.IO event the frontend listens to.
- **`backend/core/`** holds reusable mixins (`AudioIOMixin`, `VideoIOMixin`) and `ToolDispatcher`, which replaced what used to be a 500-line `if/elif` chain of tool handling.
- **`backend/plugins/`** is where every capability lives — see [Plugin System](#plugin-system) below.
- **`src/`** is the Electron renderer: a single large `App.jsx` that owns UI state and a Socket.IO client, plus one component per feature/plugin window. `Visualizer.jsx` renders the audio-reactive avatar with Three.js (`@react-three/fiber` + `@react-three/drei`).

## Plugin System

This is the part of the codebase worth understanding first if you want to extend Scarlett.

- Each plugin is a folder under `backend/plugins/<id>/`. Its Python module registers tools with a shared `ToolRegistry` using a `@tool(...)` decorator (see `plugins/base.py`).
- `plugins/loader.py` auto-discovers and imports every plugin folder at startup — **adding a capability is just adding a folder**, nothing else needs to be wired up.
- `core/tool_dispatcher.py` routes every Gemini function call to the right plugin handler, checks whether the tool is enabled in Settings, and — for tools flagged `requires_confirmation` — pops a confirmation prompt in the UI before running.
- Plugins that need one canonical, process-wide instance (an agent, a client, a connection pool) use the `lazy_singleton` helper in `plugins/base.py`, so both a tool handler *and* an unrelated REST route in `server.py` can reach the same instance without manual wiring.
- Plugins that ship a UI window declare it in `plugin.json` under `frontend`; installing one updates `src/plugins.manifest.json` and regenerates `src/pluginRegistry.jsx` automatically (`backend/plugin_tools/registry_sync.py`) — that file is generated, **never hand-edited**.
- Plugins can be **packaged** (`backend/plugin_tools/exporter.py` → a `.splugin` zip) and **installed** through the in-app Plugin Manager (Settings → Full Settings → Plugin Manager), which inspects the manifest, shows the user its pip/npm dependencies and requested permissions, and only installs after explicit confirmation.

See [Writing Your Own Plugin](#writing-your-own-plugin) for a minimal example.

## Getting Started

### Quick Install (recommended)

Scarlett ships with setup scripts under [`scripts/`](scripts/) that check for Python/Node/git, ask before installing anything missing, clone the repo if needed, create the virtual environment, install all backend and frontend dependencies, and set up your `.env` file. Nothing is installed silently — each script asks for confirmation before touching your system.

**Linux / macOS:**

```bash
curl -fsSL https://raw.githubusercontent.com/Mahan0Amol/Scarlett/main/scripts/setup.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/Mahan0Amol/Scarlett/main/scripts/setup.ps1 | iex
```

**Windows (no PowerShell experience needed):** download [`scripts/setup.bat`](scripts/setup.bat) and double-click it. It downloads and runs `setup.ps1` for you with the execution policy bypassed for that run only — it doesn't change your system's PowerShell policy.

> As with any script you pipe into your shell, it's worth opening the file and reading it first if you want to know exactly what it does before running it: [`setup.sh`](scripts/setup.sh) · [`setup.ps1`](scripts/setup.ps1) · [`setup.bat`](scripts/setup.bat).

Once a script finishes, skip ahead to [Run it](#5-run-it) — steps 1–4 below are handled for you. The manual steps are still here for anyone who wants to do it by hand or understand what the script is doing.

### Manual Install

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.11+** | Backend runtime |
| **Node.js 18+** and npm | Frontend/Electron build |
| **Google Gemini API key** | Get one at [ai.google.dev](https://ai.google.dev) — must have access to the **Live API** |
| **Git** | To clone the repo |
| **Windows 10/11** | Primary supported platform today — see [Platform Support](#platform-support) if you're on macOS/Linux |
| Working microphone & webcam | Required for voice/vision features |

This is an **Electron** app on the frontend — `package.json` points its `main` entry at `electron/main.js`, and `App.jsx` uses `window.require('electron')` for the frameless window controls (minimize/maximize/close). Before running, verify these four files actually exist at the repo root alongside `src/`:

```
electron/main.js
index.html
vite.config.js
tailwind.config.js
```

If any are missing, the frontend build/Electron shell will fail — check them into version control before continuing.

### 1. Clone the repo

```bash
git clone https://github.com/Mahan0Amol/Scarlett.git
cd Scarlett
```

### 2. Backend setup

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
playwright install
```

`requirements.txt` currently pulls in: `Pillow`, `PySide6`, `build123d`, `exceptiongroup`, `fastapi`, `google-genai`, `mediapipe`, `mss`, `mutagen`, `opencv-python`, `playwright`, `psutil`, `pyaudio`, `pyautogui`, `pydantic`, `python-dotenv`, `python-socketio`, `taskgroup`, `uvicorn`, `zeroconf`.

> **Note:** `PySide6` is listed but not currently imported anywhere in `backend/` — it's a leftover from an earlier desktop-GUI iteration of this project. Safe to remove if you confirm nothing in your fork uses it; leaving it in just costs extra install time and disk space (it's a large package).
>
> `pyaudio` can be finicky to install on some systems — on Windows it usually installs fine from a wheel; on macOS/Linux you may need `portaudio` installed via your system package manager first (e.g. `brew install portaudio` or `apt install portaudio19-dev`) before `pip install pyaudio` succeeds.

### 3. Frontend setup

```bash
npm install
```

Key runtime dependencies (from `package.json`, package name `Scarlett-v2` v1.0.0): `socket.io-client` (backend connection), `@mediapipe/tasks-vision` (hand-tracking cursor), `three` + `@react-three/fiber` + `@react-three/drei` (the 3D avatar/audio visualizer), `chess.js` / `react-chessboard` (chess plugin UI), `framer-motion` (animations), `lucide-react` (icons), `clsx` / `tailwind-merge` (conditional styling), and `electron` itself.

Dev tooling: `vite` + `@vitejs/plugin-react` (build), `tailwindcss` + `postcss` + `autoprefixer` (styling), `concurrently` + `wait-on` (orchestrates `npm run dev`), `cross-env`, and `electron` (currently pinned to `^28.2.0`).

> **License field mismatch:** `package.json` currently declares `"license": "ISC"`, while the repo's [`LICENSE`](LICENSE) file is MIT. Pick one and make them consistent — MIT is almost certainly the intended one given the LICENSE file and the [Credits](#credits)/[License](#license) sections below, so the fix is updating `package.json`'s `license` field to `"MIT"`.

### 4. Configure environment variables

Environment variables are set up in **two stages** — a starter file first, then the actual values through the app's UI:

1. In `backend/`, copy the example file and rename it:

   ```bash
   cd backend
   cp .env.example .env      # macOS/Linux
   copy .env.example .env    # Windows
   cd ..
   ```

   > ⚠️ The tracked `.env.example` currently ships with real personal defaults for `EMAIL_ADDRESS`, `USER_NAME`, and `USER_KNOWN_AS` instead of generic placeholders. Overwrite these with your own values in your local `.env` (or via the Full Settings UI in the next step) — and if you maintain this repo publicly, replace the placeholder values in `.env.example` itself so you're not shipping someone's real email address in the template.

2. Start Scarlett once (see [Run it](#5-run-it) below).
3. Click the **settings icon** in the toolbar → **Full Settings** → find the **.env** section.
4. Enter the values below there. They get written back into `backend/.env` for you.

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key (required — nothing works without this) |
| `OPENWEATHER_API_KEY` | Weather lookups |
| `EMAIL_ADDRESS` | SMTP sending account (use an app password, not your real password) |
| `EMAIL_IMAP` / `EMAIL_IMAP_PORT` | IMAP server for reading mail |
| `MUSIC_FOLDER_PATH` | Root folder the music plugin searches |
| `USER_NAME` | Your real name (used in the system prompt) |
| `USER_KNOWN_AS` | What Scarlett calls you ("sir", your name, a nickname, ...) |
| `OS` | Target OS string, used by a couple of platform-specific tools |

`backend/settings.json` holds everything that changes at runtime through the Settings UI instead of `.env`: face-auth toggle, per-tool enable/disable (`tool_permissions`), known printers/Kasa devices/door locks, selected mic/speaker/webcam, and cursor sensitivity for the hand-tracking cursor. It's created with sane defaults on first run if it doesn't exist yet.

> Only `GEMINI_API_KEY` is strictly required to get Scarlett talking. Everything else in the table above just unlocks the matching plugin (weather, email, music) — leave them blank and those plugins simply won't work until you fill them in.

### 5. Run it

**Normal mode** — one command, starts everything:

```bash
npm run dev
```

This runs `vite` and `electron .` together (via `concurrently` + `wait-on`), so the Electron window opens automatically once the Vite dev server on port `5173` is ready. It also launches the backend.

**Developer mode** — two terminals, useful if you want backend logs separate from the frontend:

```bash
# terminal 1 — backend
python backend/server.py         # serves on http://127.0.0.1:8000

# terminal 2 — frontend + Electron shell
npm run dev
```

Other useful scripts:

```bash
npm run build   # production Vite build
npm start        # launch Electron against the production build
```

Once the window opens, hit the **mic button** to start talking.

## Google OAuth Setup (Gmail)

To use Scarlett's Gmail features (the email plugin), you need your own Google OAuth credentials — Scarlett doesn't ship with shared ones.

1. **Create a Google Cloud project** at the [Google Cloud Console](https://console.cloud.google.com/). Name it anything, e.g. `Scarlett Gmail`.
2. **Enable the Gmail API**: *APIs & Services → Library* → search **Gmail API** → **Enable**.
3. **Configure the OAuth consent screen**: *Google Auth Platform → Branding* → set an application name (e.g. `Scarlett`) and fill in the required contact info. For **Audience**, choose **External** (or **Internal** if your account is part of a Google Workspace org and Scarlett is only for members of that org).
4. **Add Gmail permissions**: *Google Auth Platform → Data Access* → add the scope `https://mail.google.com/`. This lets Scarlett read, send, and modify/delete emails on your behalf.
5. **Create an OAuth client**: *Google Auth Platform → Clients → + Create Client* → Application type **Desktop app** → name it (e.g. `Scarlett Gmail`) → **Create**.
6. **Download `credentials.json`** for the client you just created, rename it exactly to `credentials.json`, and place it here:

   ```
   Scarlett/
   └── backend/
       └── plugins/
           └── email/
               ├── credentials.json
               └── (other files)
   ```

7. **Start Scarlett normally.** The first time you use a Gmail feature, it opens a Google sign-in page in your browser. Authorize it, and Scarlett stores the resulting token locally (`backend/plugins/email/token.json`) and reuses it for future sessions.

> **Security:** Never commit `credentials.json` or `token.json` to GitHub — they're authentication secrets. Make sure your `.gitignore` includes:
> ```
> **/credentials.json
> **/token.json
> ```
> Each separate Scarlett installation should use its own OAuth credentials.

## Project Structure

```
backend/
├── Scarlett.py              # AudioLoop: the Gemini Live session + system prompt
├── server.py                 # FastAPI + Socket.IO entry point, settings & plugin manager API
├── authenticator.py           # Optional face-auth
├── .env.example               # Template — copy to .env before first run
├── settings.json              # Runtime settings, created with defaults on first run
├── core/
│   ├── audio_io.py            # Mic capture / speaker playback mixin
│   ├── video_io.py            # Webcam / screen-share mixin
│   └── tool_dispatcher.py     # Routes Gemini tool calls to plugin handlers
├── plugins/                   # One folder per capability — see Plugin System
│   ├── base.py                # ToolRegistry, @tool decorator, lazy_singleton
│   ├── loader.py                # Auto-discovers & imports every plugin
│   ├── cad/ chess/ backgammon/ music/ printer/ smarthome/ web/  # manifest-based (installable/exportable)
│   └── cmd/ email/ files/ items/ keyboard/ project/ misc/       # built-in, no manifest
├── plugin_tools/
│   ├── importer.py             # Install a .splugin package
│   ├── exporter.py             # Package a plugin folder into a .splugin
│   └── registry_sync.py        # Keeps src/pluginRegistry.jsx generated from the manifest
└── web/full_settings.html      # Full settings page (env vars, tool permissions, plugin manager UI)

src/
├── App.jsx                    # Main renderer: layout, socket wiring, window management
├── Visualizer.jsx              # Audio-reactive 3D avatar (Three.js)
├── pluginRegistry.jsx           # AUTO-GENERATED — do not hand-edit
├── plugins.manifest.json        # Source of truth for installed UI plugins
└── components/                  # One component per feature/plugin window

electron/
└── main.js                     # Electron main process — window creation, frameless controls

scripts/
├── setup.sh                     # Linux/macOS installer — curl | bash
├── setup.ps1                    # Windows installer — irm | iex
└── setup.bat                    # Windows double-click wrapper around setup.ps1

docs/                           # Screenshots / demo assets
tests/                          # Test suite (see pytest.ini at repo root)
```

## Writing Your Own Plugin

Minimal example — `backend/plugins/hello/__init__.py`:

```python
from plugins.base import tool

@tool(
    name="say_hello",
    description="Says hello to someone by name.",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
async def say_hello(ctx, fc):
    name = fc.args.get("name", "there")
    return f"Hello, {name}!"
```

Steps:

1. Create `backend/plugins/<your_plugin_id>/__init__.py` with your `@tool`-decorated functions.
2. Add a `plugin.json` manifest (copy the shape from any existing plugin folder that has one, e.g. `backend/plugins/cad/`).
3. If your plugin needs a UI window, add a `frontend` entry in `plugin.json` pointing to a new component, e.g. `src/components/YourPluginWindow.jsx`.
4. Restart the backend. `loader.py` picks the new plugin up automatically, `Scarlett.py` includes its schema in the Gemini `tools` list, and `ToolDispatcher` routes calls to it — no other code changes needed.

To share your plugin with others, package it:

```bash
python backend/plugin_tools/exporter.py <path/to/your/plugin-folder> --output <path/to/your/output-folder>
```

This produces a `.splugin` file, installable by anyone through **Settings → Full Settings → Plugin Manager**.

## Platform Support

Scarlett is currently **built and tested on Windows only**. Several plugins assume a Windows environment:

- Shell commands like `cd /d` for drive switching
- `pyautogui` and keyboard-control tools that assume a Windows desktop
- Printer/smart-home discovery tools use Windows-oriented networking calls in places

If you're on **macOS or Linux**, expect to need adjustments to the `cmd`, `keyboard`, and `files` plugins at minimum before those features work. Voice conversation, the web agent, and CAD generation are less platform-dependent and more likely to work out of the box. If you get Scarlett running on another OS, the maintainer welcomes a PR or a heads-up (see [Contributing](#contributing)).

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Electron window never opens | Confirm `electron/main.js`, `index.html`, `vite.config.js`, `tailwind.config.js` exist at the repo root — they're required but not always present in every checkout. |
| `npm run dev` hangs on "waiting for Vite" | Port `5173` may already be in use by another process — stop it or change the Vite port in `vite.config.js`. |
| Backend fails to start / import errors | Make sure your virtual environment is activated before `pip install -r requirements.txt`, and that you're on Python 3.11+ (`python --version`). |
| `playwright install` fails or browser doesn't launch | Re-run `playwright install` inside the activated venv; on Linux you may also need `playwright install-deps`. |
| No response after hitting the mic button | Check `GEMINI_API_KEY` is set in `backend/.env` (or via Full Settings) and that the key has Live API access. |
| Email plugin errors on first use | Confirm `credentials.json` is in `backend/plugins/email/` and you completed the [OAuth flow](#google-oauth-setup-gmail); delete `token.json` and retry if a previous auth attempt was interrupted. |
| Printer/smart-home plugin finds no devices | These rely on local network discovery — make sure your machine, printer, and Kasa devices are all on the same network/subnet. |
| Face auth doesn't unlock | Confirm face-auth is enabled in Settings and a reference image exists (`reference.jpg`) — this feature is off by default. |

## Before You Run This Yourself

This repo was extracted directly from a working personal setup. Before you push it publicly or hand it to someone else, go through this checklist:

- [ ] **`backend/plugins/email/token.json`** — Google OAuth token for the email plugin. Never commit this.
- [ ] **`backend/plugins/email/credentials.json`** — Google OAuth client credentials. Never commit this.
- [ ] **`backend/settings.json`** — contains real device info (printer name/IP, selected mic/webcam). Fine to keep structurally, but scrub personal identifiers, or ship a `settings.example.json` and gitignore the real file.
- [ ] **`backend/.env`** — contains your real API keys and email account. Never commit this; only `.env.example` should be tracked.
- [ ] **`backend/.env.example`** — as tracked today, its defaults for `EMAIL_ADDRESS`, `USER_NAME`, and `USER_KNOWN_AS` are real personal values, not generic placeholders. Replace them with placeholders like `your_email@gmail.com` / `Your Name` before others clone this repo.
- [ ] **`reference.jpg`** (or similar) — the face-auth reference image, if you've enabled that feature. Never commit this.
- [ ] **`package.json`**`.license` field says `ISC`, but [`LICENSE`](LICENSE) is MIT — reconcile the two (see note in [Frontend setup](#3-frontend-setup)).
- [ ] Add/verify a proper **`.gitignore`** covering at minimum: `.env`, `venv/`, `node_modules/`, `*.token.json`, `credentials.json`, `settings.json`, `reference.jpg`, `__pycache__/`, and build output (`dist/`, `build/`).
- [ ] Confirm `electron/main.js`, `index.html`, `vite.config.js`, and `tailwind.config.js` are actually committed alongside `package.json` and `requirements.txt`.
- [ ] Consider trimming unused dependencies from `requirements.txt` (e.g. `PySide6` — see the note in [Backend setup](#2-backend-setup)).

## Note

This project is not complete yet and is actively being worked on. Only tested on Windows so far — if you get another OS working, a PR or a heads-up is welcome.

Found a bug or need help? `mahanbiabani12@gmail.com`

## Contributing

Contributions are welcome!

1. **Fork** the repository.
2. **Create a branch:**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Commit your changes:**
   ```bash
   git commit -m "Add amazing feature"
   ```
4. **Push to the branch:**
   ```bash
   git push origin feature/amazing-feature
   ```
5. **Open a Pull Request** with a clear description.

## Credits

This project began as a fork/extension of an earlier MIT-licensed assistant project by Nazir Louis. The original repository isn't linked here (link not currently available) — see [`LICENSE`](LICENSE) for the preserved original copyright notice.

## License

MIT — see [`LICENSE`](LICENSE). Note the license file carries two copyright lines: the original author's (required to be preserved under the MIT terms of the base project) and this fork's.