from plugins.base import tool, lazy_singleton, ui_action
from .plugin import ChessAgent

# DO NOT pass sio into the singleton constructor to avoid caching old sockets
get_agent = lazy_singleton(lambda: ChessAgent())

# ================= UI Actions (Frontend Buttons) =================

@ui_action("chess_user_move")
async def ui_chess_user_move(sio, sid, data):
    agent = get_agent()
    # Dynamically inject current socket info for UI actions
    agent.sio = sio
    agent.sid = sid
    
    move_uci = data.get("move")
    result = agent.apply_user_move(move_uci)
    
    # Emit the new state back to the specific client
    await sio.emit("plugin_update", {
        "plugin": "chess",
        "data": agent.get_state()
    }, room=sid)
    if agent.ctx and "successfully" in str(result):
        await agent.ctx.notify_model(
            f"System: Sir played {move_uci}. It is your turn now. Use the play_chess_move tool to make your move."
        )

@ui_action("chess_state_request")
async def ui_chess_state_request(sio, sid, data):
    agent = get_agent()
    await sio.emit("plugin_update", {
        "plugin": "chess",
        "data": agent.get_state()
    }, room=sid)

@tool(
    name="start_chess_game",
    description="Starts a new chess game against the user. User plays White, AI plays Black.",
    parameters={"type": "OBJECT", "properties": {}, "required": []},
)
async def start_chess_game(ctx, fc):
    # Use the new generic UI opener event
    ctx.emit("open_plugin", {"plugin": "chess"})
    
    agent = get_agent()
    # Dynamically inject the current context so the agent can emit to the correct client
    agent.ctx = ctx 
    
    return await agent.handle_function_call(fc)

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
    
    agent = get_agent()
    agent.ctx = ctx
    
    result = await agent.handle_function_call(fc)
    
    # Tell the model what happened
    await ctx.notify_model(f"System: Chess move executed. {result}")
    
    # If AI move was successful, it's user's turn now. Wait for user UI input.
    if "successfully" in str(result):
        await ctx.notify_model("System: Waiting for Sir to make his move on the board...")
        
    return result
