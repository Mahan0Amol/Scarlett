import asyncio
from plugins.base import tool
from .plugin import CadAgent


def _get_agent(ctx):
    """Lazily builds (and caches on ctx.state) this plugin's own CadAgent.
    Nothing outside this file ever needs to import or construct CadAgent -
    that's what makes this folder fully self-contained."""
    if "cad_agent" not in ctx.state:
        ctx.state["cad_agent"] = CadAgent(
            on_thought=lambda text: ctx.emit("cad_thought", {"text": text}),
            on_status=lambda status: ctx.emit("cad_status", status if isinstance(status, dict) else {"status": status}),
        )
    return ctx.state["cad_agent"]


async def _run_cad_generation(ctx, prompt):
    """Background task kicked off by the generate_cad tool."""
    print(f"[scarlett DEBUG] [CAD] Background Task Started: generate('{prompt}')")
    ctx.emit("cad_status", {"status": "generating"})

    await ctx.ensure_project("CAD")

    cad_output_dir = str(ctx.project_manager.get_current_project_path() / "cad")
    cad_data = await _get_agent(ctx).generate_prototype(prompt, output_dir=cad_output_dir)

    if cad_data:
        print(
            f"[scarlett DEBUG] [CAD] Got data: {len(cad_data.get('vertices', []))} vertices, "
            f"{len(cad_data.get('edges', []))} edges."
        )
        ctx.emit("cad_data", cad_data)

        artifact_name = cad_data.get("file_path", "output.stl")
        ctx.project_manager.save_cad_artifact(artifact_name, prompt)

        await ctx.notify_model(
            "CAD generation is complete! The 3D model is now displayed for the user. Let them know it's ready."
        )
    else:
        print("[scarlett DEBUG] [CAD] Generation returned None.")
        await ctx.notify_model("CAD generation failed.")


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
    asyncio.create_task(_run_cad_generation(ctx, prompt))
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

    ctx.emit("cad_status", {"status": "generating"})

    cad_output_dir = str(ctx.project_manager.get_current_project_path() / "cad")
    cad_data = await _get_agent(ctx).iterate_prototype(prompt, output_dir=cad_output_dir)

    if cad_data:
        ctx.emit("cad_data", cad_data)
        ctx.project_manager.save_cad_artifact("output.stl", f"Iteration: {prompt}")
        return f"Successfully iterated design: {prompt}. The updated 3D model is now displayed."

    return f"Failed to iterate design with prompt: {prompt}"
