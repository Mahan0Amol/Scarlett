import asyncio
from plugins.base import tool


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
)
async def write_file(ctx, fc):
    path = fc.args["path"]
    content = fc.args["content"]
    print(f"[TOOL] write_file path='{path}'")
    asyncio.create_task(ctx.handle_write_file(path, content))
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
    path = fc.args["path"]
    print(f"[TOOL] read_directory path='{path}'")
    asyncio.create_task(ctx.handle_read_directory(path))
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
    path = fc.args["path"]
    print(f"[TOOL] read_file path='{path}'")
    asyncio.create_task(ctx.handle_read_file(path))
    return "Reading file..."
