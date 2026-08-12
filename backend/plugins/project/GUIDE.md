# Project plugin

Tools: `create_project`, `switch_project`, `list_projects`.

Projects are the primary organisation for Scarlett-managed files. Any plugin that writes project
artifacts (CAD output, files, etc.) should ensure an active (non-"temp") project exists first via
`ctx.ensure_project(...)` - the model itself doesn't need to call these tools before every file
operation, only when the user is explicitly organising or switching between projects, or when no
active project exists yet and one is needed:

- If no active project exists and the task requires project storage, create/select an appropriate
  one.
- If the user needs to choose between multiple existing projects, list them and wait for the choice
  rather than guessing.
- Do not invent project names - ask the user if it's unclear which project they mean.
