import asyncio
import os
import base64
import mimetypes
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Full Access Scope: Read, Send, Delete, Manage
SCOPES = ['https://mail.google.com/']

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(PLUGIN_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(PLUGIN_DIR, 'token.json')

class EmailAgent:
    def __init__(self):
        self.creds = None
        self.service = None
        self._authenticate()

    def _authenticate(self):
        if os.path.exists(TOKEN_PATH):
            self.creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_PATH):
                    raise FileNotFoundError(f"credentials.json not found in {PLUGIN_DIR}")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            with open(TOKEN_PATH, 'w') as token:
                token.write(self.creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=self.creds)

    async def send_email(self, subject, body, to_email, attachment_path=None):
        # ... (send_email code remains the same as previous)
        def _send_blocking():
            message = EmailMessage()
            message['to'] = to_email
            message['from'] = 'me'
            message['subject'] = subject
            message.set_content(body)
            
            if attachment_path:
                if not os.path.isfile(attachment_path):
                    raise FileNotFoundError(f"Attachment file not found: {attachment_path}")
                ctype, encoding = mimetypes.guess_type(attachment_path)
                if ctype is None or encoding is not None:
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)
                with open(attachment_path, 'rb') as fp:
                    file_data = fp.read()
                    filename = os.path.basename(attachment_path)
                message.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=filename)

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {'raw': raw_message}
            
            try:
                self.service.users().messages().send(userId='me', body=create_message).execute()
                return True
            except HttpError as error:
                print(f"An error occurred sending email: {error}")
                return False

        return await asyncio.to_thread(_send_blocking)

    async def read_emails(self, limit=5):
        """Fetches latest unread emails and includes their IDs for further actions like deletion."""
        def _read_blocking():
            try:
                results = self.service.users().messages().list(
                    userId='me', 
                    labelIds=['INBOX'], 
                    q='is:unread', 
                    maxResults=limit
                ).execute()
                messages = results.get('messages', [])

                if not messages:
                    return "No unread emails found."

                mails = []
                for msg in messages:
                    msg_data = self.service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                    
                    headers = msg_data['payload']['headers']
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                    
                    snippet = msg_data.get('snippet', '')
                    body_snippet = snippet[:150] + "..." if len(snippet) > 150 else snippet
                    
                    # Include Message ID
                    mails.append(f"ID: {msg['id']}\nFrom: {sender}\nSubject: {subject}\nSnippet: {body_snippet}")
                
                return "\n---\n".join(mails)
                
            except HttpError as error:
                return f"An error occurred reading emails: {error}"

        return await asyncio.to_thread(_read_blocking)

    async def delete_email(self, message_id):
        """Permanently deletes an email by its ID."""
        def _delete_blocking():
            try:
                self.service.users().messages().delete(userId='me', id=message_id).execute()
                return True
            except HttpError as error:
                print(f"An error occurred deleting email: {error}")
                return False

        return await asyncio.to_thread(_delete_blocking)
    
    