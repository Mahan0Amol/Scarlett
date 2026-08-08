import asyncio
from google.genai import types
from plugins.base import tool, lazy_singleton
from .plugin import CmdAgent

# Process-wide singleton, owned entirely by this plugin. If server.py's own
# terminal UI endpoints (autocomplete, current-dir display) need the same
# CmdAgent, they import get_agent from here.
get_agent = lazy_singleton(lambda: CmdAgent())


@tool(
    name="run_cmd",
    description=(
        "Executes a windows CMD command on the host machine and returns the output. Use this to "
        "run scripts, check files, install packages, query system info, or perform any terminal operation."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "command": {
                "type": "STRING",
                "description": "The shell command to execute (e.g. 'ls -la', 'python script.py', 'pip install numpy').",
            },
            "working_dir": {
                "type": "STRING",
                "description": "Optional working directory to run the command in. Defaults to the current project directory.",
            },
        },
        "required": ["command"],
    },
    requires_confirmation=True,
)
async def run_cmd(ctx, fc):
    command = fc.args["command"]
    print(f"[TOOL] run_cmd command='{command}'")

    # This tool sends its own function response asynchronously once the
    # command finishes, so the dispatcher gets `None` back immediately and
    # doesn't wait on it / doesn't send a second response.
    session_ref = ctx.session
    fc_id = fc.id
    fc_name = fc.name
    agent = get_agent()

    async def _run_and_respond():
        result_str = ""
        try:
            result = await agent.execute_command(command)

            if result.get("clear"):
                result_str = "Terminal cleared."
                ctx.emit("cmd_clear")
            elif "error" in result:
                result_str = f"Error: {result['error']}"
                ctx.emit("cmd_error", {"error": result["error"]})
            else:
                result_str = result.get("output", "(no output)")
                ctx.emit("cmd_output", {"output": result_str, "current_dir": result.get("current_dir"), "from_ai": True})
        except Exception as e:
            result_str = f"run_cmd failed: {e}"
            print(f"[TOOL] run_cmd error: {e}")

        if len(result_str) > 3000:
            result_str = result_str[:3000] + "\n... (output truncated)"

        try:
            await session_ref.send_tool_response(
                function_responses=[types.FunctionResponse(id=fc_id, name=fc_name, response={"result": result_str})]
            )
        except Exception as e:
            print(f"[TOOL] run_cmd tool response failed: {e}")

    asyncio.create_task(_run_and_respond())
    return None
