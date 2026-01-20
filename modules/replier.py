import os
import random
import json
import time
import base64
import io
from PIL import Image
from email.mime.text import MIMEText
from email.utils import parseaddr
import google.generativeai as genai
from modules.services import get_gspread_client, get_service_for_email

# Configure Gemini
gemini_keys_env = os.getenv("GEMINI_API_KEY")
if gemini_keys_env:
    keys = [k.strip() for k in gemini_keys_env.split(',') if k.strip()]
    if keys:
        selected_key = random.choice(keys)
        genai.configure(api_key=selected_key)
        print(f"🔑 Gemini configured with 1 of {len(keys)} keys.")
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
                return get_email_body(part)
    return ""

def get_image_data_from_part(service, user_id, msg_id, part):
    """Helper to fetch image data from a message part."""
    if 'body' in part and 'attachmentId' in part['body']:
        att_id = part['body']['attachmentId']
        att = service.users().messages().attachments().get(userId=user_id, messageId=msg_id, id=att_id).execute()
        data = att['data']
    elif 'body' in part and 'data' in part['body']:
        data = part['body']['data']
    else:
        return None
    
    if data:
        file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
        return Image.open(io.BytesIO(file_data))
    return None

def find_images(service, user_id, msg_id, payload):
    """Recursively find and fetch images."""
    found_images = []
    parts = payload.get('parts')
    if not parts:
        if payload.get('mimeType', '').startswith('image/'):
            img = get_image_data_from_part(service, user_id, msg_id, payload)
            if img: found_images.append(img)
    else:
        for part in parts:
            if part.get('mimeType', '').startswith('image/'):
                img = get_image_data_from_part(service, user_id, msg_id, part)
                if img: found_images.append(img)
            elif part.get('parts'):
                found_images.extend(find_images(service, user_id, msg_id, part))
    return found_images

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
    print("Running Replier Bot (Grouped Processing)...")
    
    # 1. Connect to Sheet
    gc = get_gspread_client()
    SHEET_ID = '1N3_jJkYNCtp1MQXEObtDH9FC_VzPyL2RLBW_MdfvfCM'
    
    try:
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"❌ Error connecting to Sheet: {e}")
        return

    # Get Sheet Data
    rows = worksheet.get_all_values()
    if not rows:
        print("❌ Sheet is empty.")
        return
        
    headers = rows[0]
    try:
        email_col_idx = headers.index('Email')
        status_col_idx = headers.index('Status')
        name_col_idx = headers.index('Client Name')
        gmail_col_idx = headers.index('Gmail Account')
        skill_col_idx = headers.index('Selected Skill')
        offer_price_col_idx = headers.index('Offer Price')
        final_price_col_idx = headers.index('Final Price') 
        portfolio_col_idx = headers.index('Portfolio Link')
        
        try:
            payment_status_col_idx = headers.index('Payment Status')
        except ValueError:
             payment_status_col_idx = 20 # Fallback
             
    except ValueError as e:
        print(f"❌ Missing column in sheet: {e}")
        return

    # 2. Identify Unique Accounts (Column B)
    unique_accounts = set()
    for row in rows[1:]:
        if len(row) > gmail_col_idx:
            acc = row[gmail_col_idx].strip().lower()
            if acc:
                unique_accounts.add(acc)
    
    print(f"📋 Found {len(unique_accounts)} unique Gmail accounts to process.")

    # 3. Loop by Account
    for current_account in unique_accounts:
        print(f"\n🔄 Switching to account: {current_account}")
        
        # Login
        gmail_service = get_service_for_email(current_account)
        if not gmail_service:
            print(f"⚠️ Token not found for {current_account}. Skipping.")
            continue
            
        # Verify Identity
        try:
             profile = gmail_service.users().getProfile(userId='me').execute()
             logged_in_email = profile.get('emailAddress').lower()
             if logged_in_email != current_account:
                 print(f"❌ Mismatch! Logged in as {logged_in_email}, but expected {current_account}. Skipping to be safe.")
                 continue
        except Exception as e:
            print(f"❌ Error verifying identity for {current_account}: {e}")
            continue

        # Build Whitelist for THIS Account
        valid_clients = {} # {client_email: row_index}
        for i, row in enumerate(rows[1:], start=2):
            if len(row) > gmail_col_idx and row[gmail_col_idx].strip().lower() == current_account:
                # Add to whitelist
                if len(row) > email_col_idx:
                    c_email = str(row[email_col_idx]).strip().lower()
                    if c_email:
                        valid_clients[c_email] = i
        
        print(f"   ↳ Monitoring {len(valid_clients)} active clients for this account.")
        if not valid_clients:
            continue

        # Check Inbox
        try:
            results = gmail_service.users().messages().list(userId='me', labelIds=['UNREAD'], q='-category:promotions -category:social').execute()
            messages = results.get('messages', [])
        except Exception as e:
            print(f"   xxxx Error checking inbox: {e}")
            continue
            
        if not messages:
            print("   ↳ No unread messages.")
            continue
            
        print(f"   ↳ Found {len(messages)} unread messages. Processing...")

        # Process Messages
        for msg in messages:
            try:
                msg_detail = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
                payload = msg_detail['payload']
                headers_list = payload.get('headers', [])
                
                sender_header = next((h['value'] for h in headers_list if h['name'] == 'From'), None)
                if not sender_header: continue
                
                # Extract Email
                if '<' in sender_header:
                    from_email = sender_header.split('<')[1].split('>')[0]
                else:
                    from_email = sender_header
                from_email = from_email.strip().lower()

                # CHECK WHITELIST
                if from_email in valid_clients:
                    print(f"   ✅ MATCH: {from_email}")
                    row_idx = valid_clients[from_email]
                    # Logic to generate reply...
                    row_data = rows[row_idx - 1]
                    
                    # Extract Details
                    client_name = row_data[name_col_idx]
                    skill = row_data[skill_col_idx]
                    offer_price = row_data[offer_price_col_idx]
                    final_price = row_data[final_price_col_idx] if len(row_data) > final_price_col_idx else offer_price
                    portfolio = row_data[portfolio_col_idx]
                    
                    # Generate Reply
                    email_body = get_email_body(payload)
                    images = find_images(gmail_service, 'me', msg['id'], payload)
                    
                    subject = next((h['value'] for h in headers_list if h['name'] == 'Subject'), "Re: Conversation")

                    # Copy AI Logic from previous version (simplified for brevity but functional)
                    print(f"      🧠 Generating Reply for {client_name}...")
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    intent = "Negotiating"
                    ai_reply_text = "Thanks."
                    new_status = "Negotiating"

                    if images:
                        # Vision Logic
                        prompt = ["Analyze this image. Is this a valid payment screenshot showing a 'Successful' transaction? Extract the Amount. If it looks like a valid receipt for the expected amount, return 'VERIFIED'. If it's unclear or fake, return 'CHECK_MANUAL'.", images[0]]
                        try:
                            resp = model.generate_content(prompt)
                            if "VERIFIED" in resp.text:
                                intent = "Ordered"
                                ai_reply_text = "Payment received! Sending files shortly."
                                new_status = "Ordered"
                                if payment_status_col_idx != -1:
                                    worksheet.update_cell(row_idx, payment_status_col_idx + 1, "Paid")
                            else:
                                ai_reply_text = "Received the image, checking manually."
                                new_status = "Payment Pending"
                        except:
                            pass
                    else:
                        # Text Logic
                        prompt = f'''
You are a professional business developer for {client_name}.
Context: We offered "{skill}" for {offer_price}. Lowest: {final_price}.
Client said: "{email_body}"
TASK: Classify Intent (Ordered, Negotiating, Stop) and Generate Reply (under 100 words).
OUTPUT JSON: {{"intent": "...", "reply_text": "..."}}
'''
                        try:
                            resp = model.generate_content(prompt)
                            clean = resp.text.strip().replace("```json","").replace("```","")
                            data = json.loads(clean)
                            intent = data.get("intent", "Negotiating")
                            ai_reply_text = data.get("reply_text", "We will get back to you.")
                            new_status = intent
                        except Exception as e:
                            print(f"      AI Error: {e}")

                    # Send Reply
                    msg_obj = create_message(current_account, from_email, subject, ai_reply_text, thread_id=msg_detail['threadId'])
                    send_message(gmail_service, 'me', msg_obj)
                    
                    # Update Sheet
                    worksheet.update_cell(row_idx, status_col_idx + 1, new_status)
                    
                    # Mark Read
                    gmail_service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
                    print(f"      Reply Sent. Status: {new_status}")

                else:
                    # Ignore
                    pass

            except Exception as e:
                print(f"   Error processing message: {e}")

if __name__ == "__main__":
    process_replies()
