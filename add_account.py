import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scopes must match those used in the main application
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/spreadsheets'
]

def create_token(email_address):
    """
    Runs the OAuth flow to create a token for the specified email address.
    """
    creds = None
    # We are not loading existing tokens here because the purpose is to add/overwrite
    # a specific account's token.
    
    if os.path.exists('credentials.json'):
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    else:
        print("Error: 'credentials.json' not found. Please place it in the project root.")
        return

    # Create tokens directory if it doesn't exist
    if not os.path.exists('tokens'):
        os.makedirs('tokens')

    # Save the credentials
    token_filename = f"tokens/token_{email_address}.json"
    
    # creds.to_json() returns a JSON string representation of the credentials
    with open(token_filename, 'w') as token_file:
        token_file.write(creds.to_json())
        
    print(f"\nSuccess! Token saved to: {token_filename}")

if __name__ == '__main__':
    print("=== Gmail Account Token Generator ===")
    email = input("Enter the Email Address for this account: ").strip()
    
    if email:
        create_token(email)
    else:
        print("Invalid email address provided.")
