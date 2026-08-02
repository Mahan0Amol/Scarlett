import pyautogui
from plugins.base import tool


@tool(
    name="press_key_on_keyboard",
    description="Presses a key on the keyboard usually for shortcuts.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "key": {"type": "STRING", "description": "The name of the keys to press: key1:key2:key3:......"}
        },
        "required": ["key"],
    },
)
async def press_key_on_keyboard(ctx, fc):
    keys = fc.args["key"].split(":")
    print(f"[TOOL] press_key_on_keyboard key='{keys}'")
    try:
        pyautogui.hotkey(*keys)
        return f"Pressed keys: {keys} successfully."
    except Exception as e:
        return f"Failed to press key '{keys}': {e}"


@tool(
    name="write_with_keyboard",
    description="Writes text using the keyboard.",
    parameters={
        "type": "OBJECT",
        "properties": {"text": {"type": "STRING", "description": "The text to write."}},
        "required": ["text"],
    },
)
async def write_with_keyboard(ctx, fc):
    text = fc.args["text"]
    print(f"[TOOL] write_with_keyboard text='{text}'")
    try:
        pyautogui.write(text)
        return f"Typed text: '{text}'"
    except Exception as e:
        return f"Failed to type text '{text}': {e}"
