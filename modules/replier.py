import os
import random
import json
import time
import base64
import re
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

def get_sender_display_name(email_address):
    """
    Derives a display name from the email address.
    """
    try:
        local_part = email_address.split('@')[0]
        local_part = re.sub(r'\d+', '', local_part)
        local_part = local_part.replace('art', ' Art').replace('lab', ' Lab')
        clean_name = local_part.strip().title()
        clean_name = re.sub(r'\s+', ' ', clean_name)
        return clean_name
    except Exception:
        return "Solanki Art"

def check_last_sender_is_me(service, thread_id, my_email):
    """
    Fetches the thread and checks if the very last message is from 'me'.
    Returns True if I was the last sender.
    """
    try:
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        messages = thread.get('messages', [])
        if not messages:
            return False
            
        last_msg = messages[-1]
        
        # Determine sender of last message
        payload = last_msg.get('payload', {})
        headers_list = payload.get('headers', [])
        sender_header = next((h['value'] for h in headers_list if h['name'] == 'From'), "")
        
        if '<' in sender_header:
            last_sender_email = sender_header.split('<')[1].split('>')[0]
        else:
            last_sender_email = sender_header
            
        last_sender_email = last_sender_email.strip().lower()
        my_email = my_email.strip().lower()
        
        return last_sender_email == my_email
    except Exception as e:
        print(f"      ⚠️ Warning: Could not check thread history: {e}")
        return False

def process_replies():
    print("Running Replier Bot (Aggressive Sales & Continuous Loop)...")
    
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
        free_gift_col_idx = headers.index('Free Gift')
        
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
            
        # Verify Identity (Safety Check)
        try:
             profile = gmail_service.users().getProfile(userId='me').execute()
             logged_in_email = profile.get('emailAddress').lower()
             if logged_in_email != current_account:
                 print(f"❌ Mismatch! Logged in as {logged_in_email}, but expected {current_account}. Skipping safely.")
                 continue
        except Exception as e:
            print(f"❌ Error verifying identity for {current_account}: {e}")
            continue
            
        # 1. Derive Name from Email (Dynamic Signature)
        sender_display_name = get_sender_display_name(current_account)
        print(f"   ✍️  Signature for this batch: '{sender_display_name}'")

        # Build Whitelist for THIS Account (Sent OR Negotiating)
        valid_clients = {} # {client_email: row_index}
        for i, row in enumerate(rows[1:], start=2):
            if len(row) > gmail_col_idx and row[gmail_col_idx].strip().lower() == current_account:
                # Check Status
                if len(row) > status_col_idx:
                    current_status = row[status_col_idx].strip()
                    if current_status in ['Sent', 'Negotiating']:
                        # Add to whitelist
                        if len(row) > email_col_idx:
                            c_email = str(row[email_col_idx]).strip().lower()
                            if c_email:
                                valid_clients[c_email] = i
        
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
            continue
            
        print(f"   ↳ Found {len(messages)} unread messages. Processing...")

        # Process Messages
        for msg in messages:
            try:
                msg_detail = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
                payload = msg_detail['payload']
                headers_list = payload.get('headers', [])
                thread_id = msg_detail.get('threadId')
                
                sender_header = next((h['value'] for h in headers_list if h['name'] == 'From'), None)
                if not sender_header: continue
                
                # Extract Email
                if '<' in sender_header:
                    from_email = sender_header.split('<')[1].split('>')[0]
                else:
                    from_email = sender_header
                from_email = from_email.strip().lower()

                # CHECK WHITELIST (Continuous Conversation Logic)
                if from_email in valid_clients:
                    print(f"   ✅ MATCH: {from_email}")
                    
                    # --- CRITICAL: Thread Check (Prevent Double Reply) ---
                    if check_last_sender_is_me(gmail_service, thread_id, current_account):
                        print("      ✋ Last message was from ME. Waiting for client. Skipping.")
                        # Mark read anyway? No, keep unread if I want to be reminded? 
                        # Actually, if I sent the last one, why is this unread? 
                        # Maybe the client sent 2 emails. The first one I replied to. The second one (this one) is later?
                        # If check_last_sender_is_me returns True, it means my reply is the LATEST.
                        # So this unread message is BEHIND my reply.
                        # So I should mark this 'old' unread message as read to clear queue.
                        gmail_service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
                        continue
                    # -----------------------------------------------------

                    row_idx = valid_clients[from_email]
                    row_data = rows[row_idx - 1]
                    
                    # 3. Data Extraction (Know the Product)
                    client_name = row_data[name_col_idx]
                    skill = row_data[skill_col_idx]
                    offer_price = row_data[offer_price_col_idx]
                    free_gift = row_data[free_gift_col_idx]
                    
                    # Get Body
                    email_body = get_email_body(payload)
                    lower_body = email_body.lower()
                    
                    # 4. Hard-Coded Negative Filter (Stop Logic)
                    stop_keywords = ["stop", "unsubscribe", "remove", "not interested", "spam", "no thanks"]
                    if any(keyword in lower_body for keyword in stop_keywords):
                         print("      ⛔ OPT-OUT DETECTED. Marking as 'Opt-out'.")
                         worksheet.update_cell(row_idx, status_col_idx + 1, "Opt-out")
                         # Mark as read
                         gmail_service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
                         continue
                    # -------------------------------

                    images = find_images(gmail_service, 'me', msg['id'], payload)
                    subject = next((h['value'] for h in headers_list if h['name'] == 'Subject'), "Re: Conversation")

                    print(f"      🧠 Generating AGGRESSIVE Sales Reply for {client_name}...")
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    intent = "Negotiating"
                    new_status = "Negotiating"

                    # Vision Logic (Payment Check)
                    if images:
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
                            ai_reply_text = "I received the image but couldn't verify it automatically. Checking manually."
                            new_status = "Payment Pending"
                    else:
                        # 5. Wolf of Wall Street Persona (Aggressive)
                        prompt = f"""You are an elite Sales Closer for {sender_display_name}. You do not just 'answer questions' — you overcome objections and close deals. You are speaking to {client_name} about {skill}.

The Deal: Special price of {offer_price} (includes {free_gift}).
The User Said: "{email_body}"

Strategy:
1. Language: Reply in the SAME language as the user (DETECT IT).
2. Negotiation Phase: If they argue price -> Defend value, Sell ROI, Create Urgency.
3. Closing Phase (CRITICAL): If they AGREE (say 'Yes', 'Okay', 'Agreed', 'Send link') -> DO NOT ask for money. 
   - Say EXACTLY: "Fantastic decision! To get started on your Premium Logo immediately, I just need a few details: What is the exact Brand Name you want? Do you have any specific Color Preferences or Slogans? Once you reply with this, I will hand over your file to our Delivery Agent to finalize the order."
4. Handoff Phase: If they send the details (Brand Name, Colors) -> Reply: "Perfect! I have locked in your order. Our Delivery Team will contact you shortly for the final step. Welcome to {sender_display_name}!"
5. Tone: Professional, Enthusiastic, Deal-Closing.
6. Keep it under 100 words.
7. Sign-off: "Best regards, {sender_display_name}"
"""
                        try:
                            resp = model.generate_content(prompt)
                            ai_reply_text = resp.text.strip()
                            if ai_reply_text.startswith("```"): ai_reply_text = ai_reply_text.replace("```","")
                            
                            new_status = "Negotiating" # Status Update
                        except Exception as e:
                            print(f"      AI Error: {e}")
                            ai_reply_text = f"Thanks for your interest, {client_name}. I can offer you a special price of {offer_price}. Shall we proceed?\n\nBest regards,\n{sender_display_name}"

                    # Send Reply
                    msg_obj = create_message(current_account, from_email, subject, ai_reply_text, thread_id=msg_detail.get('threadId'))
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
