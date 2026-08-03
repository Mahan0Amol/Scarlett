import asyncio
from plugins.base import tool
from .plugin import WebAgent


def _get_agent(ctx):
    if "web_agent" not in ctx.state:
        ctx.state["web_agent"] = WebAgent()
    return ctx.state["web_agent"]


async def _run_web_task(ctx, prompt):
    print(f"[scarlett DEBUG] [WEB] Task started: '{prompt}'")

    async def update_frontend(image_b64, log_text):
        ctx.emit("browser_frame", {"image": image_b64, "log": log_text})

    result = await _get_agent(ctx).run_task(prompt, update_callback=update_frontend)
    print(f"[scarlett DEBUG] [WEB] Task finished: {result}")
    await ctx.notify_model(f"Web Agent has finished.\nResult: {result}")


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
    asyncio.create_task(_run_web_task(ctx, prompt))
    return "Web Navigation started. Do not reply to this message."
