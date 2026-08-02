from plugins.base import tool


@tool(
    name="discover_printers",
    description="Discovers 3D printers available on the local network.",
    parameters={"type": "OBJECT", "properties": {}},
)
async def discover_printers(ctx, fc):
    printers = await ctx.printer_agent.discover_printers()
    if printers:
        printer_list = [f"{p['name']} ({p['host']}:{p['port']}, type: {p['printer_type']})" for p in printers]
        return "Found Printers:\n" + "\n".join(printer_list)
    return "No printers found on network. Ensure printers are on and running OctoPrint/Moonraker."


@tool(
    name="print_stl",
    description="Prints an STL file to a 3D printer. Handles slicing the STL to G-code and uploading to the printer.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "stl_path": {"type": "STRING", "description": "Path to STL file, or 'current' for the most recent CAD model."},
            "printer": {"type": "STRING", "description": "Printer name or IP address."},
            "profile": {"type": "STRING", "description": "Optional slicer profile name."},
        },
        "required": ["stl_path", "printer"],
    },
)
async def print_stl(ctx, fc):
    stl_path = fc.args["stl_path"]
    printer = fc.args["printer"]
    profile = fc.args.get("profile")

    if stl_path.lower() == "current":
        stl_path = "output.stl"

    project_path = str(ctx.project_manager.get_current_project_path())
    result = await ctx.printer_agent.print_stl(stl_path, printer, profile, root_path=project_path)
    return result.get("message", "Unknown result")


@tool(
    name="get_print_status",
    description="Gets the current status of a 3D printer including progress, time remaining, and temperatures.",
    parameters={
        "type": "OBJECT",
        "properties": {"printer": {"type": "STRING", "description": "Printer name or IP address."}},
        "required": ["printer"],
    },
)
async def get_print_status(ctx, fc):
    printer = fc.args["printer"]
    status = await ctx.printer_agent.get_print_status(printer)

    if not status:
        return f"Could not get status for printer '{printer}'. Ensure it is discovered first."

    lines = [
        f"Printer: {status.printer}",
        f"State: {status.state}",
        f"Progress: {status.progress_percent:.1f}%",
    ]
    if status.time_remaining:
        lines.append(f"Time Remaining: {status.time_remaining}")
    if status.time_elapsed:
        lines.append(f"Time Elapsed: {status.time_elapsed}")
    if status.filename:
        lines.append(f"File: {status.filename}")
    if status.temperatures:
        temps = status.temperatures
        if "hotend" in temps:
            lines.append(f"Hotend: {temps['hotend']['current']:.0f}°C / {temps['hotend']['target']:.0f}°C")
        if "bed" in temps:
            lines.append(f"Bed: {temps['bed']['current']:.0f}°C / {temps['bed']['target']:.0f}°C")

    return "\n".join(lines)
