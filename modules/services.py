import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import gspread
from google.oauth2.credentials import Credentials

# Scopes for Gmail and Sheets
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/spreadsheets'
]

def get_creds():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def get_service_for_email(email_address):
    """
    Constructs a Gmail service instance for a specific email address
    by looking for tokens/token_{email_address}.json
    """
    token_path = f'tokens/token_{email_address}.json'
    
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            print(f"Error loading credentials for {email_address}: {e}")
            return None
    else:
        print(f"Token file not found for: {email_address}")
        return None

def get_gmail_service():
    creds = get_creds()
    return build('gmail', 'v1', credentials=creds)

def get_gspread_client():
    creds = get_creds()
    return gspread.authorize(creds)
