from plugins.base import tool


@tool(
    name="send_email",
    description="Sends an email to a recipient.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "recipient": {"type": "STRING", "description": "The email address of the recipient."},
            "subject": {"type": "STRING", "description": "The subject of the email."},
            "body": {"type": "STRING", "description": "The body content of the email."},
        },
        "required": ["recipient", "subject", "body"],
    },
)
async def send_email(ctx, fc):
    recipient = fc.args["recipient"]
    subject = fc.args["subject"]
    body = fc.args["body"]
    print(f"[TOOL] send_email to='{recipient}' subject='{subject}'")
    await ctx.email_agent.send_email(subject, body, recipient)
    return f"Email sent to {recipient}"
