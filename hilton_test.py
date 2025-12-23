# import time
# import re
# import csv
# from datetime import datetime

# import undetected_chromedriver as uc
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import (
#     TimeoutException,
#     StaleElementReferenceException
# )

# # ================== CONFIG ==================

# START_URL = "https://www.hilton.com/en/locations/pet-friendly/"
# OUTPUT_FILE = "hilton_pet_friendly_hotels.csv"

# FIELDS = [
#     "hotel_code",
#     "hotel_name",
#     "address",
#     "phone",
#     "is_pet_friendly",
#     "pet_policy_text",
#     "pet_fee",
#     "weight_limit",
#     "last_updated"
# ]

# MAX_SCROLLS = 40

# # ================== UTILS ==================

# def make_options():
#     opts = uc.ChromeOptions()
#     opts.add_argument("--start-maximized")
#     opts.add_argument("--disable-blink-features=AutomationControlled")
#     opts.add_argument("--no-sandbox")
#     opts.add_argument("--disable-dev-shm-usage")
#     return opts

# def extract_money(text):
#     if not text:
#         return ""
#     m = re.search(r"([$€£]\s?\d+[.,]?\d*)", text)
#     return m.group(1) if m else ""

# def extract_weight(text):
#     if not text:
#         return ""
#     m = re.search(r"(\d+\s?(lb|kg))", text.lower())
#     return m.group(1) if m else ""

# def wait_for_popup_content(driver, timeout=30):
#     start = time.time()
#     while True:
#         popup = driver.find_element(
#             By.CSS_SELECTOR,
#             "div.relative.flex.size-full.flex-col.overflow-y-auto"
#         )

#         text_nodes = [
#             e for e in popup.find_elements(By.XPATH, ".//*")
#             if e.text.strip()
#         ]

#         if len(text_nodes) > 8:
#             return popup

#         if time.time() - start > timeout:
#             raise TimeoutException("Popup content did not load")

#         time.sleep(0.4)

# # ================== MAIN ==================

# def main():
#     driver = uc.Chrome(options=make_options(), use_subprocess=True)
#     wait = WebDriverWait(driver, 60)

#     hotels = []
#     processed = set()
#     scroll_count = 0

#     try:
#         print("🔄 Opening Hilton page...")
#         driver.get(START_URL)
#         wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
#         time.sleep(2)

#         while True:
#             buttons = driver.find_elements(
#                 By.XPATH,
#                 "//button[.//span[normalize-space()='View hotel details']]"
#             )

#             target = None

#             for btn in buttons:
#                 try:
#                     test_id = btn.get_attribute("data-testid") or btn.text
#                     if test_id not in processed:
#                         target = btn
#                         break
#                 except StaleElementReferenceException:
#                     continue

#             # 🔚 No new button found → scroll or stop
#             if not target:
#                 if scroll_count >= MAX_SCROLLS:
#                     print("✅ All hotels processed")
#                     break

#                 driver.execute_script("window.scrollBy(0, window.innerHeight * 0.9)")
#                 scroll_count += 1
#                 time.sleep(2)
#                 continue

#             try:
#                 driver.execute_script(
#                     "arguments[0].scrollIntoView({block:'center'});", target
#                 )
#                 time.sleep(0.4)

#                 # JS CLICK — CRITICAL
#                 driver.execute_script("arguments[0].click();", target)

#                 popup = wait_for_popup_content(driver)

#                 # ---------- EXTRACT ----------
#                 all_text = "\n".join(
#                     e.text.strip()
#                     for e in popup.find_elements(By.XPATH, ".//*")
#                     if e.text.strip()
#                 )

#                 try:
#                     name = popup.find_element(By.XPATH, ".//h1 | .//h2").text
#                 except:
#                     name = "UNKNOWN"

#                 try:
#                     phone_match = re.search(
#                         r'(\+?\d[\d\s().-]{7,}\d)', all_text
#                     )
#                     phone = phone_match.group(1) if phone_match else ""
#                 except:
#                     phone = ""

#                 test_id = target.get_attribute("data-testid") or name
#                 processed.add(test_id)

#                 hotels.append({
#                     "hotel_code": f"HILTON-{len(hotels)+1}",
#                     "hotel_name": name,
#                     "address": "",
#                     "phone": phone,
#                     "is_pet_friendly": "true" if "pet" in all_text.lower() else "false",
#                     "pet_policy_text": all_text,
#                     "pet_fee": extract_money(all_text),
#                     "weight_limit": extract_weight(all_text),
#                     "last_updated": datetime.utcnow().isoformat()
#                 })

#                 print(f"✅ {len(hotels)}. Extracted: {name}")

#                 # ---------- CLOSE ----------
#                 popup.send_keys(Keys.ESCAPE)
#                 time.sleep(1)

#             except Exception as e:
#                 print("⚠ Error:", e)
#                 try:
#                     driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
#                 except:
#                     pass
#                 continue

#     finally:
#         driver.quit()

#     # ================== SAVE ==================

#     with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
#         writer = csv.DictWriter(f, fieldnames=FIELDS)
#         writer.writeheader()
#         writer.writerows(hotels)

#     print(f"\n🎉 DONE — Saved {len(hotels)} hotels → {OUTPUT_FILE}")

# # ================== RUN ==================

# if __name__ == "__main__":
#     main()





# import time, re, csv, json, os
# from datetime import datetime
# import undetected_chromedriver as uc

# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

# START_URL = "https://www.hilton.com/en/locations/pet-friendly/"
# OUTPUT_FILE = "hilton_pet_friendly_hotels.csv"
# PROGRESS_FILE = "progress.json"

# FIELDS = [
#     "hotel_code", "hotel_name", "address", "phone", "rating",
#     "description", "card_price",
#     "overview_table_json", "pets_json", "parking_json",
#     "amenities_json", "nearby_json", "airport_json",
#     "is_pet_friendly", "last_updated"
# ]

# MAX_SCROLLS = 40


# # ===================== UTILS =====================

# def load_progress():
#     return json.load(open(PROGRESS_FILE)) if os.path.exists(PROGRESS_FILE) else {"page": 1}

# def save_progress(page):
#     json.dump({"page": page}, open(PROGRESS_FILE, "w"))

# def make_driver():
#     opts = uc.ChromeOptions()
#     opts.add_argument("--start-maximized")
#     opts.add_argument("--disable-blink-features=AutomationControlled")
#     return uc.Chrome(options=opts, use_subprocess=True)

# def safe_text(el):
#     try: return el.text.strip()
#     except: return ""

# def extract_price(text):
#     m = re.search(r"[€$£R$]\s?\d+[.,]?\d*", text)
#     return m.group(0) if m else ""

# def wait_modal(driver, timeout=30):
#     WebDriverWait(driver, timeout).until(
#         EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='dialog']"))
#     )
#     return driver.find_element(By.CSS_SELECTOR, "div[role='dialog']")

# # ===================== SCRAPER =====================

# class HiltonScraper:

#     def __init__(self):
#         self.driver = make_driver()
#         self.wait = WebDriverWait(self.driver, 60)
#         self.hotels = []
#         self.progress = load_progress()

#     # ---------- CARD DATA ----------
#     def get_card_data(self, card):
#         price = extract_price(card.text)
#         try:
#             address = card.find_element(By.CSS_SELECTOR, "[data-testid='locationMarker']").text
#         except:
#             address = ""
#         return price, address

#     # ---------- OVERVIEW TABLE ----------
#     def extract_overview_table(self, modal):
#         data = {}
#         for row in modal.find_elements(By.CSS_SELECTOR, "table tbody tr"):
#             k = safe_text(row.find_element(By.TAG_NAME, "th"))
#             v = safe_text(row.find_element(By.TAG_NAME, "td"))
#             data[k] = v
#         return data

#     # ---------- AMENITIES ----------
#     def extract_amenities(self, modal):
#         amenities = []
#         for li in modal.find_elements(By.CSS_SELECTOR, "li [data-testid^='hotelAmenity']"):
#             label = safe_text(li.find_element(By.CSS_SELECTOR, "[data-testid='hotelAmenityLabel']"))
#             if label:
#                 amenities.append(label)
#         return amenities

#     # ---------- DESCRIPTION + RATING ----------
#     def extract_basic_info(self, modal):
#         desc, rating = "", ""
#         try:
#             desc = modal.find_element(By.XPATH, ".//p[contains(@class,'text-start')]").text
#         except: pass
#         try:
#             rating = modal.find_element(By.XPATH, ".//p[contains(text(),'Rating')]").text
#         except: pass
#         return desc, rating

#     # ---------- TABS ----------
#     def extract_tab_list(self, tab_button_id, panel_id):
#         self.driver.find_element(By.ID, tab_button_id).click()
#         time.sleep(1)

#         items = []
#         for li in self.driver.find_elements(By.CSS_SELECTOR, f"#{panel_id} li"):
#             parts = li.text.split("\n")
#             if len(parts) >= 2:
#                 items.append({"name": parts[0], "distance": parts[1]})
#         return items

#     # ---------- MAIN LOOP ----------
#     def run(self):
#         self.driver.get(START_URL)
#         time.sleep(3)

#         current_page = self.progress["page"]

#         for _ in range(current_page - 1):
#             self.driver.find_element(By.ID, "pagination-right").click()
#             time.sleep(3)

#         while True:
#             cards = self.driver.find_elements(By.XPATH, "//li[contains(@class,'hotel-card')]")

#             for card in cards:
#                 try:
#                     price, address = self.get_card_data(card)
#                     btn = card.find_element(By.XPATH, ".//span[text()='View hotel details']/ancestor::button")
#                     self.driver.execute_script("arguments[0].click();", btn)

#                     modal = wait_modal(self.driver)

#                     name = safe_text(modal.find_element(By.XPATH, ".//h1 | .//h2"))
#                     desc, rating = self.extract_basic_info(modal)
#                     overview = self.extract_overview_table(modal)
#                     amenities = self.extract_amenities(modal)

#                     nearby = self.extract_tab_list("nearBy", "tab-panel-nearBy")
#                     airport = self.extract_tab_list("airport", "tab-panel-airport")

#                     pets = overview.get("Pets", "")
#                     parking = overview.get("Parking", "")

#                     self.hotels.append({
#                         "hotel_code": f"HILTON-{len(self.hotels)+1}",
#                         "hotel_name": name,
#                         "address": address,
#                         "phone": "",
#                         "rating": rating,
#                         "description": desc,
#                         "card_price": price,
#                         "overview_table_json": json.dumps(overview),
#                         "pets_json": pets,
#                         "parking_json": parking,
#                         "amenities_json": json.dumps(amenities),
#                         "nearby_json": json.dumps(nearby),
#                         "airport_json": json.dumps(airport),
#                         "is_pet_friendly": "pet" in pets.lower(),
#                         "last_updated": datetime.utcnow().isoformat()
#                     })

#                     modal.send_keys(Keys.ESCAPE)
#                     time.sleep(1)

#                 except Exception as e:
#                     print("⚠ Error:", e)
#                     self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
#                     continue

#             save_progress(current_page)
#             self.save_csv()

#             try:
#                 self.driver.find_element(By.ID, "pagination-right").click()
#                 current_page += 1
#                 time.sleep(4)
#             except:
#                 break

#         self.driver.quit()

#     def save_csv(self):
#         with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
#             writer = csv.DictWriter(f, fieldnames=FIELDS)
#             writer.writeheader()
#             writer.writerows(self.hotels)


# # ===================== RUN =====================
# if __name__ == "__main__":
#     HiltonScraper().run()
