"""
Packages a plugin folder (backend/plugins/<id>/) into a single distributable
file: <id>-<version>.splugin. Under the hood this is just a zip archive -
the custom extension exists so double-clicking or drag-and-dropping the file
onto the app is unambiguous, not because the format itself is special.

Usage:
    python backend/plugin_tools/exporter.py chess
    python backend/plugin_tools/exporter.py chess --output /some/dir
"""

import argparse
import json
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIR = REPO_ROOT / "backend" / "plugins"

REQUIRED_MANIFEST_FIELDS = ("id", "name", "version")

# Never ship these even if present in the plugin folder.
EXCLUDED_NAMES = {"__pycache__", ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc"}


class PluginExportError(Exception):
    pass


def _load_manifest(plugin_dir: Path) -> dict:
    manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.exists():
        raise PluginExportError(f"No plugin.json found in {plugin_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    missing = [field for field in REQUIRED_MANIFEST_FIELDS if not manifest.get(field)]
    if missing:
        raise PluginExportError(f"plugin.json is missing required field(s): {', '.join(missing)}")

    return manifest


def _iter_files(plugin_dir: Path):
    for path in plugin_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_NAMES for part in path.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        yield path


def export_plugin(plugin_id: str, output_dir: Path = None) -> Path:
    """Zips backend/plugins/<plugin_id>/ into <id>-<version>.splugin.
    Returns the path to the created file."""
    plugin_dir = PLUGINS_DIR / plugin_id
    if not plugin_dir.is_dir():
        raise PluginExportError(f"No such plugin folder: {plugin_dir}")

    manifest = _load_manifest(plugin_dir)

    output_dir = Path(output_dir) if output_dir else REPO_ROOT
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{manifest['id']}-{manifest['version']}.splugin"

    files = list(_iter_files(plugin_dir))
    if not files:
        raise PluginExportError(f"Plugin folder {plugin_dir} is empty - nothing to export.")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            # Archive paths are relative to the plugin folder itself, e.g.
            # "__init__.py", "plugin.py", "frontend/ChessWindow.jsx" - so
            # the importer can extract straight into backend/plugins/<id>/.
            arcname = file_path.relative_to(plugin_dir)
            zf.write(file_path, arcname)

    print(f"[exporter] Exported '{plugin_id}' v{manifest['version']} -> {output_path} ({len(files)} files)")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export a Scarlett plugin to a .splugin file")
    parser.add_argument("plugin_id", help="Folder name under backend/plugins/, e.g. 'chess'")
    parser.add_argument("--output", "-o", default=None, help="Directory to write the .splugin file to")
    args = parser.parse_args()

    try:
        export_plugin(args.plugin_id, output_dir=args.output)
    except PluginExportError as e:
        print(f"[exporter] ERROR: {e}")
        raise SystemExit(1)
