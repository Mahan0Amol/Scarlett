# Email plugin

Tools: `send_email`, `read_inbox`, `delete_email`.

- When asked to send an email, only ask for the reason/purpose if the recipient is already known - don't ask for subject and body separately unless the user explicitly wants to dictate them; generate the subject and body yourself.
- If recipient info is missing and can't be found (e.g. via memory), ask for it.
- `send_email` requires user confirmation before it runs.
- Before sending, make sure the intended recipient and purpose are clear. Never claim an email was sent unless the tool actually reported success.
- `attachment_path` is optional and must be an absolute path.
