import requests
from plugins.base import tool, lazy_singleton
from .kasa import KasaAgent
from .smart import SmartAgent

# Process-wide singletons, owned entirely by this plugin. If server.py's own
# routes (e.g. device-management endpoints) need the same KasaAgent, they
# import get_kasa_agent from here - nothing has to be wired into AudioLoop.
get_kasa_agent = lazy_singleton(lambda known_devices=None: KasaAgent(known_devices=known_devices))
get_smart_agent = lazy_singleton(lambda: SmartAgent())


@tool(
    name="list_smart_devices",
    description="Lists all available smart home devices (lights, plugs, etc.) on the network.",
    parameters={"type": "OBJECT", "properties": {}},
)
async def list_smart_devices(ctx, fc):
    frontend_list = await get_smart_agent().discover_devices()

    dev_summaries = [f"{d['alias']} (IP: {d['ip']}, Type: {d['type']})" for d in frontend_list]
    result_str = "No devices found." if not dev_summaries else "Found Devices:\n" + "\n".join(dev_summaries)

    ctx.emit("kasa_devices", frontend_list)

    return result_str


@tool(
    name="move_robot",
    description="Control moving a robot based on raspberry pi.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "robot": {"type": "STRING", "description": "Target robot's IP Adress."},
            "direction": {
                "type": "STRING",
                "description": "The direction the robot should go: 'forward', 'backward', 'left', 'right', 'stop'.",
            },
            "duration": {
                "type": "STRING",
                "description": "The duration of moving (it is a number and for stop it should be 0).",
            },
        },
        "required": ["direction", "duration"],
    },
)
async def move_robot(ctx, fc):
    robot = fc.args["robot"]
    direction = fc.args["direction"]
    duration = fc.args["duration"]
    print(f"[TOOL] move_robot target='{robot}' direction='{direction}'")

    try:
        r = requests.post(f"http://{robot}:5000/move", json={"direction": direction, "duration": duration}, timeout=3)
        if r.status_code == 200:
            return f"Moved '{robot}' in direction '{direction}' for {duration} seconds."
        return f"direction '{direction}' on '{robot}' failed."
    except Exception as e:
        return f"direction '{direction}' on '{robot}' failed: {e}"


@tool(
    name="control_light",
    description="Controls a smart light device.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "The IP address of the device to control. Always prefer the IP address over the alias for reliability.",
            },
            "action": {"type": "STRING", "description": "The action to perform: 'turn_on', 'turn_off', or 'set'."},
            "brightness": {"type": "INTEGER", "description": "Optional brightness level (0-100)."},
            "color": {"type": "STRING", "description": "Optional color name (e.g., 'red', 'cool white') or 'warm'."},
        },
        "required": ["target", "action"],
    },
)
async def control_light(ctx, fc):
    target = fc.args["target"]
    action = fc.args["action"]
    brightness = fc.args.get("brightness")
    color = fc.args.get("color")
    print(f"[TOOL] control_light target='{target}' action='{action}'")

    result_msg = f"Action '{action}' on '{target}' failed."
    success = False

    try:
        if action == "turn_on":
            response = requests.post(f"http://{target}/relay/on", timeout=5)
            success = response.status_code == 200 and "success" in response.text
            if success:
                result_msg = f"Turned ON '{target}'."
        elif action == "turn_off":
            response = requests.post(f"http://{target}/relay/off", timeout=5)
            success = response.status_code == 200 and "success" in response.text
            if success:
                result_msg = f"Turned OFF '{target}'."
        elif action == "set":
            success = True
            result_msg = f"Updated '{target}':"
    except Exception as e:
        return f"Action '{action}' on '{target}' failed: {e}"

    if success or action == "set":
        if brightness is not None:
            if await get_kasa_agent().set_brightness(target, brightness):
                result_msg += f" Set brightness to {brightness}."
        if color is not None:
            if await get_kasa_agent().set_color(target, color):
                result_msg += f" Set color to {color}."

    return result_msg


@tool(
    name="control_door",
    description="Controls a smart door lock.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "The IP address of the door to control. Always prefer the IP address over the alias for reliability.",
            },
            "action": {"type": "STRING", "description": "The action to perform: 'open_door' or 'close_door'."},
        },
        "required": ["target", "action"],
    },
)
async def control_door(ctx, fc):
    target = fc.args["target"]
    action = fc.args["action"]
    print(f"[TOOL] control_door target='{target}' action='{action}'")

    result_msg = f"Action '{action}' on '{target}' failed."

    try:
        if action == "open_door":
            response = requests.post(f"http://{target}/relay/on", timeout=5)
            if response.status_code == 200 and "success" in response.text:
                result_msg = f"Opened '{target}'."
        elif action == "close_door":
            response = requests.post(f"http://{target}/relay/off", timeout=5)
            if response.status_code == 200 and "success" in response.text:
                result_msg = f"Closed '{target}'."
    except Exception as e:
        return f"Action '{action}' on '{target}' failed: {e}"

    return result_msg
