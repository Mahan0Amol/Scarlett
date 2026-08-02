"""
Auto-discovers and imports every plugin in backend/plugins/ so their
@tool-decorated functions register themselves into the shared registry.

A plugin can be either:
    - plugins/<name>/__init__.py   (a folder per plugin - the standard shape)
    - plugins/<name>.py             (a flat module - also supported)

Adding a plugin = adding a folder (or file) here. Nothing else to wire up.
"""

import importlib
import pkgutil
from pathlib import Path

from .base import registry

_LOADED = False


def load_plugins(package_name: str = "plugins"):
    global _LOADED

    package = importlib.import_module(package_name)
    package_path = Path(package.__file__).parent

    for _, module_name, _is_pkg in pkgutil.iter_modules([str(package_path)]):
        if module_name in ("base", "loader", "__init__"):
            continue
        # Works for both plugins/<name>.py and plugins/<name>/__init__.py -
        # importing either one runs its @tool registrations.
        importlib.import_module(f"{package_name}.{module_name}")

    _LOADED = True
    return registry

