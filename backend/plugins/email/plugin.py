import asyncio
import os
import smtplib
from email.message import EmailMessage


class EmailAgent:
    def __init__(self, email_config=None):
        self.email_config = {
            "email": os.getenv("EMAIL_ADDRESS"),
            "password": os.getenv("EMAIL_PASSWORD"),
            "smtp": "smtp.gmail.com",
            "port": 587
        }

    async def send_email(self, subject, body, to_email):
        sender = self.email_config.get("email")
        password = self.email_config.get("password")
        smtp_server = self.email_config.get("smtp", "smtp.gmail.com")
        port = self.email_config.get("port", 587)

        if not sender or not password:
            raise ValueError("EmailAgent not configured with email/password")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        msg.set_content(body)

        def _send_blocking():
            with smtplib.SMTP(smtp_server, port) as server:
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)

        await asyncio.to_thread(_send_blocking)
        return True
