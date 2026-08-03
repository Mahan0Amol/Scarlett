import os
from plugins.base import tool
from .plugin import EmailAgent


def _get_agent(ctx):
    """Config comes from environment variables (set them in your .env),
    the same place GEMINI_API_KEY already lives - not hardcoded here."""
    if "email_agent" not in ctx.state:
        ctx.state["email_agent"] = EmailAgent(email_config={
            "email": os.getenv("EMAIL_ADDRESS"),
            "password": os.getenv("EMAIL_APP_PASSWORD"),
            "smtp": os.getenv("EMAIL_SMTP", "smtp.gmail.com"),
            "port": int(os.getenv("EMAIL_PORT", "587")),
        })
    return ctx.state["email_agent"]


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
    try:
        await _get_agent(ctx).send_email(subject, body, recipient)
    except ValueError as e:
        return f"Email not sent: {e}. Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in your .env."
    return f"Email sent to {recipient}"
