"""
Auto-discovers and imports every plugin in backend/plugins/ so their
@tool-decorated functions register themselves into the shared registry.

A plugin can be either:
    - plugins/<name>/__init__.py   (a folder per plugin - the standard shape)
    - plugins/<name>.py             (a flat module - also supported)

Adding a plugin = adding a folder (or file) here. Nothing else to wire up.

PLUGIN METADATA / GUIDES
-------------------------
Two optional files per plugin folder, both read from disk (never imported,
so they carry no code-execution risk and don't affect tool registration):

    plugin.json   - {"name": ..., "description": ...} (may have more keys,
                     only these two are used here). Powers the one-line
                     catalog entry for this plugin.
    GUIDE.md       - Free-form usage instructions for the model: exact
                     argument conventions, gotchas, examples, ordering
                     requirements between this plugin's tools, etc.

Neither the system prompt in Scarlett.py nor this loader hard-codes
anything about a specific plugin's usage. Instead:
    - get_plugin_catalog() builds a short "installed plugins" summary,
      sent once at session start, so the model always knows what exists.
    - a generic `read_plugin_guide` tool (registered below, only if at
      least one plugin ships a GUIDE.md) lets the model pull in a
      specific plugin's full guide on demand - lazily, only when it's
      about to use that plugin and isn't already sure how.

This means adding/removing a plugin, or expanding its instructions, never
touches Scarlett.py's system prompt again.
"""

import importlib
import json
import pkgutil
from pathlib import Path

from .base import registry

_LOADED = False


def _iter_plugin_modules(package_path: Path):
    for _, module_name, _is_pkg in pkgutil.iter_modules([str(package_path)]):
        if module_name in ("base", "loader", "__init__"):
            continue
        yield module_name


def load_plugins(package_name: str = "plugins"):
    global _LOADED

    package = importlib.import_module(package_name)
    package_path = Path(package.__file__).parent

    plugin_ids = []
    for module_name in _iter_plugin_modules(package_path):
        # Works for both plugins/<name>.py and plugins/<name>/__init__.py -
        # importing either one runs its @tool registrations. Safe to call
        # every time: Python caches imports, so re-importing an
        # already-loaded module is a no-op and won't re-run @tool(...) and
        # raise an "already registered" error.
        importlib.import_module(f"{package_name}.{module_name}")
        plugin_ids.append(module_name)

    if not _LOADED:
        _register_guide_tool(package_path, plugin_ids)
        _LOADED = True

    return registry


def _read_plugin_meta(plugin_dir: Path) -> dict:
    """Best-effort read of plugin.json. Missing/invalid file -> {}."""
    meta_path = plugin_dir / "plugin.json"
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[plugins] Failed to parse {meta_path}: {e}")
        return {}


def get_plugin_catalog(package_name: str = "plugins") -> str:
    """
    One line per installed plugin (id, display name, one-line description,
    and whether a full GUIDE.md is available). Meant to be sent to the
    model once at session start via notify_model - cheap enough to always
    include, unlike each plugin's full GUIDE.md.
    """
    package = importlib.import_module(package_name)
    package_path = Path(package.__file__).parent

    lines = []
    for module_name in sorted(_iter_plugin_modules(package_path)):
        plugin_dir = package_path / module_name
        meta = _read_plugin_meta(plugin_dir)
        display_name = meta.get("name", module_name)
        description = meta.get("description", "").strip()
        has_guide = (plugin_dir / "GUIDE.md").exists()

        line = f"- {module_name} ({display_name})"
        if description:
            line += f": {description}"
        if has_guide:
            line += f' — call read_plugin_guide("{module_name}") for full usage details'
        lines.append(line)

    return "\n".join(lines)


def _register_guide_tool(package_path: Path, plugin_ids):
    """
    Registers one generic tool, read_plugin_guide, that lazily returns a
    plugin's GUIDE.md on request. Only registered at all if at least one
    plugin actually ships a guide, and its enum only lists plugins that do
    - so the model can't call it with an id that has nothing to return.
    """
    guide_ids = sorted(
        pid for pid in plugin_ids if (package_path / pid / "GUIDE.md").exists()
    )
    if not guide_ids:
        return

    from .base import tool

    @tool(
        name="read_plugin_guide",
        description=(
            "Reads the full usage guide for one installed plugin: exact argument "
            "conventions, ordering requirements between its tools, gotchas, and examples. "
            "You're only given a one-line description of each plugin at session start - call "
            "this the first time in a session you're about to use a plugin's tools and aren't "
            "already confident how they work. No need to call it again for a plugin you've "
            "already read the guide for this session."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "plugin_id": {
                    "type": "STRING",
                    "description": "The plugin id to read the guide for (matches the id shown in the plugin catalog).",
                    "enum": guide_ids,
                }
            },
            "required": ["plugin_id"],
        },
    )
    async def read_plugin_guide(ctx, fc):
        plugin_id = fc.args["plugin_id"]
        guide_path = package_path / plugin_id / "GUIDE.md"
        if not guide_path.exists():
            return f"No GUIDE.md found for plugin '{plugin_id}'."
        return guide_path.read_text(encoding="utf-8")
