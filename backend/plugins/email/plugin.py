import asyncio
import smtplib
import imaplib
import email
from email.header import decode_header
from email.message import EmailMessage

class EmailAgent:
    def __init__(self, email_config=None):
        self.email_config = email_config or {}

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

    async def read_emails(self, limit=5):
        """Connects to IMAP server and fetches the latest emails."""
        
        sender = self.email_config.get("email")
        password = self.email_config.get("password")
        imap_server = self.email_config.get("imap", "imap.gmail.com")
        imap_port = self.email_config.get("imap_port", 993)

        if not sender or not password:
            raise ValueError("EmailAgent not configured with email/password")

        def _read_blocking():
            mails = []

            try:
                # Connect to IMAP server
                mail = imaplib.IMAP4_SSL(imap_server, imap_port)
                mail.login(sender, password)

                # Select inbox before searching
                mail.select("inbox")

                # Search emails
                status, messages = mail.search(None, "ALL")

                if status != "OK":
                    return "Failed to retrieve emails."

                mail_ids = messages[0].split()

                if not mail_ids:
                    return "No emails found."

                # Get latest N emails
                latest_ids = mail_ids[-limit:]

                # Newest first
                for e_id in reversed(latest_ids):

                    status, msg_data = mail.fetch(e_id, "(RFC822)")

                    if status == "OK":

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)

                        # Decode subject
                        subject_header = msg.get(
                            "Subject",
                            "(No Subject)"
                        )

                        decoded_subject = decode_header(subject_header)[0]

                        if isinstance(decoded_subject[0], bytes):
                            subject = decoded_subject[0].decode(
                                decoded_subject[1] or "utf-8",
                                errors="replace"
                            )
                        else:
                            subject = decoded_subject[0]

                        from_ = msg.get("From", "Unknown")

                        # Extract body
                        body_snippet = ""

                        if msg.is_multipart():
                            for part in msg.walk():

                                if part.get_content_type() == "text/plain":

                                    payload = part.get_payload(
                                        decode=True
                                    )

                                    if payload:
                                        body_snippet = payload.decode(
                                            errors="replace"
                                        )

                                    break

                        else:
                            payload = msg.get_payload(
                                decode=True
                            )

                            if payload:
                                body_snippet = payload.decode(
                                    errors="replace"
                                )


                        # Clean text
                        words = body_snippet.split()

                        if len(words) > 50:
                            body_snippet = (
                                " ".join(words[:50])
                                + "..."
                            )

                        mails.append(
                            f"From: {from_}\n"
                            f"Subject: {subject}\n"
                            f"Snippet: {body_snippet}"
                        )

                mail.logout()

                return "\n---\n".join(mails) if mails else "No emails found."

            except Exception as e:
                return f"Error reading emails: {e}"


        return await asyncio.to_thread(_read_blocking)