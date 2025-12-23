from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from contextlib import contextmanager
import csv
import json
import re
from datetime import datetime
import time

START_URL = "https://www.hilton.com/en/locations/pet-friendly/"
OUTPUT_FILE = "hilton_pet_friendly_hotels_selenium.csv"
HEADLESS = False  # Set to True for headless execution

FIELDS = [
    "hotel_code", "hotel_brand", "city", "states", "country",
    "address", "contacts", "parking", "links",
    "is_pet_friendly", "pet_policy", "pet_fee", "weight_limit",
    "service_animals_allowed", "last_updated"
]

def clean(text):
    return text.strip() if text else ""

def extract_money(text):
    if not text:
        return ""
    m = re.search(r"([$R€£]\s?\d+[.,]?\d*)", text)
    return m.group(1) if m else ""

def extract_weight(text):
    if not text:
        return ""
    m = re.search(r"(\d+\s?kg|\d+\s?lb)", text.lower())
    return m.group(1) if m else ""

@contextmanager
def wait_for_page_load(driver, timeout=30):
    """
    Context manager for waiting for page loads after clicks[citation:8]
    This prevents the 'execution context destroyed' error
    """
    old_page = driver.find_element(By.TAG_NAME, 'html')
    yield
    WebDriverWait(driver, timeout).until(
        EC.staleness_of(old_page)
    )

# Setup WebDriver with options
options = webdriver.ChromeOptions()
if HEADLESS:
    options.add_argument('--headless')
options.add_argument('--window-size=1920,1080')
# Disable implicit waits to use explicit waits only[citation:1][citation:3]
options.set_capability('pageLoadStrategy', 'normal')

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)  # Primary explicit wait object

try:
    print("Navigating to page...")
    driver.get(START_URL)
    
    # Wait for page to be fully ready[citation:3]
    wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
    
    print("Waiting for hotel cards to load...")
    # Wait for hotel cards with multiple possible selectors
    hotel_cards = wait.until(
        EC.presence_of_all_elements_located((
            By.CSS_SELECTOR, 
            "ul li button[data-testid^='hotelDetails-'], button[data-testid^='hotelDetails-']"
        ))
    )
    
    total = len(hotel_cards)
    print(f"Found {total} hotel cards")
    
    hotels = []
    
    for i in range(total):
        print(f"\n--- Processing hotel {i+1} of {total} ---")
        
        try:
            # Re-locate cards each iteration to avoid stale references[citation:10]
            current_cards = driver.find_elements(
                By.CSS_SELECTOR, 
                "ul li button[data-testid^='hotelDetails-'], button[data-testid^='hotelDetails-']"
            )
            
            if i >= len(current_cards):
                print(f"  Card index {i} no longer available, skipping...")
                continue
                
            btn = current_cards[i]
            
            # Extract hotel code from data-testid
            testid = btn.get_attribute("data-testid") or ""
            hotel_code_hint = testid.split("hotelDetails-")[-1] if "hotelDetails-" in testid else f"hotel_{i+1}"
            print(f"  Hotel code hint: {hotel_code_hint}")
            
            # Scroll into view using JavaScript[citation:6]
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
            time.sleep(0.5)  # Brief pause after scroll
            
            # Store reference to current page for staleness detection
            old_body = driver.find_element(By.TAG_NAME, 'body')
            
            # Click and wait for navigation/dialog[citation:8]
            btn.click()
            
            # Wait for dialog to appear
            print("  Waiting for dialog...")
            try:
                # Wait for dialog with multiple possible selectors
                dialog = wait.until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        "div[role='dialog'], div[aria-modal='true'], .modal-dialog, .modal-content"
                    ))
                )
                print("  Dialog detected")
            except TimeoutException:
                print("  Dialog not found, attempting to continue...")
                # Check if we're on a new page instead
                try:
                    wait.until(EC.staleness_of(old_body))
                    print("  Page navigation occurred instead of dialog")
                    # Go back and continue
                    driver.back()
                    wait.until(EC.presence_of_all_elements_located((
                        By.CSS_SELECTOR, 
                        "button[data-testid^='hotelDetails-']"
                    )))
                    continue
                except:
                    print("  No navigation detected, skipping hotel...")
                    continue
            
            # Extract data from dialog
            hotel_data = {}
            
            # 1. Get hotel name
            hotel_name = ""
            name_selectors = [
                "div[role='dialog'] h1",
                "div[role='dialog'] h2", 
                "[data-testid*='hotel-name']",
                "[data-testid*='hotelName']",
                ".hotel-name",
                ".property-name"
            ]
            
            for selector in name_selectors:
                try:
                    name_elem = dialog.find_element(By.CSS_SELECTOR, selector)
                    hotel_name = name_elem.text.strip()
                    if hotel_name and len(hotel_name) > 5:
                        print(f"  Found hotel name: {hotel_name[:50]}...")
                        break
                except NoSuchElementException:
                    continue
            
            # 2. Get address
            address = ""
            address_selectors = [
                "div[role='dialog'] address",
                "[data-testid*='address']",
                ".hotel-address",
                ".property-address"
            ]
            
            for selector in address_selectors:
                try:
                    addr_elem = dialog.find_element(By.CSS_SELECTOR, selector)
                    address = addr_elem.text.strip()
                    if address and len(address) > 10:
                        break
                except NoSuchElementException:
                    continue
            
            # 3. Get phone number
            phone = ""
            try:
                dialog_text = dialog.text
                phone_match = re.search(r'(\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})', dialog_text)
                if phone_match:
                    phone = phone_match.group(1)
            except:
                pass
            
            # 4. Look for pet policy
            pet_policy = ""
            try:
                # Get all text and look for pet-related sections
                full_text = dialog.text
                lines = full_text.split('\n')
                pet_lines = []
                
                pet_keywords = ['pet', 'dog', 'cat', 'animal', 'pet-friendly', 
                               'weight limit', 'pet fee', 'pets allowed', 'pet policy']
                
                for line in lines:
                    line_lower = line.lower()
                    if any(keyword in line_lower for keyword in pet_keywords):
                        if len(line.strip()) > 10:  # Avoid very short lines
                            pet_lines.append(line.strip())
                
                if pet_lines:
                    pet_policy = " | ".join(pet_lines[:5])
            except:
                pass
            
            # 5. Determine if pet-friendly
            is_pet_friendly = "false"
            if pet_policy:
                policy_lower = pet_policy.lower()
                if ('pet' in policy_lower or 'dog' in policy_lower or 'cat' in policy_lower):
                    # Check for negative indicators
                    negative_indicators = ['no pet', 'pets not allowed', 'does not allow', 'not accept']
                    if not any(neg in policy_lower for neg in negative_indicators):
                        is_pet_friendly = "true"
            elif 'pet-friendly' in dialog.text.lower():
                is_pet_friendly = "true"
            
            # 6. Try to find links
            links = ""
            try:
                link_elements = dialog.find_elements(By.CSS_SELECTOR, "a[href*='hilton.com']")
                hotel_links = []
                for link_elem in link_elements[:3]:  # Limit to first 3 links
                    href = link_elem.get_attribute("href")
                    if href and 'hilton.com' in href:
                        hotel_links.append(href)
                if hotel_links:
                    links = ", ".join(hotel_links)
            except:
                pass
            
            # Create the record
            record = {
                "hotel_code": f"HILTON-{i+1}_{hotel_code_hint}",
                "hotel_brand": clean(hotel_name),
                "city": "",  # Could extract from address with additional parsing
                "states": "",  # Could extract from address with additional parsing
                "country": "",  # Could extract from address with additional parsing
                "address": clean(address),
                "contacts": clean(phone),
                "parking": "",  # Could look for parking info in dialog
                "links": links,
                "is_pet_friendly": is_pet_friendly,
                "pet_policy": clean(pet_policy),
                "pet_fee": extract_money(pet_policy),
                "weight_limit": extract_weight(pet_policy),
                "service_animals_allowed": "true" if 'service animal' in pet_policy.lower() else "false",
                "last_updated": datetime.utcnow().isoformat()
            }
            
            hotels.append(record)
            print(f"  ✓ Added: {record['hotel_brand'][:40] if record['hotel_brand'] else 'Unnamed hotel'}...")
            
            # Close the dialog
            print("  Closing dialog...")
            close_success = False
            
            # Method 1: Try Escape key
            try:
                from selenium.webdriver.common.keys import Keys
                dialog.send_keys(Keys.ESCAPE)
                time.sleep(1)
                close_success = True
            except:
                pass
            
            # Method 2: Try clicking close button
            if not close_success:
                close_selectors = [
                    "button[aria-label*='Close']",
                    "button:contains('Close')",
                    "[data-testid*='close']",
                    ".close-button",
                    ".modal-close",
                    "button.close"
                ]
                for selector in close_selectors:
                    try:
                        close_btn = dialog.find_element(By.CSS_SELECTOR, selector)
                        close_btn.click()
                        time.sleep(1)
                        close_success = True
                        break
                    except:
                        continue
            
            # Method 3: Click outside dialog
            if not close_success:
                try:
                    # Click at position (100, 100) - outside dialog
                    webdriver.ActionChains(driver).move_by_offset(100, 100).click().perform()
                    time.sleep(1)
                    close_success = True
                except:
                    pass
            
            # Wait for dialog to disappear
            try:
                wait.until(EC.invisibility_of_element(dialog))
            except:
                pass
                
            # Brief pause before next iteration
            time.sleep(1)
            
        except Exception as e:
            print(f"  Error processing hotel {i+1}: {str(e)[:100]}")
            # Try to recover by refreshing the list
            try:
                driver.refresh()
                wait.until(EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR, 
                    "button[data-testid^='hotelDetails-']"
                )))
            except:
                pass
            continue
    
    print(f"\nSuccessfully processed {len(hotels)} hotels")
    
finally:
    driver.quit()

# Write CSV
print(f"\nWriting {len(hotels)} records to {OUTPUT_FILE}")
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(hotels)

print(f"\n✅ DONE — Successfully scraped {len(hotels)} Hilton pet-friendly hotels using Selenium")