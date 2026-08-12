# Cmd plugin

Tool: `run_cmd`.

- Executes a Windows CMD command on the host and returns its output. Requires user confirmation before it runs.
- On Windows, use `cd` and `cd /d <drive>:\<path>` when changing drives is required.
- Report useful results rather than dumping huge output - truncate long output intelligently.
- Do not run destructive commands unless the user clearly intends the operation.
- This tool sends its own result back asynchronously once the command finishes; don't expect an immediate synchronous return.
