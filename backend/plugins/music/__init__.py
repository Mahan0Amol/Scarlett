import os
from pathlib import Path
from plugins.base import tool, lazy_singleton, ui_action
from .plugin import MusicAgent

get_agent = lazy_singleton(
    lambda sio=None: MusicAgent(os.getenv("MUSIC_FOLDER") or str(Path.home() / "Music"), sio)
)


@ui_action("open_music_window")
async def ui_open_music_window(sio, sid, data):
    print(f"[SERVER] AI requested to open music window: {data}")
    await sio.emit("open_music_window", room=sid)


@ui_action("music_play")
async def ui_music_play(sio, sid, data):
    agent = get_agent(sio=sio)
    agent.unpause()

    await sio.emit(
        "music_state",
        {**agent.current_metadata, "isPlaying": True},
        room=sid
    )


@ui_action("music_state_request")
async def ui_music_state_request(sio, sid, data):
    agent = get_agent(sio=sio)

    await sio.emit(
        "music_state",
        agent.get_current_state(),
        room=sid
    )


@ui_action("music_pause")
async def ui_music_pause(sio, sid, data):
    agent = get_agent(sio=sio)
    agent.pause()

    await sio.emit(
        "music_state",
        {**agent.current_metadata, "isPlaying": False},
        room=sid
    )


@ui_action("music_next")
async def ui_music_next(sio, sid, data):
    agent = get_agent(sio=sio)

    agent.current_metadata = agent.next_track()

    if agent.current_metadata:
        await sio.emit(
            "music_state",
            agent.get_current_state(),
            room=sid
        )


@ui_action("music_prev")
async def ui_music_prev(sio, sid, data):
    agent = get_agent(sio=sio)

    agent.current_metadata = agent.prev_track()

    if agent.current_metadata:
        await sio.emit(
            "music_state",
            agent.get_current_state(),
            room=sid
        )


@ui_action("music_seek")
async def ui_music_seek(sio, sid, data):
    agent = get_agent(sio=sio)

    if data and "position" in data:
        agent.seek(int(data["position"]))

        await sio.emit(
            "music_state",
            agent.get_current_state(),
            room=sid
        )


@ui_action("music_volume")
async def ui_music_volume(sio, sid, data):
    agent = get_agent(sio=sio)

    if data and "volume" in data:
        agent.set_volume(int(data["volume"]))

        await sio.emit(
            "music_state",
            agent.get_current_state(),
            room=sid
        )


@ui_action("music_stop")
async def ui_music_stop(sio, sid, data):
    agent = get_agent(sio=sio)

    agent.stop()

    await sio.emit(
        "music_state",
        {
            "title": "No Track Selected",
            "artist": "Unknown Artist",
            "duration": 0,
            "thumb": None,
            "position": 0,
            "isPlaying": False,
            "volume": agent.player.audio_get_volume()
        },
        room=sid
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
