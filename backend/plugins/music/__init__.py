from plugins.base import tool


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
    return await ctx.music_agent.handle_function_call(fc)


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
    if ctx.sio and ctx.client_sid:
        await ctx.sio.emit("open_music_window", room=ctx.client_sid)
    return await ctx.music_agent.handle_function_call(fc)


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
    return await ctx.music_agent.handle_function_call(fc)
