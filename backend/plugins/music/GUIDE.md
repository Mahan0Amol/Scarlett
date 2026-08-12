# Music plugin

Tools: `search_music`, `play_music`, `control_music`.

- When a tool needs a filesystem path, use the full path, not a relative one.
- Prefer `play_music` directly when the exact track/path is already known; use `search_music` first only when it isn't.
- Don't make the user manually navigate folders when the needed info is already available from a previous search or memory.
- `control_music` handles playback control (pause/resume/skip/volume etc. - check its parameters for the exact action names).
