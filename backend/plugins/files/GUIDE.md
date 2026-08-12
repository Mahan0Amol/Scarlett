# Files plugin

Tools: `write_file`, `read_directory`, `read_file`.

- Files are saved inside the active project by default (see the project plugin) - don't invent
  arbitrary file paths.
- If a required path is unknown and can't be discovered from available tools or memory, ask the
  user rather than guessing.
- These tools report their result back to the model asynchronously via a notification rather than
  a direct synchronous return - expect a short delay between the call and hearing the outcome.
