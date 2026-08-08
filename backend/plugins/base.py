"""
Plugin core: a tiny registry that lets a plugin module declare a tool's
Gemini schema *and* its handler in one place, using a decorator.

To add a new tool:
    1. Create (or open) a file in backend/plugins/, e.g. plugins/lights_plugin.py
    2. Decorate an async function with @tool(...)
    3. Done. No other file needs to change — loader.py auto-discovers it,
       Scarlett.py auto-includes its schema in the Gemini `tools` list, and
       the dispatcher auto-routes calls to it.

Handler signature:
    async def handler(ctx, fc) -> Optional[str]

    - ctx: the running AudioLoop instance (self). Gives access to
      ctx.project_manager, ctx.kasa_agent, ctx.session, ctx.sio, etc.
    - fc:  the raw Gemini FunctionCall (fc.id, fc.name, fc.args).
    - Return a string  -> sent back to the model as the tool's result.
    - Return None       -> no function response is sent (e.g. because the
      handler already sent one itself, like run_cmd does asynchronously, or
      because none is needed, like generate_cad which just kicks off a
      background task the frontend will show progress for).
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable
    behavior: Optional[str] = None          # e.g. "NON_BLOCKING", passed straight to Gemini
    requires_confirmation: bool = False      # opt-in per tool; set True for destructive/sensitive actions


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        behavior: Optional[str] = None,
        requires_confirmation: bool = False,
    ):
        def decorator(func: Callable):
            if name in self._tools:
                raise ValueError(
                    f"Tool '{name}' is already registered "
                    f"(in {self._tools[name].handler.__module__})."
                )
            self._tools[name] = ToolSpec(
                name=name,
                description=description,
                parameters=parameters,
                handler=func,
                behavior=behavior,
                requires_confirmation=requires_confirmation,
            )
            return func
        return decorator

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def all(self):
        return list(self._tools.values())

    def function_declarations(self):
        """Builds the list of function declarations Gemini expects."""
        decls = []
        for t in self._tools.values():
            decl = {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            if t.behavior:
                decl["behavior"] = t.behavior
            decls.append(decl)
        return decls


# Single shared registry for the whole app.
registry = ToolRegistry()

# Convenience alias so plugin files can just do: from plugins.base import tool
tool = registry.register



class UIActionRegistry:
    def __init__(self):
        self._actions = {}

    def register(self, event_name: str):
        def decorator(func):
            if event_name in self._actions:
                raise ValueError(f"UI Action '{event_name}' is already registered.")
            self._actions[event_name] = func
            return func
        return decorator

    def all(self):
        return self._actions

# ساخت یک نمونه عمومی و alias برای استفاده آسان در پلاگین‌ها
ui_registry = UIActionRegistry()
ui_action = ui_registry.register


def lazy_singleton(builder):
    """Wraps a builder function into a cached accessor - the plugin's one
    canonical, process-wide instance (e.g. its agent). Any code anywhere -
    a tool handler in this plugin, or server.py's own routes if they need
    the same instance for a non-AI UI feature - just imports and calls the
    returned accessor. Nothing needs to be wired in from outside; the
    plugin folder is the single source of truth for its own resources.

    Example (inside a plugin's __init__.py):
        get_agent = lazy_singleton(lambda: SomeAgent())

        @tool(...)
        async def some_tool(ctx, fc):
            return await get_agent().do_thing()

    And, only if some *other* part of the app also needs that same agent:
        from plugins.some_plugin import get_agent
        agent = get_agent()
    """
    _cache = {}

    def get(*args, **kwargs):
        if "instance" not in _cache:
            _cache["instance"] = builder(*args, **kwargs)
        return _cache["instance"]

    return get

