# Chess plugin

Tools: `start_chess_game`, `play_chess_move`, `set_chess_theme`.

- Call `start_chess_game` when a new game needs to be opened.
- You play as Black unless the tool/game state says otherwise.
- Moves must be in UCI format, e.g. `e7e5`, `g8f6`.
- Never assume the board position if the current game state is available from a tool - check it before choosing a move.
