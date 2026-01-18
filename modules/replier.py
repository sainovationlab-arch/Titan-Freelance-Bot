import os
import time
from email.utils import parseaddr
from modules.services import get_gmail_service, get_gspread_client

def process_replies():
    print("Running Replier Bot...")
    
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
    
    # Get Sheet Data First (VIP Whitelist)
    rows = worksheet.get_all_values()
    headers = rows[0]
    
    try:
        email_col_idx = headers.index('Email')
        status_col_idx = headers.index('Status')
        name_col_idx = headers.index('Client Name')
        gmail_col_idx = headers.index('Gmail Account')
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
    
    for i, row in enumerate(rows[1:], start=2): # Start=2 because row 1 is header, so index 2 matches sheet row 2
        # Safety check for short rows
        if len(row) > email_col_idx:
            raw_email = row[email_col_idx]
            clean_email = str(raw_email).strip().lower()
            if clean_email:
                valid_clients[clean_email] = i
    
    print(f"📋 Loaded {len(valid_clients)} Client Emails from Sheet.")

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
                
                # Get Client Name from the stored row index
                # Note: 'rows' is 0-indexed list of lists.
                # 'i' in the loop above was 'start=2'.
                # So if valid_clients has '2', it corresponds to rows[1] (since rows[0] is header).
                # So rows index = row_idx - 1.
                
                rows_list_idx = row_idx - 1
                if rows_list_idx < len(rows):
                    client_name = rows[rows_list_idx][name_col_idx]
                else:
                    client_name = "Unknown"

                # Update 'Status' to 'Replied'
                worksheet.update_cell(row_idx, status_col_idx + 1, "Replied")
                
                # Mark email as READ
                gmail_service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
                
                print(f"✅ MATCH FOUND! Reply received from {client_name} ({from_email}). Sheet updated.")
            
            else:
                # Ignore silently
                pass

        except Exception as e:
            print(f"❌ Error processing message {msg['id']}: {e}")

if __name__ == "__main__":
    process_replies()
