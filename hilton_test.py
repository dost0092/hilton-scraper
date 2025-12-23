import time
import re
import csv
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException
)

# ================== CONFIG ==================

START_URL = "https://www.hilton.com/en/locations/pet-friendly/"
OUTPUT_FILE = "hilton_pet_friendly_hotels.csv"

FIELDS = [
    "hotel_code",
    "hotel_name",
    "address",
    "phone",
    "is_pet_friendly",
    "pet_policy_text",
    "pet_fee",
    "weight_limit",
    "last_updated"
]

MAX_SCROLLS = 40

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
    m = re.search(r"([$€£]\s?\d+[.,]?\d*)", text)
    return m.group(1) if m else ""

def extract_weight(text):
    if not text:
        return ""
    m = re.search(r"(\d+\s?(lb|kg))", text.lower())
    return m.group(1) if m else ""

def wait_for_popup_content(driver, timeout=30):
    start = time.time()
    while True:
        popup = driver.find_element(
            By.CSS_SELECTOR,
            "div.relative.flex.size-full.flex-col.overflow-y-auto"
        )

        text_nodes = [
            e for e in popup.find_elements(By.XPATH, ".//*")
            if e.text.strip()
        ]

        if len(text_nodes) > 8:
            return popup

        if time.time() - start > timeout:
            raise TimeoutException("Popup content did not load")

        time.sleep(0.4)

# ================== MAIN ==================

def main():
    driver = uc.Chrome(options=make_options(), use_subprocess=True)
    wait = WebDriverWait(driver, 60)

    hotels = []
    processed = set()
    scroll_count = 0

    try:
        print("🔄 Opening Hilton page...")
        driver.get(START_URL)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(2)

        while True:
            buttons = driver.find_elements(
                By.XPATH,
                "//button[.//span[normalize-space()='View hotel details']]"
            )

            target = None

            for btn in buttons:
                try:
                    test_id = btn.get_attribute("data-testid") or btn.text
                    if test_id not in processed:
                        target = btn
                        break
                except StaleElementReferenceException:
                    continue

            # 🔚 No new button found → scroll or stop
            if not target:
                if scroll_count >= MAX_SCROLLS:
                    print("✅ All hotels processed")
                    break

                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.9)")
                scroll_count += 1
                time.sleep(2)
                continue

            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", target
                )
                time.sleep(0.4)

                # JS CLICK — CRITICAL
                driver.execute_script("arguments[0].click();", target)

                popup = wait_for_popup_content(driver)

                # ---------- EXTRACT ----------
                all_text = "\n".join(
                    e.text.strip()
                    for e in popup.find_elements(By.XPATH, ".//*")
                    if e.text.strip()
                )

                try:
                    name = popup.find_element(By.XPATH, ".//h1 | .//h2").text
                except:
                    name = "UNKNOWN"

                try:
                    phone_match = re.search(
                        r'(\+?\d[\d\s().-]{7,}\d)', all_text
                    )
                    phone = phone_match.group(1) if phone_match else ""
                except:
                    phone = ""

                test_id = target.get_attribute("data-testid") or name
                processed.add(test_id)

                hotels.append({
                    "hotel_code": f"HILTON-{len(hotels)+1}",
                    "hotel_name": name,
                    "address": "",
                    "phone": phone,
                    "is_pet_friendly": "true" if "pet" in all_text.lower() else "false",
                    "pet_policy_text": all_text,
                    "pet_fee": extract_money(all_text),
                    "weight_limit": extract_weight(all_text),
                    "last_updated": datetime.utcnow().isoformat()
                })

                print(f"✅ {len(hotels)}. Extracted: {name}")

                # ---------- CLOSE ----------
                popup.send_keys(Keys.ESCAPE)
                time.sleep(1)

            except Exception as e:
                print("⚠ Error:", e)
                try:
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                except:
                    pass
                continue

    finally:
        driver.quit()

    # ================== SAVE ==================

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(hotels)

    print(f"\n🎉 DONE — Saved {len(hotels)} hotels → {OUTPUT_FILE}")

# ================== RUN ==================

if __name__ == "__main__":
    main()
