# Smarthome plugin

Tools: `list_smart_devices`, `control_light`, `control_door`, `move_robot`.

## Lights
- Call `list_smart_devices` first if the target device's IP isn't already known.
- Always prefer the device's IP address over its alias/name for `control_light`/`control_door` - aliases are for talking to the user, IPs are for calling the tool.
- `control_light` actions: `turn_on`, `turn_off`, `set` (with optional `brightness` 0-100 and/or `color`).

## Doors
- `control_door` actions: `open_door`, `close_door`. This tool requires user confirmation before it runs - that's expected, not an error.

## Robot
- `move_robot` controls a network robot (Raspberry-Pi based) by IP.
- Valid directions: `forward`, `backward`, `left`, `right`, `stop`.
- Never invent a robot IP - ask the user if it isn't already known.
