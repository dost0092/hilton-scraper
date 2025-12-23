

import time
import re
import csv
import json
import os
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException
)

# ================== CONFIG ==================

START_URL = "https://www.hilton.com/en/locations/pet-friendly/"
OUTPUT_FILE_CSV = "hilton_pet_friendly_hotels.csv"
OUTPUT_FILE_JSON = "hilton_pet_friendly_hotels.json"
STATE_FILE = "hilton_last_state.json"

FIELDS = [
    "hotel_code",
    "hotel_name",
    "address",
    "phone",
    "rating",
    "description",
    "card_price",
    "overview_table_json",
    "pets_json",
    "parking_json",
    "amenities_json",
    "nearby_json",
    "airport_json",
    "is_pet_friendly",
    "last_updated"
]

MAX_SCROLLS = 20
RETRY_LIMIT = 3


# ================== UTILS ==================

def make_options():
    opts = uc.ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    return opts


def extract_money(text):
    if not text:
        return ""
    m = re.search(r"([$€£R$]\s?\d+[.,]?\d*)", text)
    return m.group(1) if m else ""


def extract_weight(text):
    if not text:
        return ""
    m = re.search(r"(\d+\s?(lb|kg))", text.lower())
    return m.group(1) if m else ""


def save_state(page_num):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_page": page_num}, f)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            data = json.load(f)
            return data.get("last_page", 1)
    return 1


def wait_for_popup_content(driver, timeout=40):
    start = time.time()
    while True:
        try:
            popup = driver.find_element(
                By.CSS_SELECTOR,
                "div.relative.flex.size-full.flex-col.overflow-y-auto"
            )
            text_nodes = [e for e in popup.find_elements(By.XPATH, ".//*") if e.text.strip()]
            if len(text_nodes) > 8:
                return popup
        except:
            pass
        if time.time() - start > timeout:
            raise TimeoutException("Popup content did not load")
        time.sleep(0.4)


def safe_find_text(el, xpath):
    try:
        return el.find_element(By.XPATH, xpath).text.strip()
    except:
        return ""


def parse_overview_table(popup):
    data = {}
    try:
        rows = popup.find_elements(By.XPATH, ".//table//tr")
        for row in rows:
            try:
                key = row.find_element(By.XPATH, ".//th").text.strip()
                val = row.find_element(By.XPATH, ".//td").text.strip()
                data[key] = val
            except:
                continue
    except:
        pass
    return data


def parse_amenities(popup):
    amenities = []
    try:
        li_elements = popup.find_elements(
            By.XPATH, ".//ul[contains(@class,'peer flex')]/li"
        )
        for li in li_elements:
            label = safe_find_text(li, ".//span[@data-testid='hotelAmenityLabel']")
            if label:
                amenities.append(label)
    except:
        pass
    return amenities


def parse_nearby(popup):
    data = []
    try:
        items = popup.find_elements(By.XPATH, "//*[@id='tab-panel-nearBy']//li")
        for item in items:
            try:
                place = safe_find_text(item, ".//div[1]/span")
                distance = safe_find_text(item, ".//div[2]")
                if place:
                    data.append({"place": place, "distance": distance})
            except:
                continue
    except:
        pass
    return data


def parse_airport_info(popup):
    data = []
    try:
        # Click "Airport info" button
        btn = popup.find_element(By.XPATH, "//*[@id='airport']")
        btn.click()
        time.sleep(1)
        items = popup.find_elements(By.XPATH, "//*[@id='tab-panel-airport']//li")
        for item in items:
            try:
                name = safe_find_text(item, ".//div[1]/div/span[last()]")
                distance = safe_find_text(item, ".//div[1]/div[2]")
                shuttle = safe_find_text(item, ".//p")
                if name:
                    data.append({"airport": name, "distance": distance, "shuttle": shuttle})
            except:
                continue
    except:
        pass
    return data


def retry_action(action, retries=RETRY_LIMIT, delay=2):
    for i in range(retries):
        try:
            return action()
        except Exception as e:
            print(f"⚠ Retry {i+1}/{retries}: {e}")
            time.sleep(delay)
    raise Exception("Max retries exceeded")


# ================== MAIN SCRAPER ==================

def main():
    start_page = load_state()
    print(f"🔄 Resuming from page {start_page}")

    driver = uc.Chrome(options=make_options(), use_subprocess=True)
    wait = WebDriverWait(driver, 60)
    hotels = []
    page = start_page

    # Prepare files
    if not os.path.exists(OUTPUT_FILE_CSV):
        with open(OUTPUT_FILE_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()

    if not os.path.exists(OUTPUT_FILE_JSON):
        with open(OUTPUT_FILE_JSON, "w", encoding="utf-8") as f:
            json.dump([], f)

    try:
        driver.get(START_URL)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(3)

        # Jump to last saved page
        for p in range(1, start_page):
            try:
                btn_next = driver.find_element(By.ID, "pagination-right")
                driver.execute_script("arguments[0].click();", btn_next)
                time.sleep(3)
            except:
                break

        while True:
            print(f"📄 Scraping page {page}...")

            # Find hotel cards
            buttons = driver.find_elements(By.XPATH, "//button[.//span[normalize-space()='View hotel details']]")

            for i, btn in enumerate(buttons):
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    time.sleep(0.5)
                    try:
                        btn.click()
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].click();", btn)
                        except Exception:
                            time.sleep(0.8)
                            driver.execute_script("arguments[0].click();", btn)

                    popup = retry_action(lambda: wait_for_popup_content(driver))
                    all_text = "\n".join(
                        e.text.strip()
                        for e in popup.find_elements(By.XPATH, ".//*")
                        if e.text.strip()
                    )

                    # Extracting Details
                    name = safe_find_text(popup, ".//h1 | .//h2") or "UNKNOWN"
                    rating = safe_find_text(popup, ".//p[contains(text(),'Rating')]")
                    description = safe_find_text(popup, ".//div/p[@class='inline text-start md:block']")
                    address = safe_find_text(driver, ".//span[@data-testid='locationMarker']")
                    price = safe_find_text(driver, ".//span[@data-testid='rateItem']")

                    overview = parse_overview_table(popup)
                    amenities = parse_amenities(popup)
                    nearby = parse_nearby(popup)
                    airport = parse_airport_info(popup)

                    pets_json = {}
                    parking_json = {}
                    for k, v in overview.items():
                        if "pet" in k.lower():
                            pets_json[k] = v
                        if "park" in k.lower():
                            parking_json[k] = v

                    hotel_data = {
                        "hotel_code": f"HILTON-{page}-{i+1}",
                        "hotel_name": name,
                        "address": address,
                        "phone": re.search(r'(\+?\d[\d\s().-]{7,}\d)', all_text).group(1)
                                   if re.search(r'(\+?\d[\d\s().-]{7,}\d)', all_text) else "",
                        "rating": rating,
                        "description": description,
                        "card_price": price,
                        "overview_table_json": json.dumps(overview, ensure_ascii=False),
                        "pets_json": json.dumps(pets_json, ensure_ascii=False),
                        "parking_json": json.dumps(parking_json, ensure_ascii=False),
                        "amenities_json": json.dumps(amenities, ensure_ascii=False),
                        "nearby_json": json.dumps(nearby, ensure_ascii=False),
                        "airport_json": json.dumps(airport, ensure_ascii=False),
                        "is_pet_friendly": "true" if "pet" in all_text.lower() else "false",
                        "last_updated": datetime.utcnow().isoformat()
                    }

                    hotels.append(hotel_data)
                    print(f"✅ Extracted: {hotel_data['hotel_name']}")

                    # Save incrementally
                    with open(OUTPUT_FILE_CSV, "a", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=FIELDS)
                        writer.writerow(hotel_data)

                    # JSON incremental save
                    with open(OUTPUT_FILE_JSON, "r+", encoding="utf-8") as jf:
                        data = json.load(jf)
                        data.append(hotel_data)
                        jf.seek(0)
                        json.dump(data, jf, ensure_ascii=False, indent=2)

                    popup.send_keys(Keys.ESCAPE)
                    time.sleep(1)

                except Exception:
                    try:
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    except:
                        pass
                    continue

            # Save state after each page
            save_state(page)

            # Restart browser every 5 pages
            if page % 2 == 0:
                print(f"🔄 Restarting browser after {page} pages...")
                driver.quit()
                driver = uc.Chrome(options=make_options(), use_subprocess=True)
                wait = WebDriverWait(driver, 60)
                driver.get(START_URL)
                for p in range(1, page):
                    try:
                        btn_next = driver.find_element(By.ID, "pagination-right")
                        driver.execute_script("arguments[0].click();", btn_next)
                        time.sleep(3)
                    except:
                        break

            # Pagination
            try:
                btn_next = driver.find_element(By.ID, "pagination-right")
                if "disabled" in btn_next.get_attribute("class"):
                    print("✅ No more pages.")
                    break
                print("➡️ Moving to next page...")
                driver.execute_script("arguments[0].click();", btn_next)
                page += 1
                time.sleep(4)
            except NoSuchElementException:
                print("✅ All pages scraped.")
                break

    finally:
        driver.quit()
        print(f"\n🎉 DONE — Scraped {len(hotels)} hotels total.")
        save_state(page)


if __name__ == "__main__":
    main()
