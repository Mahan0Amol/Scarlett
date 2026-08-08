import asyncio
import os
from plugins.base import tool


async def _write_file(ctx, path, content):
    print(f"[scarlett DEBUG] [FS] Writing file: '{path}'")
    await ctx.ensure_project("FS")

    filename = os.path.basename(path)
    current_project_path = ctx.project_manager.get_current_project_path()
    final_path = current_project_path / path if os.path.isabs(path) else current_project_path / filename

    try:
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(content)
        result = f"File '{final_path.name}' written successfully to project '{ctx.project_manager.current_project}'."
    except Exception as e:
        result = f"Failed to write file '{path}': {e}"

    print(f"[scarlett DEBUG] [FS] {result}")
    await ctx.notify_model(result)


async def _read_directory(ctx, path):
    print(f"[scarlett DEBUG] [FS] Reading directory: '{path}'")
    try:
        if not os.path.exists(path):
            result = f"Directory '{path}' does not exist."
        else:
            result = f"Contents of '{path}': {', '.join(os.listdir(path))}"
    except Exception as e:
        result = f"Failed to read directory '{path}': {e}"

    print(f"[scarlett DEBUG] [FS] {result}")
    await ctx.notify_model(result)


async def _read_file(ctx, path):
    print(f"[scarlett DEBUG] [FS] Reading file: '{path}'")
    try:
        if not os.path.exists(path):
            result = f"File '{path}' does not exist."
        else:
            with open(path, "r", encoding="utf-8") as f:
                result = f"Content of '{path}':\n{f.read()}"
    except Exception as e:
        result = f"Failed to read file '{path}': {e}"

    print(f"[scarlett DEBUG] [FS] {result}")
    await ctx.notify_model(result)


@tool(
    name="write_file",
    description="Writes content to a file at the specified path. Overwrites if exists.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "path": {"type": "STRING", "description": "The path of the file to write to."},
            "content": {"type": "STRING", "description": "The content to write to the file."},
        },
        "required": ["path", "content"],
    },
    requires_confirmation=True,
)
async def write_file(ctx, fc):
    asyncio.create_task(_write_file(ctx, fc.args["path"], fc.args["content"]))
    return "Writing file..."


@tool(
    name="read_directory",
    description="Lists the contents of a directory.",
    parameters={
        "type": "OBJECT",
        "properties": {"path": {"type": "STRING", "description": "The path of the directory to list."}},
        "required": ["path"],
    },
)
async def read_directory(ctx, fc):
    asyncio.create_task(_read_directory(ctx, fc.args["path"]))
    return "Reading directory..."


@tool(
    name="read_file",
    description="Reads the content of a file.",
    parameters={
        "type": "OBJECT",
        "properties": {"path": {"type": "STRING", "description": "The path of the file to read."}},
        "required": ["path"],
    },
)
async def read_file(ctx, fc):
    asyncio.create_task(_read_file(ctx, fc.args["path"]))
    return "Reading file..."
