"""
Installs a .splugin package into this project.

Two-step API, deliberately:

    info = inspect_plugin("chess-1.0.0.splugin")
    # -> show info["manifest"], info["python_dependencies"],
    #    info["npm_dependencies"], info["permissions"] to the user
    install_plugin("chess-1.0.0.splugin", confirmed=True)

install_plugin() refuses to run unless confirmed=True, on purpose - a
plugin's dependency list can run arbitrary code at install time (that's how
pip/npm packages work), so nothing should install silently without a human
having seen what's about to happen.

Usage from the command line:
    python backend/plugin_tools/importer.py chess-1.0.0.splugin
    python backend/plugin_tools/importer.py chess-1.0.0.splugin --overwrite --no-deps
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
import platform

try:
    from .registry_sync import add_plugin_entry, remove_plugin_entry, regenerate_registry
except ImportError:
    # Running as a standalone script (python backend/plugin_tools/importer.py)
    # rather than as part of a package - fall back to a path-based import.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from registry_sync import add_plugin_entry, remove_plugin_entry, regenerate_registry

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIR = REPO_ROOT / "backend" / "plugins"
COMPONENTS_DIR = REPO_ROOT / "src" / "components"

REQUIRED_MANIFEST_FIELDS = ("id", "name", "version")


class PluginImportError(Exception):
    pass


# --------------------------------------------------------------------------
# Extraction / validation
# --------------------------------------------------------------------------

def _extract_to_temp(splugin_path: Path) -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="splugin_"))
    try:
        with zipfile.ZipFile(splugin_path, "r") as zf:
            zf.extractall(tmp_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise PluginImportError(f"'{splugin_path}' is not a valid .splugin file (corrupt, or not a zip).")
    return tmp_dir


def _load_manifest(extracted_dir: Path) -> dict:
    manifest_path = extracted_dir / "plugin.json"
    if not manifest_path.exists():
        raise PluginImportError("Plugin package is missing plugin.json - cannot install.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        try:
            manifest = json.load(f)
        except json.JSONDecodeError as e:
            raise PluginImportError(f"plugin.json is not valid JSON: {e}")

    missing = [field for field in REQUIRED_MANIFEST_FIELDS if not manifest.get(field)]
    if missing:
        raise PluginImportError(f"plugin.json is missing required field(s): {', '.join(missing)}")

    for entry in manifest.get("frontend", []):
        if not entry.get("ui_id") or not entry.get("component") or not entry.get("file"):
            raise PluginImportError(
                "Each entry in plugin.json's 'frontend' list needs 'ui_id', 'component', and 'file'."
            )

    return manifest


# --------------------------------------------------------------------------
# Step 1: inspect (read-only, safe to call anytime)
# --------------------------------------------------------------------------

def inspect_plugin(splugin_path) -> dict:
    """Extracts and validates a .splugin WITHOUT installing anything.
    Returns everything a confirmation UI needs to show the user."""
    splugin_path = Path(splugin_path)
    if not splugin_path.exists():
        raise PluginImportError(f"File not found: {splugin_path}")

    tmp_dir = _extract_to_temp(splugin_path)
    try:
        manifest = _load_manifest(tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "manifest": manifest,
        "already_installed": (PLUGINS_DIR / manifest["id"]).exists(),
        "python_dependencies": manifest.get("python_dependencies", []),
        "npm_dependencies": manifest.get("npm_dependencies", {}),
        "permissions": manifest.get("permissions", []),
    }


# --------------------------------------------------------------------------
# Step 2: install (requires explicit confirmation)
# --------------------------------------------------------------------------

def _copy_backend_files(tmp_dir: Path, dest_dir: Path):
    for item in tmp_dir.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(tmp_dir)
        if rel.parts[0] == "frontend":
            continue  # frontend files are handled separately
        target = dest_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def _copy_frontend_files_and_register(tmp_dir: Path, dest_dir: Path, manifest: dict):
    frontend_entries = manifest.get("frontend", [])
    if not frontend_entries:
        return

    COMPONENTS_DIR.mkdir(parents=True, exist_ok=True)
    dest_frontend_dir = dest_dir / "frontend"
    dest_frontend_dir.mkdir(parents=True, exist_ok=True)

    for entry in frontend_entries:
        src = tmp_dir / "frontend" / entry["file"]
        if not src.exists():
            raise PluginImportError(
                f"plugin.json lists frontend file '{entry['file']}' but it isn't inside the package."
            )
        # Two copies, on purpose:
        #  1. src/components/ - where Vite actually serves the running app from.
        #  2. backend/plugins/<id>/frontend/ - keeps the plugin folder itself
        #     self-contained, so it can be re-exported later without going
        #     stale (exporter zips *this* folder, not src/components/).
        shutil.copy2(src, COMPONENTS_DIR / entry["file"])
        shutil.copy2(src, dest_frontend_dir / entry["file"])
        add_plugin_entry(entry["ui_id"], entry["component"], entry["file"])

    regenerate_registry()


def _install_python_dependencies(deps: list[str]) -> bool:
    if not deps:
        return True
    print(f"[importer] Installing Python dependencies: {', '.join(deps)}")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--break-system-packages", *deps],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[importer] pip install FAILED:\n{result.stderr}")
        return False
    return True


def _install_npm_dependencies(deps: dict) -> bool:
    if not deps:
        return True
    packages = [f"{name}@{version}" for name, version in deps.items()]
    print(f"[importer] Installing npm dependencies: {', '.join(packages)}")

    npm_path = shutil.which("npm.cmd") if platform.system() == "Windows" else shutil.which("npm")
    if not npm_path:
        npm_path = shutil.which("npm")  # fallback, just in case
    if not npm_path:
        print("[importer] npm install FAILED: 'npm' was not found on PATH. Is Node.js installed?")
        return False

    result = subprocess.run([npm_path, "install", *packages], cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[importer] npm install FAILED:\n{result.stderr}")
        return False
    return True

def _rollback(plugin_id: str, manifest: dict):
    """Best-effort cleanup if installation fails partway through, so a
    failed install doesn't leave the app in a broken half-installed state."""
    print(f"[importer] Rolling back partial install of '{plugin_id}'...")
    shutil.rmtree(PLUGINS_DIR / plugin_id, ignore_errors=True)
    for entry in manifest.get("frontend", []):
        (COMPONENTS_DIR / entry["file"]).unlink(missing_ok=True)
        remove_plugin_entry(entry["ui_id"])
    regenerate_registry()


def install_plugin(splugin_path, confirmed: bool = False, overwrite: bool = False, install_deps: bool = True) -> dict:
    if not confirmed:
        raise PluginImportError(
            "install_plugin() requires confirmed=True. Call inspect_plugin() first, show the user "
            "the dependencies and permissions it lists, and only proceed once they explicitly agree - "
            "installing dependencies means running code you haven't reviewed."
        )

    splugin_path = Path(splugin_path)
    tmp_dir = _extract_to_temp(splugin_path)

    try:
        manifest = _load_manifest(tmp_dir)
        plugin_id = manifest["id"]
        dest_dir = PLUGINS_DIR / plugin_id

        if dest_dir.exists() and not overwrite:
            raise PluginImportError(
                f"Plugin '{plugin_id}' is already installed. Pass overwrite=True to upgrade/reinstall."
            )

        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True)

        try:
            _copy_backend_files(tmp_dir, dest_dir)
            _copy_frontend_files_and_register(tmp_dir, dest_dir, manifest)

            deps_ok = True
            if install_deps:
                deps_ok = _install_python_dependencies(manifest.get("python_dependencies", []))
                deps_ok = _install_npm_dependencies(manifest.get("npm_dependencies", {})) and deps_ok

            if not deps_ok:
                _rollback(plugin_id, manifest)
                raise PluginImportError(
                    f"Dependency installation failed for '{plugin_id}' - install rolled back. See log above."
                )

        except Exception:
            _rollback(plugin_id, manifest)
            raise

        print(
            f"[importer] Installed '{manifest['name']}' v{manifest['version']} ({plugin_id}).\n"
            f"[importer] Restart the backend (python backend/server.py) to load its tools.\n"
            f"[importer] Refresh the frontend if it doesn't pick up the new window automatically."
        )
        return {"plugin_id": plugin_id, "manifest": manifest}

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def uninstall_plugin(plugin_id: str, remove_dependencies: bool = False) -> dict:
    """Completely removes a plugin as if it never existed:
    - backend/plugins/<id>/ folder (python code + its own frontend/ copy)
    - src/components/<file> for every frontend entry it registered
    - its entry in src/plugins.manifest.json (+ regenerates pluginRegistry.jsx)
    - optionally, its pip/npm dependencies (off by default - they may be
      shared with other plugins or the app itself, so this is opt-in and
      best-effort only)

    Only works on plugins that ship a plugin.json (i.e. ones installed via
    the Plugin Manager / listed by /api/plugins/list). Built-in, manifest-
    less plugins under backend/plugins/ are never touched by this path.
    """
    dest_dir = PLUGINS_DIR / plugin_id
    manifest_path = dest_dir / "plugin.json"

    if not dest_dir.is_dir() or not manifest_path.exists():
        raise PluginImportError(f"'{plugin_id}' is not an installed manifest-based plugin.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    removed_deps = {"python": [], "npm": [], "failed": []}

    # 1) Frontend: delete the compiled component + drop its manifest entry
    for entry in manifest.get("frontend", []):
        (COMPONENTS_DIR / entry["file"]).unlink(missing_ok=True)
        remove_plugin_entry(entry["ui_id"])
    regenerate_registry()

    # 2) Optional: best-effort dependency removal
    if remove_dependencies:
        py_deps = manifest.get("python_dependencies", [])
        if py_deps:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", *py_deps],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                removed_deps["python"] = py_deps
            else:
                removed_deps["failed"].append({"type": "python", "error": result.stderr})

        npm_deps = manifest.get("npm_dependencies", {})
        if npm_deps:
            npm_path = shutil.which("npm.cmd") if platform.system() == "Windows" else shutil.which("npm")
            if npm_path:
                result = subprocess.run(
                    [npm_path, "uninstall", *npm_deps.keys()],
                    cwd=REPO_ROOT, capture_output=True, text=True,
                )
                if result.returncode == 0:
                    removed_deps["npm"] = list(npm_deps.keys())
                else:
                    removed_deps["failed"].append({"type": "npm", "error": result.stderr})

    # 3) Backend: delete the plugin folder itself (code + its self-contained
    # frontend/ copy) - do this LAST so a failure above still leaves the
    # plugin.json around for a retry.
    shutil.rmtree(dest_dir)

    print(f"[importer] Uninstalled '{manifest['name']}' ({plugin_id}). Restart the backend to unload its tools.")
    return {"plugin_id": plugin_id, "manifest": manifest, "removed_dependencies": removed_deps}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install a Scarlett .splugin package")
    parser.add_argument("splugin_path", help="Path to the .splugin file")
    parser.add_argument("--overwrite", action="store_true", help="Reinstall even if already installed")
    parser.add_argument("--no-deps", action="store_true", help="Skip pip/npm dependency installation")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip the confirmation prompt (non-interactive)")
    args = parser.parse_args()

    try:
        info = inspect_plugin(args.splugin_path)
    except PluginImportError as e:
        print(f"[importer] ERROR: {e}")
        raise SystemExit(1)

    m = info["manifest"]
    print(f"\nAbout to install: {m['name']} v{m['version']} ({m['id']})")
    print(f"  Description: {m.get('description', '(none)')}")
    print(f"  Already installed: {info['already_installed']}")
    print(f"  Python dependencies: {info['python_dependencies'] or '(none)'}")
    print(f"  npm dependencies: {info['npm_dependencies'] or '(none)'}")
    print(f"  Permissions requested: {info['permissions'] or '(none)'}\n")

    if not args.yes:
        answer = input("Proceed with installation? [y/N] ").strip().lower()
        if answer != "y":
            print("[importer] Cancelled.")
            raise SystemExit(0)

    try:
        install_plugin(
            args.splugin_path,
            confirmed=True,
            overwrite=args.overwrite,
            install_deps=not args.no_deps,
        )
    except PluginImportError as e:
        print(f"[importer] ERROR: {e}")
        raise SystemExit(1)
