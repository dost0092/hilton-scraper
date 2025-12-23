import time
import json
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def make_options():
    opts = uc.ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    return opts

def main():
    driver = uc.Chrome(options=make_options(), use_subprocess=True)
    wait = WebDriverWait(driver, 60)

    try:
        driver.get("https://www.hilton.com/en/locations/pet-friendly/")
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(3)

        # Click the first hotel details button
        view_btn = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[normalize-space()='View hotel details']]")
            )
        )
        driver.execute_script("arguments[0].click();", view_btn)

        # Wait until popup has real content
        max_wait = 20
        start = time.time()
        while True:
            try:
                popup = driver.find_element(
                    By.CSS_SELECTOR,
                    "div.relative.flex.size-full.flex-col.overflow-y-auto.lg\\:h-auto.lg\\:flex-row"
                )
                # Count only elements with text
                text_elements = [e for e in popup.find_elements(By.XPATH, ".//*") if e.text.strip()]
                if len(text_elements) > 5:
                    break
            except:
                pass
            if time.time() - start > max_wait:
                raise TimeoutError("Popup content did not load in time")
            time.sleep(0.5)

        # Extract info (example: name + all text)
        data = {}
        try:
            data['name'] = popup.find_element(By.XPATH, ".//h1 | .//h2").text
        except:
            data['name'] = None

        # Merge all text content
        data['all_text'] = "\n".join([e.text.strip() for e in popup.find_elements(By.XPATH, ".//*") if e.text.strip()])

        # Save JSON
        with open("hilton_hotel.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print("✅ Hotel popup extracted → hilton_hotel.json")

    except Exception as e:
        print("❌ Error:", e)

    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
