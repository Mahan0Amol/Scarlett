# CAD plugin

Tools: `generate_cad`, `iterate_cad`.

- `generate_cad` starts a new 3D model from a natural-language description; `iterate_cad` refines the current model with a follow-up instruction.
- Both are non-blocking / fire-and-forget from the dispatcher's point of view: they kick off a background job and the frontend shows progress, so don't expect a synchronous "done" result back from the call itself.
- When the requested design is complete (you'll be notified), tell the user it's ready and visible - don't claim it's ready before that.
