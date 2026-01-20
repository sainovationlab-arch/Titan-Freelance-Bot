import os
import random
import json
import time
import base64
from email.mime.text import MIMEText
from email.utils import parseaddr
import google.generativeai as genai
from modules.services import get_gmail_service, get_gspread_client

# Configure Gemini
# Ensure GEMINI_API_KEY is set in environment variables
gemini_keys_env = os.getenv("GEMINI_API_KEY")
if gemini_keys_env:
    keys = [k.strip() for k in gemini_keys_env.split(',') if k.strip()]
    if keys:
        selected_key = random.choice(keys)
        genai.configure(api_key=selected_key)
        print(f"🔑 Gemini configured with 1 of {len(keys)} keys.")
        print(f"📦 Installed GenAI Version: {genai.__version__}")
    else:
        print("❌ Error: GEMINI_API_KEY provided but contains no valid keys.")
else:
    print("❌ Error: GEMINI_API_KEY not found in environment.")

def get_email_body(payload):
    """Recursively attempts to find the text/plain part of the email body."""
    parts = payload.get('parts')
    if not parts:
        data = payload.get('body').get('data')
        if data:
            return base64.urlsafe_b64decode(data).decode()
    else:
        for part in parts:
            if part['mimeType'] == 'text/plain':
                data = part.get('body').get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode()
            elif part.get('parts'):
                # recurse if nested
                return get_email_body(part)
    return ""

def create_message(sender, to, subject, message_text, thread_id=None):
    """Create a message for an email."""
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    if thread_id:
        message['threadId'] = thread_id
        
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw, 'threadId': thread_id} if thread_id else {'raw': raw}

def send_message(service, user_id, message):
    """Send an email message."""
    try:
        message = service.users().messages().send(userId=user_id, body=message).execute()
        print(f"Message Id: {message['id']} sent.")
        return message
    except Exception as e:
        print(f"An error occurred sending message: {e}")
        return None

def process_replies():
    print("Running Replier Bot (Autonomous AI Negotiator)...")
    
    # 1. Login to Gmail and Sheets
    gmail_service = get_gmail_service()
    if not gmail_service:
        print("❌ Error: Could not connect to Gmail.")
        return

    gc = get_gspread_client()
    SHEET_ID = '1N3_jJkYNCtp1MQXEObtDH9FC_VzPyL2RLBW_MdfvfCM'
    
    try:
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"❌ Error connecting to Sheet: {e}")
        return

    # Get Sheet Data First (VIP Whitelist)
    rows = worksheet.get_all_values()
    headers = rows[0]
    
    try:
        email_col_idx = headers.index('Email')
        status_col_idx = headers.index('Status')
        name_col_idx = headers.index('Client Name')
        gmail_col_idx = headers.index('Gmail Account')
        
        # AI Data Columns
        skill_col_idx = headers.index('Selected Skill')
        offer_price_col_idx = headers.index('Offer Price')
        final_price_col_idx = headers.index('Final Price') 
        portfolio_col_idx = headers.index('Portfolio Link')
        
        # New Column for Order Requirements
        try:
            order_req_col_idx = headers.index('Order Requirements')
        except ValueError:
            print("⚠️ 'Order Requirements' column not found. Adding it would be good, but proceeding without writing requirements.")
            order_req_col_idx = -1
        
    except ValueError as e:
        print(f"❌ Missing column in sheet: {e}")
        return

    # --- Account Matching Logic ---
    try:
        profile = gmail_service.users().getProfile(userId='me').execute()
        current_bot_email = profile.get('emailAddress')
        
        # Get Target Email from Sheet (First Data Row)
        if len(rows) > 1 and len(rows[1]) > gmail_col_idx:
            target_sheet_email = rows[1][gmail_col_idx].strip()
        else:
            print("❌ Sheet is empty or missing Gmail Account in first row.")
            return

        print(f"🕵️ LOGGED IN AS: {current_bot_email}")
        print(f"📋 SHEET REQUIRES: {target_sheet_email}")

        if current_bot_email.lower().strip() != target_sheet_email.lower():
            print(f"❌ CRITICAL ERROR: Token Mismatch! I am logged in as {current_bot_email}, but the Sheet says I should be {target_sheet_email}.")
            print(f"💡 ACTION: Please generate a NEW token for {target_sheet_email} and update GitHub Secrets.")
            return # EXIT immediately

    except Exception as e:
        print(f"❌ Error verifying account identity: {e}")
        return
    # ------------------------------

    # Build VIP Whitelist
    valid_clients = {} # {email: row_index} with row_index being actual integer index in 'rows'
    valid_statuses = ['Sent', 'Follow-up 1', 'Replied', 'AI Negotiating', 'Negotiating']
    
    for i, row in enumerate(rows[1:], start=2): # Start=2 because row 1 is header, so index 2 matches sheet row 2
        # Safety check for short rows
        if len(row) > email_col_idx and len(row) > status_col_idx:
            raw_email = row[email_col_idx]
            status_val = row[status_col_idx].strip()
            
            clean_email = str(raw_email).strip().lower()
            
            # Filter: Only monitor if we have contacted them or are in conversation
            if clean_email and status_val in valid_statuses:
                valid_clients[clean_email] = i
    
    print(f"📋 Monitoring {len(valid_clients)} Active Clients (Status: Sent/Replied/etc). Ignoring pending rows.")

    # 2. Check Inbox for UNREAD emails
    if len(valid_clients) == 0:
        print("⚠️ No valid clients found in sheet. Stopping.")
        return

    try:
        # q='is:unread' or labelIds=['UNREAD']
        results = gmail_service.users().messages().list(userId='me', labelIds=['UNREAD'], q='-category:promotions -category:social').execute()
        messages = results.get('messages', [])
    except Exception as e:
        print(f"❌ Error checking inbox: {e}")
        return
    
    if not messages:
        print("📭 No unread messages found.")
        return

    print(f"📥 Found {len(messages)} unread messages. Scanning for VIPs...")

    # 3. Process each message
    for msg in messages:
        try:
            msg_detail = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = msg_detail['payload']
            headers_list = payload.get('headers', [])
            subject = next((h['value'] for h in headers_list if h['name'] == 'Subject'), "Re: Conversation")
            
            sender_header = next((h['value'] for h in headers_list if h['name'] == 'From'), None)
            
            if not sender_header:
                continue
            
            print(f"🧐 Scanning: {sender_header}")

            # Extract Clean Email
            if '<' in sender_header and '>' in sender_header:
                from_email = sender_header.split('<')[1].split('>')[0]
            else:
                from_email = sender_header
            
            from_email = from_email.strip().lower()
            print(f" 🧹 Cleaned: {from_email}")
            
            # Smart Scan (VIP Check)
            if from_email in valid_clients:
                print("✅ MATCH!")
                # MATCH FOUND
                row_idx = valid_clients[from_email]
                rows_list_idx = row_idx - 1
                row_data = rows[rows_list_idx]
                
                if rows_list_idx < len(rows):
                    client_name = row_data[name_col_idx]
                    skill = row_data[skill_col_idx]
                    offer_price = row_data[offer_price_col_idx]
                    # Handle Final Price missing gracefully if needed
                    final_price = row_data[final_price_col_idx] if len(row_data) > final_price_col_idx else offer_price
                    portfolio = row_data[portfolio_col_idx]
                else:
                    client_name = "Unknown"
                    skill = "Project"
                    offer_price = "$?"
                    final_price = "$?"
                    portfolio = ""

                # 1. Fetch Request Body
                email_body = get_email_body(payload)
                
                # 2. Generate AI Reply with Intent Detection mechanism
                print(f"🧠 Generating AI Reply & Analyzing Intent for {client_name} regarding {skill}...")
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # Enhanced Prompt for Intent Detection + Reply
                prompt = f"""
You are a professional business developer for {client_name}. 
Context: We offered "{skill}" for {offer_price}. The absolute lowest we can go is {final_price}. 
Client said: "{email_body}" 

TASK 1: CLASSIFY INTENT
- "Ordered": If client says "Let's start", "Here are details", "I want to buy", "proceed", or sends requirements.
- "Negotiating": If discussing price, samples, asking questions, or negotiating.
- "Stop": If client says "No", "Not interested", "Unsubscribe" or stop contacting.

TASK 2: EXTRACT DETAILS (If Intent is 'Ordered')
- Extract specific project requirements (e.g., 'Red logo', 'SEO for website').
- Keep it under 20 words.
- If no details found, return "Details pending".

TASK 3: GENERATE REPLY based on intent.
- If Ordered: Thank them and say we are ready to start.
- If Negotiating: Answer questions, handle objections. If price complaint, offer {offer_price} first, then {final_price}.
- If Stop: Polite confirmation that we will stop contacting.
- Constraints: 
    - No "Thanks for prompt reply". Use natural openers.
    - Include portfolio {portfolio} if asked.
    - Sign off: 'Best regards, SA Innovation Lab'.
    - Under 100 words.

OUTPUT FORMAT (JSON ONLY):
{{
  "intent": "Ordered" | "Negotiating" | "Stop",
  "order_requirements": "Extracted requirements or 'Details pending' (only if Ordered, else null)",
  "reply_text": "Your email reply here"
}}
"""
                try:
                    response = model.generate_content(prompt)
                    # Clean up json if markdown code blocks are present
                    clean_text = response.text.strip()
                    if clean_text.startswith("```json"):
                        clean_text = clean_text[7:]
                    if clean_text.startswith("```"):
                         clean_text = clean_text[3:] 
                    if clean_text.endswith("```"):
                        clean_text = clean_text[:-3]
                    
                    data = json.loads(clean_text)
                    intent = data.get("intent", "Negotiating")
                    order_requirements = data.get("order_requirements", "")
                    ai_reply_text = data.get("reply_text", "Thanks for your email. We will get back to you soon.")
                    
                except Exception as e:
                    print(f"❌ AI Analysis Failed: {e}. Falling back to default.")
                    intent = "Negotiating"
                    order_requirements = ""
                    ai_reply_text = "Thanks for your email! We will proceed with the discussion."

                # Map Intent to Status
                status_map = {
                    "Ordered": "Ordered",
                    "Negotiating": "Negotiating", 
                    "Stop": "Stop"
                }
                new_status = status_map.get(intent, "Negotiating")

                # 3. Create & Send Message DIRECTLY
                msg_object = create_message(current_bot_email, from_email, subject, ai_reply_text, thread_id=msg_detail['threadId'])
                send_message(gmail_service, 'me', msg_object)

                # 4. Update Status and Requirements
                worksheet.update_cell(row_idx, status_col_idx + 1, new_status)
                
                # Write Order Requirements if found and column exists
                if intent == "Ordered" and order_requirements and order_req_col_idx != -1:
                     worksheet.update_cell(row_idx, order_req_col_idx + 1, order_requirements)
                     print(f"📝 Order Requirements Saved: {order_requirements}")
                
                # 5. Mark as Read
                gmail_service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
                
                print(f"🤖 AI Reply SENT. Intent: {intent}. Sheet updated to '{new_status}'.")
            
            else:
                # Ignore silently
                pass

        except Exception as e:
            print(f"❌ Error processing message {msg['id']}: {e}")

if __name__ == "__main__":
    process_replies()
