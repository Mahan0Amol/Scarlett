import os
from plugins.base import tool
from .plugin import EmailAgent


def _get_agent(ctx):
    """Config comes from environment variables (set them in your .env)"""
    if "email_agent" not in ctx.state:
        ctx.state["email_agent"] = EmailAgent(email_config={
            "email": os.getenv("EMAIL_ADDRESS"),
            "password": os.getenv("EMAIL_APP_PASSWORD"),
            "smtp": os.getenv("EMAIL_SMTP", "smtp.gmail.com"),
            "port": int(os.getenv("EMAIL_PORT", "587")),
            "imap": os.getenv("EMAIL_IMAP", "imap.gmail.com"), # Added IMAP config
            "imap_port": int(os.getenv("EMAIL_IMAP_PORT", "993")),
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


@tool(
    name="read_inbox",
    description="Checks the user's email inbox for unread emails and returns a summary of the latest ones.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "limit": {"type": "STRING", "description": "Number of recent unread emails to fetch. Default is 5."}
        },
        "required": [],
    },
)
async def read_inbox(ctx, fc):
    limit = int(fc.args.get("limit", 5))
    print(f"[TOOL] read_inbox limit={limit}")
    try:
        agent = _get_agent(ctx)
        result = await agent.read_emails(limit)
        return result
    except ValueError as e:
        return f"Cannot read inbox: {e}. Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in your .env."
    except Exception as e:
        return f"Error reading inbox: {e}"