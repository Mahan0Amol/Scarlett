import asyncio
from plugins.base import tool


@tool(
    name="run_web_agent",
    description="Opens a web browser and performs a task according to the prompt.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The detailed instructions for the web browser agent."}
        },
        "required": ["prompt"],
    },
    behavior="NON_BLOCKING",
)
async def run_web_agent(ctx, fc):
    prompt = fc.args.get("prompt", "")
    print(f"[TOOL] run_web_agent prompt='{prompt}'")
    asyncio.create_task(ctx.handle_web_agent_request(prompt))
    return "Web Navigation started. Do not reply to this message."
