from plugins.base import tool


@tool(
    name="create_project",
    description="Creates a new project folder to organize files.",
    parameters={
        "type": "OBJECT",
        "properties": {"name": {"type": "STRING", "description": "The name of the new project."}},
        "required": ["name"],
    },
)
async def create_project(ctx, fc):
    name = fc.args["name"]
    print(f"[TOOL] create_project name='{name}'")
    success, msg = ctx.project_manager.create_project(name)
    if success:
        ctx.project_manager.switch_project(name)
        msg += f" Switched to '{name}'."
        if ctx.on_project_update:
            ctx.on_project_update(name)
    return msg


@tool(
    name="switch_project",
    description="Switches the current active project context.",
    parameters={
        "type": "OBJECT",
        "properties": {"name": {"type": "STRING", "description": "The name of the project to switch to."}},
        "required": ["name"],
    },
)
async def switch_project(ctx, fc):
    name = fc.args["name"]
    print(f"[TOOL] switch_project name='{name}'")
    success, msg = ctx.project_manager.switch_project(name)
    if success:
        if ctx.on_project_update:
            ctx.on_project_update(name)
        context = ctx.project_manager.get_project_context()
        try:
            await ctx.session.send(input=f"System Notification: {msg}\n\n{context}", end_of_turn=False)
        except Exception as e:
            print(f"[TOOL] Failed to send project context: {e}")
    return msg


@tool(
    name="list_projects",
    description="Lists all available projects.",
    parameters={"type": "OBJECT", "properties": {}},
)
async def list_projects(ctx, fc):
    projects = ctx.project_manager.list_projects()
    return f"Available projects: {', '.join(projects)}"
