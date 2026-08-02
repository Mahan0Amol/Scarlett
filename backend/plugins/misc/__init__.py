import asyncio
from plugins.base import tool


@tool(
    name="wait_and_delay",
    description="Waits for a specified duration or delays execution.",
    parameters={
        "type": "OBJECT",
        "properties": {"duration": {"type": "NUMBER", "description": "The duration in milliseconds to wait."}},
        "required": ["duration"],
    },
)
async def wait_and_delay(ctx, fc):
    duration = fc.args["duration"] / 1000
    print(f"[TOOL] wait_and_delay duration={duration}s")
    # NOTE: was `time.sleep()` in the original code, which blocks the whole
    # event loop (freezes audio/video/every other tool for the duration).
    # Swapped to asyncio.sleep so it only suspends this task.
    await asyncio.sleep(duration)
    return f"Waited for {duration} seconds"
