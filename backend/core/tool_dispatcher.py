"""
Replaces the old ~500-line if/elif chain in Scarlett.py.

ToolDispatcher loads every plugin once, exposes the combined function
declarations for the Gemini `tools` config, and routes each incoming
FunctionCall to the right plugin handler — including the confirmation
flow, which used to be duplicated by hand inside every branch.
"""

import asyncio
import uuid
from typing import Optional

from google.genai import types

from plugins.loader import load_plugins


class ToolDispatcher:
    def __init__(self, ctx):
        """
        ctx: the AudioLoop instance. Plugin handlers receive it as their
        first argument so they can reach ctx.project_manager, ctx.session,
        ctx.sio, etc. without every agent needing to be re-plumbed here.
        """
        self.ctx = ctx
        self.registry = load_plugins()

    def function_declarations(self):
        return self.registry.function_declarations()

    async def dispatch(self, fc) -> Optional["types.FunctionResponse"]:
        spec = self.registry.get(fc.name)

        if spec is None:
            print(f"[TOOL] Unknown tool requested: '{fc.name}'")
            return types.FunctionResponse(
                id=fc.id, name=fc.name, response={"result": f"Unknown tool '{fc.name}'."}
            )

        # `ctx.permissions` (from settings.json / the Settings UI) is an
        # enable/disable gate - True (or unset) means the tool is allowed to
        # run at all, False means it's fully blocked. This is a separate
        # concept from `spec.requires_confirmation`, which is a per-tool
        # decision made by the plugin author about whether an *allowed* tool
        # should still pop up an "are you sure?" prompt before running (e.g.
        # for destructive actions). These two used to be the same flag,
        # which meant toggling a tool "off" in Settings actually made it
        # skip confirmation and run silently - the opposite of what the
        # toggle implied.
        enabled = self.ctx.permissions.get(fc.name, True)
        if not enabled:
            print(f"[TOOL] '{fc.name}' is disabled in settings.")
            return types.FunctionResponse(
                id=fc.id, name=fc.name,
                response={"result": f"The '{fc.name}' tool is currently disabled in settings."},
            )

        if spec.requires_confirmation:
            confirmed = await self._request_confirmation(fc.name, fc.args)
            if not confirmed:
                print(f"[TOOL] '{fc.name}' denied by user.")
                return types.FunctionResponse(
                    id=fc.id, name=fc.name, response={"result": "User denied the request to use this tool."}
                )

        try:
            result = await spec.handler(self.ctx, fc)
        except Exception as e:
            print(f"[TOOL] Error running '{fc.name}': {e}")
            result = f"Error running '{fc.name}': {e}"

        if result is None:
            # Handler either needs no reply (e.g. generate_cad) or is sending
            # its own FunctionResponse asynchronously later (e.g. run_cmd).
            return None

        return types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result})

    async def _request_confirmation(self, tool_name, args) -> bool:
        if not self.ctx.sio:
            # No frontend connected to ask - behave like the original code
            # did when no confirmation UI was wired up (proceed without asking).
            return True

        request_id = str(uuid.uuid4())
        future = asyncio.Future()
        self.ctx._pending_confirmations[request_id] = future

        print(f"[TOOL] Requesting confirmation for '{tool_name}' (ID: {request_id})")
        self.ctx.emit("tool_confirmation_request", {"id": request_id, "tool": tool_name, "args": args})

        try:
            confirmed = await future
        finally:
            self.ctx._pending_confirmations.pop(request_id, None)

        print(f"[TOOL] Confirmation {request_id} resolved: {confirmed}")
        return confirmed
