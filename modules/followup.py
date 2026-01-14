import os
import time
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from modules.services import get_gspread_client

def init_driver():
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless") # Commented out for visual verification if needed
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def login_instagram(driver, username, password):
    driver.get("https://www.instagram.com/accounts/login/")
    time.sleep(4)
    try:
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
        time.sleep(5)
    except Exception as e:
        print(f"Login failed: {e}")

def like_posts(driver, profile_url, num=3):
    driver.get(profile_url)
    time.sleep(3)
    
    # Find posts (links with /p/)
    links = driver.find_elements(By.TAG_NAME, "a")
    post_links = [l.get_attribute('href') for l in links if '/p/' in l.get_attribute('href')]
    
    # Unique and remove duplicates
    post_links = list(set(post_links))[:num]
    
    for link in post_links:
        driver.get(link)
        time.sleep(2)
        try:
            # Try finding the like button (svg with aria-label='Like')
            like_btn_container = driver.find_element(By.XPATH, "//span[contains(@class, 'xp7jhwk')]") # Very brittle, fallback to aria-label
            # Better strategy: Find svg with aria-label="Like"
            like_svg = driver.find_element(By.CSS_SELECTOR, "svg[aria-label='Like']")
            parent_btn = like_svg.find_element(By.XPATH, "./../..")
            parent_btn.click()
            print(f"Liked post {link}")
        except Exception:
            # If fail, maybe already liked ('Unlike')
            print(f"Skipping post {link} - likely already liked or selector failed")
        time.sleep(1)

def send_dm(driver, profile_url, message):
    driver.get(profile_url)
    time.sleep(3)
    try:
        # Click Message button
        msg_btn = driver.find_element(By.XPATH, "//div[text()='Message']")
        msg_btn.click()
        time.sleep(4)
        
        # Handle "Not Now" for notifications popup if it appears
        if "Turn on Notifications" in driver.page_source:
             driver.find_element(By.XPATH, "//button[text()='Not Now']").click()
             time.sleep(1)

        # Type message
        txt_box = driver.find_element(By.TAG_NAME, "textarea") # Often textarea
        if not txt_box:
             txt_box = driver.find_element(By.CSS_SELECTOR, "[contenteditable='true']")
             
        txt_box.send_keys(message)
        txt_box.send_keys(Keys.RETURN)
        print(f"Sent DM to {profile_url}")
    except Exception as e:
        print(f"Failed to DM {profile_url}: {e}")

def run_followup():
    print("Running Followup...")
    gc = get_gspread_client()
    SHEET_ID = '1N3_jJkYNCtp1MQXEObtDH9FC_VzPyL2RLBW_MdfvfCM'
    try:
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
    except Exception:
        return

    rows = worksheet.get_all_values()
    headers = rows[0]
    
    try:
        date_col_idx = headers.index('Email Sending Date')
        status_col_idx = headers.index('Status')
        ig_link_idx = headers.index('Instagram Link') # Assuming this exists or using Portfolio Link? 
        # Requirement said: "go to Instagram link". I'll assume explicit column.
        # If not, maybe parse Portfolio? I'll assume "Instagram Link" for now.
    except ValueError:
        # Fallback if "Instagram Link" missing, try to find it
        try:
             ig_link_idx = headers.index('Instagram')
        except ValueError:
             print("Instagram Link column not found.")
             return

    target_rows = []
    
    today = datetime.date.today()
    three_days_ago = (today - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    
    for i, row in enumerate(rows[1:], start=2):
        date_val = row[date_col_idx]
        status = row[status_col_idx]
        ig_link = row[ig_link_idx] if len(row) > ig_link_idx else ""
        
        if date_val == three_days_ago and status == "Pending" and ig_link:
             target_rows.append((i, ig_link))
             
    if not target_rows:
        print("No followups due.")
        return

    driver = init_driver()
    try:
        login_instagram(driver, os.getenv("IG_USER"), os.getenv("IG_PASS"))
        
        for idx, ig_link in target_rows:
            like_posts(driver, ig_link)
            send_dm(driver, ig_link, "Hi! Just following up on my previous email. Let me know if you are interested!")
            # Update status? Maybe to "Followed Up"?
            worksheet.update_cell(idx, status_col_idx + 1, "Followed Up")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    run_followup()
