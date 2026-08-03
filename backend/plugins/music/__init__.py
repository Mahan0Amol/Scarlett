import os
from pathlib import Path
from plugins.base import tool, lazy_singleton
from .plugin import MusicAgent

# Process-wide singleton, owned entirely by this plugin. Folder comes from
# MUSIC_FOLDER in .env, falling back to ~/Music. If server.py's own routes
# (transport-control buttons in the UI) need the same MusicAgent, they
# import get_agent from here - nothing has to be wired into AudioLoop.
get_agent = lazy_singleton(
    lambda sio=None: MusicAgent(os.getenv("MUSIC_FOLDER") or str(Path.home() / "Music"), sio)
)


@tool(
    name="search_music",
    description="Searches for music tracks based on specified query.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "The search query for finding music tracks like the song's name."}
        },
        "required": ["query"],
    },
)
async def search_music(ctx, fc):
    print(f"[TOOL] MusicAgent call: '{fc.name}' args={fc.args}")
    return await get_agent(sio=ctx.sio).handle_function_call(fc)


@tool(
    name="play_music",
    description="Plays a specified music track.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "track_name": {
                "type": "STRING",
                "description": "The name of the track to play (You give this from the search_music results).",
            }
        },
        "required": ["track_name"],
    },
)
async def play_music(ctx, fc):
    print(f"[TOOL] MusicAgent call: '{fc.name}' args={fc.args}")
    ctx.emit("open_music_window")
    return await get_agent(sio=ctx.sio).handle_function_call(fc)


@tool(
    name="control_music",
    description="Controls music playback (pause, unpause, next, previous).",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "The action to perform: 'unpause', 'pause', 'next', or 'previous'."}
        },
        "required": ["action"],
    },
)
async def control_music(ctx, fc):
    print(f"[TOOL] MusicAgent call: '{fc.name}' args={fc.args}")
    return await get_agent(sio=ctx.sio).handle_function_call(fc)
