import os
import google.generativeai as genai
from modules.services import get_gmail_service, get_gspread_client
from email.utils import parseaddr
import base64
from email.mime.text import MIMEText

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def send_reply(service, thread_id, to, subject, body):
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    message['threadId'] = thread_id
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {'raw': raw, 'threadId': thread_id}
    try:
        service.users().messages().send(userId='me', body=body).execute()
        return True
    except Exception as e:
        print(f"Error sending reply: {e}")
        return False

def get_email_content(payload):
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
    return ""

def run_replier():
    print("Running Replier...")
    gmail_service = get_gmail_service()
    gc = get_gspread_client()
    SHEET_ID = '1N3_jJkYNCtp1MQXEObtDH9FC_VzPyL2RLBW_MdfvfCM'
    
    try:
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
    except Exception:
        return

    # List unread messages
    results = gmail_service.users().messages().list(userId='me', labelIds=['UNREAD'], q='-category:promotions -category:social').execute()
    messages = results.get('messages', [])
    
    if not messages:
        print("No unread messages.")
        return

    rows = worksheet.get_all_values()
    headers = rows[0]
    
    try:
        email_col_idx = headers.index('Email')
        first_price_idx = headers.index('First Price')
        final_price_idx = headers.index('Final Price')
        req_col_idx = headers.index('Order Requirements')
    except ValueError:
        print("Missing columns for replier.")
        return

    # Cache row updates to avoid frequent API calls or re-reading, but simple loop is fine for now
    
    for msg in messages:
        msg_detail = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
        payload = msg_detail['payload']
        headers_list = payload.get('headers', [])
        
        sender = next((h['value'] for h in headers_list if h['name'] == 'From'), None)
        subject = next((h['value'] for h in headers_list if h['name'] == 'Subject'), "Re: No Subject")
        
        if not sender:
            continue
            
        name, from_email = parseaddr(sender)
        
        # Check if email is in sheet
        target_row_idx = -1
        row_data = None
        
        for i, r in enumerate(rows[1:], start=2):
            if r[email_col_idx].strip() == from_email.strip():
                target_row_idx = i
                row_data = r
                break
        
        if target_row_idx != -1:
            # Found client
            email_body = get_email_content(payload)
            first_price = row_data[first_price_idx]
            final_price = row_data[final_price_idx]
            
            # Gemini Logic
            model = genai.GenerativeModel('gemini-pro')
            prompt = f"""
            You are a freelance assistant. Connect with the client.
            Client sent this email: "{email_body}"
            
            Our goal is to close the deal. 
            My starting price is {first_price}. My lowest acceptable price is {final_price}.
            Negotiate politely.
            
            If the client agrees to a price within range or provides requirements, output the reply content.
            
            ALSO, strictly follow this format for the LAST line of your response:
            STATUS: [AGREED/NEGOTIATING] | REQUIREMENTS: [Summary of requirements if agreed, else None]
            
            Write the email reply now.
            """
            
            response = model.generate_content(prompt)
            reply_text = response.text
            
            # Parse status
            lines = reply_text.strip().split('\n')
            last_line = lines[-1]
            content_to_send = "\n".join(lines[:-1]) # Remove status line
            
            if "STATUS:" in last_line:
                status_part = last_line.split('|')[0].replace("STATUS:", "").strip()
                req_part = last_line.split('|')[1].replace("REQUIREMENTS:", "").strip()
                
                if status_part == "AGREED":
                    # Update sheet
                    worksheet.update_cell(target_row_idx, req_col_idx + 1, req_part)
            else:
                content_to_send = reply_text # Fallback
            
            send_reply(gmail_service, msg_detail['threadId'], from_email, subject, content_to_send)
            
            # Mark as read
            gmail_service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
            print(f"Replied to {from_email}")

if __name__ == "__main__":
    run_replier()
