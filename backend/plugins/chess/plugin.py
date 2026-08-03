import chess
import asyncio

class ChessAgent:
    _instance = None

    def __new__(cls, sio=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, sio=None):
        if self._initialized:
            return
        self._initialized = True
        self.sio = sio
        self.board = chess.Board()
        self.game_active = False

    def reset_game(self):
        self.board.reset()
        self.game_active = True

    async def emit_state(self):
        if self.sio:
            await self.sio.emit("chess_state", {
                "fen": self.board.fen(),
                "turn": "white" if self.board.turn == chess.WHITE else "black",
                "is_check": self.board.is_check(),
                "is_checkmate": self.board.is_checkmate(),
                "is_stalemate": self.board.is_stalemate(),
                "is_game_over": self.board.is_game_over()
            })

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

    async def handle_function_call(self, fc):
        func_map = {
            "start_chess_game": self.start_game,
            "play_chess_move": self.play_move,
        }
        func = func_map.get(fc.name)
        if not func:
            return None
        return await func(fc)