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

    # 2. Check Inbox for UNREAD emails
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

    print(f"📥 Found {len(messages)} unread messages.")

    # Get Sheet Data
    rows = worksheet.get_all_values()
    headers = rows[0]
    
    try:
        email_col_idx = headers.index('Email')
        status_col_idx = headers.index('Status')
        name_col_idx = headers.index('Client Name')
    except ValueError as e:
        print(f"❌ Missing column in sheet: {e}")
        return

    # 3. Process each message
    for msg in messages:
        try:
            msg_detail = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = msg_detail['payload']
            headers_list = payload.get('headers', [])
            
            sender_header = next((h['value'] for h in headers_list if h['name'] == 'From'), None)
            
            if not sender_header:
                continue
            
            print(f"📩 New Reply Found from: {sender_header}")

            # Extract Clean Email
            if '<' in sender_header and '>' in sender_header:
                from_email = sender_header.split('<')[1].split('>')[0]
            else:
                from_email = sender_header
            
            from_email = from_email.strip().lower()
            print(f"🧹 Cleaned Email: {from_email}")
            
            # Search for this email in the Google Sheet
            match_found = False
            for i, row in enumerate(rows[1:], start=2): # 1-based index, skip header
                sheet_email_raw = row[email_col_idx]
                sheet_email = str(sheet_email_raw).strip().lower()
                
                print(f"🔍 Checking against Sheet Email: {sheet_email}")
                
                if sheet_email == from_email:
                    # MATCH FOUND
                    match_found = True
                    client_name = row[name_col_idx]
                    
                    # Update 'Status' to 'Replied'
                    worksheet.update_cell(i, status_col_idx + 1, "Replied")
                    
                    # Mark email as READ
                    gmail_service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
                    
                    print(f"✅ Reply received from {client_name} ({from_email}). Sheet updated to 'Replied'.")
                    break
            
            if not match_found:
                print(f"⚠️ Ignored email from {from_email} (No match in sheet).")

        except Exception as e:
            print(f"❌ Error processing message {msg['id']}: {e}")

if __name__ == "__main__":
    process_replies()
