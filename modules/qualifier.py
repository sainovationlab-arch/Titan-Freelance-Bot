import os
import time
import requests
import random
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ BeautifulSoup not found. Please install it: pip install beautifulsoup4")
    BeautifulSoup = None

import google.generativeai as genai
from modules.services import get_gspread_client

def scrape_website(url):
    """Scrapes text from the given URL."""
    if not BeautifulSoup:
        return ""
    
    try:
        # Add http if missing
        if not url.startswith('http'):
            url = 'https://' + url
            
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Kill all script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text()
        
        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit to 3000 chars
        return text[:3000]
        
    except Exception as e:
        print(f"⚠️ Error scraping {url}: {e}")
        return None

def run_qualifier():
    print("Running Lead Qualifier Bot...")
    
    if not BeautifulSoup:
        return

    # 1. Configure Gemini
    gemini_keys_env = os.getenv("GEMINI_API_KEY")
    if gemini_keys_env:
        keys = [k.strip() for k in gemini_keys_env.split(',') if k.strip()]
        if keys:
            genai.configure(api_key=random.choice(keys))
        else:
            print("❌ Error: Valid GEMINI_API_KEY not found.")
            return
    else:
        print("❌ Error: GEMINI_API_KEY environment variable not set.")
        return

    model = genai.GenerativeModel('gemini-2.5-flash')

    # 2. Connect to Sheet
    gc = get_gspread_client()
    SHEET_ID = '1N3_jJkYNCtp1MQXEObtDH9FC_VzPyL2RLBW_MdfvfCM'
    
    try:
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"❌ Error connecting to Sheet: {e}")
        return

    rows = worksheet.get_all_values()
    headers = rows[0]

    try:
        website_col_idx = headers.index('Website')
        type_col_idx = headers.index('Client Type')
        name_col_idx = headers.index('Client Name')
    except ValueError as e:
        print(f"❌ Missing required columns: {e}")
        return

    # 3. Scan & Process
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= website_col_idx:
            continue
            
        website = row[website_col_idx].strip()
        client_name = row[name_col_idx].strip()
        
        # Check if Client Type is already set
        current_type = ""
        if len(row) > type_col_idx:
            current_type = row[type_col_idx].strip()
            
        # TARGET: Website exists AND Client Type is EMPTY
        if website and not current_type:
            print(f"🔍 Analyzing {client_name} ({website})...")
            
            # A. Scrape
            site_text = scrape_website(website)
            
            if site_text is None:
                # Website Dead/Error
                worksheet.update_cell(i, type_col_idx + 1, "Check Manual")
                print(f"⚠️ {client_name}: Website unreachable. Marked 'Check Manual'.")
                continue
                
            if not site_text:
                # Empty content
                worksheet.update_cell(i, type_col_idx + 1, "Check Manual")
                print(f"⚠️ {client_name}: No text found. Marked 'Check Manual'.")
                continue

            # B. Analyze with Gemini
            prompt = f"""Analyze this website text deeply. I need to know the 'Financial Strength' or 'Aukaat' of this client. Look for keywords like 'Global', 'Investors', 'Pvt Ltd', 'Corporate', 'Partners'.

If it looks like a High-Ticket Client (Big Agency, Corporate, Established Brand) -> Return 'VIP'.

If it looks like a Small Business, Local Shop, or Personal Portfolio -> Return 'Normal'.

Return ONLY the single word result.

Text:
{site_text}"""

            try:
                response = model.generate_content(prompt)
                result = response.text.strip()
                
                # Cleanup result just in case
                if "VIP" in result:
                    final_verdict = "VIP"
                else:
                    final_verdict = "Normal" # Default to Normal if unclear
                    
                # C. Update Sheet
                worksheet.update_cell(i, type_col_idx + 1, final_verdict)
                print(f"✅ {client_name}: Classified as {final_verdict}")
                
                # Rate limit protection
                time.sleep(2)
                
            except Exception as e:
                print(f"❌ Gemini Error for {client_name}: {e}")
                
if __name__ == "__main__":
    run_qualifier()
