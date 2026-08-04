import chess
import asyncio

class ChessAgent:
    def __init__(self):
        self.ctx = None  # Set dynamically by @tool handlers
        self.sio = None  # Set dynamically by @ui_action handlers
        self.sid = None  # Set dynamically by @ui_action handlers
        self.board = chess.Board()
        self.game_active = False
        self.theme = {
            "dark": "#2c3e50",
            "light": "#ecf0f1",
            "glow": "none"
        }

    def reset_game(self):
        self.board.reset()
        self.game_active = True

    def get_state(self):
        return {
            "fen": self.board.fen(),
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_stalemate": self.board.is_stalemate(),
            "is_game_over": self.board.is_game_over(),
            "theme": self.theme # Include theme in state
        }

    async def emit_state(self):
        state = self.get_state()
        if self.sio and self.sid:
            await self.sio.emit("plugin_update", {"plugin": "chess", "data": state}, room=self.sid)
        elif self.ctx:
            self.ctx.emit("plugin_update", {"plugin": "chess", "data": state})

    def update_theme_colors(self, dark, light, glow="none"):
        """Updates the board colors based on AI input."""
        self.theme["dark"] = dark
        self.theme["light"] = light
        self.theme["glow"] = glow if glow and glow.lower() != "none" else "none"
        return True

    async def start_game(self, fc):
        self.reset_game()
        await self.emit_state()
        return "Chess game started! I am playing as Black, you are White. Make your move."

    async def play_move(self, fc):
        if not self.game_active:
            return "The game hasn't started. Call start_chess_game first."
            
        move_uci = fc.args.get("move")
        try:
            move = chess.Move.from_uci(move_uci)
            if move not in self.board.legal_moves:
                return f"Illegal move: {move_uci}. Try again."

            self.board.push(move)
            await self.emit_state()

            if self.board.is_game_over():
                self.game_active = False
                return "Game over."

            return {
                "status": "success",
                "fen": self.board.fen(),
                "legal_moves": [m.uci() for m in self.board.legal_moves],
                "turn": "black",
                "is_check": self.board.is_check(),
                "is_checkmate": self.board.is_checkmate(),
            }

        except Exception as e:
            return f"Invalid move format or error: {e}. Use UCI format like 'e2e4'."

    def apply_user_move(self, move_uci):
        """Called from UI when user drops a piece"""
        if not self.game_active:
            return "Game not active"
        try:
            move = chess.Move.from_uci(move_uci)
            if move not in self.board.legal_moves:
                return "Illegal move"
            
            self.board.push(move)
            return "Move applied successfully"
        except Exception:
            return "Invalid move format"

    async def handle_function_call(self, fc):
        func_map = {
            "start_chess_game": self.start_game,
            "play_chess_move": self.play_move,
        }
        func = func_map.get(fc.name)
        if not func:
            return None
        return await func(fc)