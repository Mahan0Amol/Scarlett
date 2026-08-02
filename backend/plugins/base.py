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
    requires_confirmation: bool = True       # default fallback if not overridden in settings.json


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        behavior: Optional[str] = None,
        requires_confirmation: bool = True,
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
