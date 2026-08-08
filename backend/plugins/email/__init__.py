import os
from plugins.base import tool
from .plugin import EmailAgent

def _get_agent(ctx):
    """Creates or returns the EmailAgent instance. 
    Authentication is handled inside the agent via OAuth2."""
    if "email_agent" not in ctx.state:
        ctx.state["email_agent"] = EmailAgent()
    return ctx.state["email_agent"]


@tool(
    name="send_email",
    description="Sends an email to a recipient. Can optionally attach a file.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "recipient": {"type": "STRING", "description": "The email address of the recipient."},
            "subject": {"type": "STRING", "description": "The subject of the email."},
            "body": {"type": "STRING", "description": "The body content of the email."},
            "attachment_path": {"type": "STRING", "description": "Optional. The absolute path of a file to attach to the email."}
        },
        "required": ["recipient", "subject", "body"],
    },
    requires_confirmation=True,
)
async def send_email(ctx, fc):
    recipient = fc.args["recipient"]
    subject = fc.args["subject"]
    body = fc.args["body"]
    attachment_path = fc.args.get("attachment_path") # Optional parameter
    
    print(f"[TOOL] send_email to='{recipient}' subject='{subject}' attachment='{attachment_path}'")
    try:
        success = await _get_agent(ctx).send_email(subject, body, recipient, attachment_path)
        if success:
            return f"Email sent to {recipient}" + (" with attachment." if attachment_path else ".")
        else:
            return "Failed to send email."
    except FileNotFoundError as e:
        return f"Email not sent: {e}"
    except Exception as e:
        return f"Email not sent: {e}"


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
    except Exception as e:
        return f"Error reading inbox: {e}"

@tool(
    name="delete_email",
    description="Permanently deletes a specific email using its message ID. The ID is obtained from the read_inbox tool.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "message_id": {"type": "STRING", "description": "The unique ID of the email message to delete."}
        },
        "required": ["message_id"],
    },
    requires_confirmation=True,
)
async def delete_email(ctx, fc):
    message_id = fc.args["message_id"]
    print(f"[TOOL] delete_email id='{message_id}'")
    try:
        agent = _get_agent(ctx)
        success = await agent.delete_email(message_id)
        if success:
            return f"Email with ID {message_id} has been permanently deleted."
        else:
            return "Failed to delete email."
    except Exception as e:
        return f"Error deleting email: {e}"