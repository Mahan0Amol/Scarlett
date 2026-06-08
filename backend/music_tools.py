search_music_tool = {
    "name": "search_music",
    "description": "Searches for music tracks based on specified query.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "The search query for finding music tracks like the song's name."}
        },
        "required": ["query"]
    }
}

play_music_tool = {
    "name": "play_music",
    "description": "Plays a specified music track.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "track_name": {"type": "STRING", "description": "The name of the track to play (You give this from the search_music results)."}
        },
        "required": ["track_name"]
    }
}

control_music_tool = {
    "name": "control_music",
    "description": "Controls music playback (pause, unpause, next, previous).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "The action to perform: 'unpause', 'pause', 'next', or 'previous'."}
        },
        "required": ["action"]
    }
}

music_tools_list = [{"function_declarations": [
    search_music_tool,
    play_music_tool,
    control_music_tool
]}]