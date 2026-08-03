from plugins.base import tool, lazy_singleton
from .plugin import ChessAgent

get_agent = lazy_singleton(lambda sio=None: ChessAgent(sio=sio))

@tool(
    name="start_chess_game",
    description="Starts a new chess game against the user. User plays White, AI plays Black.",
    parameters={"type": "OBJECT", "properties": {}, "required": []},
)
async def start_chess_game(ctx, fc):
    ctx.emit("open_chess_window")
    return await get_agent(sio=ctx.sio).handle_function_call(fc)

@tool(
    name="play_chess_move",
    description="Makes a chess move for the AI. Must be in UCI format (e.g., 'e7e5', 'g8f6').",
    parameters={
        "type": "OBJECT",
        "properties": {
            "move": {"type": "STRING", "description": "The move in UCI format (e.g., 'e2e4')"}
        },
        "required": ["move"],
    },
)
async def play_chess_move(ctx, fc):
    print(f"[TOOL] ChessAgent call: '{fc.name}' args={fc.args}")
    result = await get_agent(sio=ctx.sio).handle_function_call(fc)
    
    # Tell the model what happened
    await ctx.notify_model(f"System: Chess move executed. {result}")
    
    # If AI move was successful, it's user's turn now. Wait for user UI input.
    if "successfully" in result:
        await ctx.notify_model("System: Waiting for Sir to make his move on the board...")
        
    return result