import asyncio
from plugins.base import tool


@tool(
    name="generate_cad",
    description="Generates a 3D CAD model based on a prompt.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The description of the object to generate."}
        },
        "required": ["prompt"],
    },
    behavior="NON_BLOCKING",
)
async def generate_cad(ctx, fc):
    prompt = fc.args.get("prompt", "")
    print(f"[TOOL] generate_cad prompt='{prompt}'")
    asyncio.create_task(ctx.handle_cad_request(prompt))
    # No function response needed - the model already acknowledged when the user asked.
    return None


@tool(
    name="iterate_cad",
    description=(
        "Modifies or iterates on the current CAD design based on user feedback. Use this when "
        "the user asks to adjust, change, modify, or iterate on the existing 3D model "
        "(e.g., 'make it taller', 'add a handle', 'reduce the thickness')."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The changes or modifications to apply to the current design."}
        },
        "required": ["prompt"],
    },
    behavior="NON_BLOCKING",
)
async def iterate_cad(ctx, fc):
    prompt = fc.args["prompt"]
    print(f"[TOOL] iterate_cad prompt='{prompt}'")

    if ctx.on_cad_status:
        ctx.on_cad_status("generating")

    cad_output_dir = str(ctx.project_manager.get_current_project_path() / "cad")
    cad_data = await ctx.cad_agent.iterate_prototype(prompt, output_dir=cad_output_dir)

    if cad_data:
        if ctx.on_cad_data:
            ctx.on_cad_data(cad_data)
        ctx.project_manager.save_cad_artifact("output.stl", f"Iteration: {prompt}")
        return f"Successfully iterated design: {prompt}. The updated 3D model is now displayed."

    return f"Failed to iterate design with prompt: {prompt}"
