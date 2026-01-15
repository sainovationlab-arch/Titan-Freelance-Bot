import json
import base64
import subprocess
import os

def upload_secrets():
    # Read credentials.json
    try:
        with open('credentials.json', 'r') as f:
            credentials_content = f.read()
    except FileNotFoundError:
        print("Error: credentials.json not found.")
        return

    # Read token.pickle and convert to base64
    try:
        with open('token.pickle', 'rb') as f:
            token_content = f.read()
            token_base64 = base64.b64encode(token_content).decode('utf-8')
    except FileNotFoundError:
        print("Error: token.pickle not found.")
        return

    # Upload GCP_CREDENTIALS
    print("Uploading GCP_CREDENTIALS...")
    subprocess.run(['gh', 'secret', 'set', 'GCP_CREDENTIALS'], input=credentials_content, text=True, check=True)

    # Upload GCP_TOKEN
    print("Uploading GCP_TOKEN...")
    subprocess.run(['gh', 'secret', 'set', 'GCP_TOKEN'], input=token_base64, text=True, check=True)

    # Upload APP_TOKENS_JSON
    print("Uploading APP_TOKENS_JSON...")
    tokens = {}
    tokens_dir = 'tokens'
    if os.path.exists(tokens_dir):
        for filename in os.listdir(tokens_dir):
            if filename.endswith('.json'):
                with open(os.path.join(tokens_dir, filename), 'r') as f:
                    tokens[filename] = f.read()
    
    tokens_json = json.dumps(tokens)
    subprocess.run(['gh', 'secret', 'set', 'APP_TOKENS_JSON'], input=tokens_json, text=True, check=True)

    print("✅ Secrets Uploaded Successfully!")

if __name__ == "__main__":
    upload_secrets()
