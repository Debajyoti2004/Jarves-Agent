import os.path
import base64
import json
import logging
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup
import google.generativeai as genai
import time 
from typing import Optional,List,Dict

logger = logging.getLogger("EmailToolLogic")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'C:/Users/Debajyoti/OneDrive/Desktop/Jarves full agent/EmailAccessAgent/credentials.json'

if os.getenv("GOOGLE_API_KEY"):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    LLM_MODEL_NAME = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.0-pro")
else:
    logger.error("GOOGLE_API_KEY not found for Email Tool's LLM.")
    LLM_MODEL_NAME = None

MEMORY_FILE = "C:/Users/Debajyoti/OneDrive/Desktop/Jarves full agent/EmailAccessAgent/email_memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return {}
    return {}

def save_memory(memory_data):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory_data, f, indent=2)

def get_conversation_history(sender_email, subject_keywords):
    memory = load_memory()
    key = f"{sender_email.lower()}"
    history = memory.get(key, [])
    relevant_history = []
    if subject_keywords:
        for entry in history:
            if any(kw.lower() in entry.get("subject","").lower() for kw in subject_keywords):
                relevant_history.append(entry)
    return relevant_history if relevant_history else history[-5:]

def add_to_memory(sender_email, subject, received_text, sent_reply_text):
    memory = load_memory()
    key = f"{sender_email.lower()}"
    if key not in memory:
        memory[key] = []

    memory[key].append({
        "subject": subject,
        "received": received_text,
        "replied": sent_reply_text, 
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    memory[key] = memory[key][-20:]
    save_memory(memory)

def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try: creds.refresh(Request())
            except Exception: creds = None
        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"'{CREDENTIALS_FILE}' not found.")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            try: creds = flow.run_local_server(port=0)
            except Exception:
                print(f"Please authorize: {flow.authorization_url()[0]}")
                auth_code = input("Enter authorization code: ")
                flow.fetch_token(code=auth_code); creds = flow.credentials
        with open(TOKEN_FILE, 'w') as token: token.write(creds.to_json())
    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e: logger.error(f"Error creating Gmail service: {e}"); return None

def parse_email_body(parts):
    text_body = ""
    if parts:
        for part in parts:
            mime_type = part.get('mimeType'); body = part.get('body'); data = body.get('data')
            if data:
                decoded_data = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                if mime_type == 'text/plain': text_body += decoded_data
                elif mime_type == 'text/html':
                    soup = BeautifulSoup(decoded_data, "html.parser")
                    text_body += soup.get_text(separator='\n', strip=True)
            if 'parts' in part: text_body += parse_email_body(part['parts'])
    return text_body.strip()

def get_unread_emails(max_results=5):
    service = get_gmail_service()
    if not service: return []
    
    try:
        results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=max_results).execute()
        messages = results.get('messages', [])
        emails = []
        if not messages: logger.info("No unread messages found.")
        else:
            for msg_summary in messages:
                msg = service.users().messages().get(userId='me', id=msg_summary['id']).execute()
                payload = msg.get('payload', {}); headers = payload.get('headers', [])
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'N/A')
                sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'N/A')
                sender_email = sender; 
                if '<' in sender and '>' in sender: sender_email = sender[sender.find('<') + 1:sender.find('>')]
                body_text = "";
                if 'parts' in payload: body_text = parse_email_body(payload['parts'])
                elif 'body' in payload and payload['body'].get('data'):
                    decoded_data = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace')
                    if payload.get('mimeType') == 'text/plain': body_text = decoded_data
                    elif payload.get('mimeType') == 'text/html': body_text = BeautifulSoup(decoded_data, "html.parser").get_text(separator='\n', strip=True)
                else:
                    body_data = payload.get('body', {}).get('data')
                    if body_data: body_text = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                emails.append({'id': msg_summary['id'], 'threadId': msg.get('threadId'), 'sender': sender, 'sender_email': sender_email, 'subject': subject, 'snippet': msg.get('snippet', ''), 'body': body_text[:2000]})
        return emails
    except Exception as e: 
        logger.error(f"Error fetching unread emails: {e}", exc_info=True); return []

def draft_reply_with_llm(received_email_content: str, sender: str, subject: str, history: List[Dict]):
    if not LLM_MODEL_NAME: return "LLM not configured."
    model = genai.GenerativeModel(LLM_MODEL_NAME)
    prompt_parts = [f"You are Jarvis, an AI assistant helping to draft an email reply on behalf of your user (Debajyoti, email: majeedebajyoti2004@gmail.com).",
                    f"An email was received from: {sender}", f"Subject: {subject}", f"Received email content:\n\"\"\"\n{received_email_content}\n\"\"\""]
    if history:
        history_str = "\n---\n".join([f"Previous (Subject: {h.get('subject','N/A')}):\nReceived: {h.get('received','')[:300]}...\nReplied: {h.get('replied','')[:300]}..." for h in history])
        prompt_parts.append(f"\nRelevant conversation history:\n\"\"\"\n{history_str}\n\"\"\"")
    else: 
        prompt_parts.append("\nNo specific prior conversation history found.")
    prompt_parts.append("\nDraft a concise, professional, helpful reply from Debajyoti's perspective. Output ONLY the email body. If no reply is needed or it's spam, suggest 'No reply needed' or 'Mark as read'. If unsure, suggest Debajyoti review it.")
    full_prompt = "\n".join(prompt_parts)
    
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e: 
        return f"Error: LLM reply generation failed: {str(e)}"

def send_email(service, to: str, subject: str, message_text: str, thread_id: Optional[str] = None):
    try:
        message = MIMEText(message_text)
        message['to'] = to; message['subject'] = subject
        create_message = {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}
        
        if thread_id: 
            create_message['threadId'] = thread_id
        sent_message = service.users().messages().send(userId='me', body=create_message).execute()
        
        return True, f"Email sent. ID: {sent_message['id']}"
    except Exception as e: 
        return False, f"Failed to send email: {e}"

def mark_email_as_read(service, msg_id):
    try:
        service.users().messages().modify(userId='me', id=msg_id, body={'removeLabelIds': ['UNREAD']}).execute()
        return True
    except Exception: 
        return False