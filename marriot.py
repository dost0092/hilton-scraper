from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import csv
import os
import random
import time
from datetime import datetime

SEARCH_URL = "https://www.marriott.com/search"
OUTPUT_CITY_LINKS = "marriott_city_links.csv"
OUTPUT_HOTELS = "marriott_hotels.csv"
PROFILE_DIR = "playwright-profile-marriott"
HEADLESS = True

def human_wait(a=0.8, b=1.8):
    time.sleep(random.uniform(a, b))

def timestamp():
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")

def accept_consent_if_present(page):
    selectors = [
        "button#onetrust-accept-btn-handler",
        "button:has-text('Accept All')",
        "button:has-text('I Agree')",
        "button:has-text('Accept Cookies')",
        "button:has-text('Got it')",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=800):
                btn.click()
                human_wait(0.5, 1.0)
                break
        except Exception:
            pass

def is_blocked(page):
    try:
        url = page.url
    except Exception:
        url = ""
    body_text = ""
    try:
        body_text = page.text_content("body") or ""
    except Exception:
        pass
    if not body_text:
        try:
            body_text = page.content()
        except Exception:
            pass
    signals = [
        "Access Denied",
        "errors.edgesuite.net",
        "An error has occurred",
        "Something went wrong with the previous request",
        "Reference #",
        "Akamai",
    ]
    return any(s in (body_text or "") for s in signals) or ("errors.edgesuite.net" in (url or ""))

def debug_dump(page, prefix="debug"):
    ts = timestamp()
    try:
        page.screenshot(path=f"{prefix}_{ts}.png", full_page=True)
    except Exception:
        pass
    try:
        html = page.content()
        with open(f"{prefix}_{ts}.html", "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        pass

def safe_inner_text(locator, timeout=1200):
    try:
        return locator.inner_text(timeout=timeout).strip()
    except Exception:
        return ""

def safe_get_attribute(locator, name, timeout=1200):
    try:
        return locator.get_attribute(name, timeout=timeout)
    except Exception:
        return None

def normalize_url(href: str):
    if not href:
        return ""
    href = href.strip()
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://www.marriott.com" + href
    return "https://www.marriott.com/" + href

def launch_browser(p):
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    context = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=HEADLESS,
        viewport={"width": 1366, "height": 768},
        user_agent=ua,
        locale="en-US",
        timezone_id="America/New_York",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
        ],
    )
    page = context.new_page()
    page.set_default_timeout(60000)
    try:
        page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Upgrade-Insecure-Requests": "1",
        })
    except Exception:
        pass
    return context, page

def collect_city_links(page):
    page.goto(SEARCH_URL, wait_until="domcontentloaded")
    human_wait()
    accept_consent_if_present(page)
    human_wait()

    # Light human-like actions to allow cookies, reduce bot suspicion
    try:
        page.mouse.wheel(0, 1200)
        human_wait(0.6, 1.2)
        page.mouse.wheel(0, -800)
    except Exception:
        pass

    # Wait for city links container
    page.wait_for_selector("div.panel-body ul.panel-links li.links-list a.links")

    links = page.locator("div.panel-body ul.panel-links li.links-list a.links")
    count = links.count()
    city_data = []
    for i in range(count):
        link = links.nth(i)
        name = safe_inner_text(link)
        href = safe_get_attribute(link, "href") or ""
        full_url = normalize_url(href)
        if name and full_url:
            city_data.append({"name": name, "url": full_url})

    with open(OUTPUT_CITY_LINKS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "url"])
        writer.writeheader()
        writer.writerows(city_data)

    print(f"Saved {len(city_data)} city links to {OUTPUT_CITY_LINKS}")
    return city_data

def wait_for_hotel_cards(page):
    # Try multiple selectors; DOM may vary across city pages
    candidates = [
        "div.property-card__details-container",
        "article.property-card",
        "[data-test='property-card']",
        "div[data-testid='property-card']",
        "li.property-card",
    ]
    for sel in candidates:
        try:
            page.wait_for_selector(sel, timeout=15000, state="attached")
            return sel
        except PWTimeoutError:
            continue
        except Exception:
            continue
    return None

def extract_hotels_from_page(page, cards_selector):
    hotels = []
    cards = page.locator(cards_selector)
    cnt = cards.count()
    for i in range(cnt):
        card = cards.nth(i)

        def text_or_blank(sel_list):
            for s in sel_list:
                t = safe_inner_text(card.locator(s))
                if t:
                    return t
            return ""

        def href_or_blank(sel_list):
            for s in sel_list:
                href = safe_get_attribute(card.locator(s), "href")
                if href:
                    return normalize_url(href)
            return ""

        hotel_name = text_or_blank([
            "h2.property-card__title a",
            "a.property-card__title",
            "h2 a",
            "h3 a",
            "a[aria-label*='View Hotel']",
        ])

        view_details = href_or_blank([
            "a.property-card__tertiary-link",
            "a:has-text('View Details')",
            "a:has-text('View Hotel')",
            "a[href*='/hotels/']",
            "a[href*='/en-us/hotels/']",
        ])

        review_score = text_or_blank([
            "span.star-number-container",
            "[data-test='review-score']",
            "[data-testid='review-score']",
        ])

        review_count = text_or_blank([
            "span.review-number-container",
            "[data-test='review-count']",
            "[data-testid='review-count']",
        ])

        distance = text_or_blank([
            "div.distance-value",
            "[data-test='distance']",
            "[data-testid='distance']",
        ])

        description = text_or_blank([
            "p.property-card__details-container_desc",
            "[data-test='card-description']",
            "p",
        ])

        hotels.append({
            "hotel_name": hotel_name,
            "view_details": view_details,
            "review_score": review_score,
            "review_count": review_count,
            "distance": distance,
            "description": description
        })
    return hotels

def paginate_next(page):
    # Try multiple next selectors
    candidates = [
        "a[aria-label*='Next']",
        "a[rel='next']",
        "button[aria-label*='Next']",
        "a.pagination-next",
        "li.pagination-next a",
        "a:has(span.pagination-next-link)",
    ]
    for sel in candidates:
        loc = page.locator(sel).first
        try:
            if loc.count() and loc.is_enabled() and loc.is_visible():
                loc.click()
                page.wait_for_load_state("networkidle", timeout=60000)
                human_wait()
                return True
        except Exception:
            continue
    return False

def scrape_first_city(page, city_url):
    hotels_all = []

    # Navigate and prepare
    page.goto(city_url, wait_until="domcontentloaded")
    human_wait()
    accept_consent_if_present(page)
    try:
        page.wait_for_load_state("networkidle", timeout=60000)
    except Exception:
        pass

    # Early block detection
    if is_blocked(page):
        print(f"Blocked/interstitial detected at {page.url}")
        debug_dump(page, prefix="blocked")
        return hotels_all

    # Try to detect hotel cards
    cards_selector = wait_for_hotel_cards(page)
    if not cards_selector:
        print("Hotel cards not found; dumping debug artifacts.")
        debug_dump(page, prefix="no_cards")
        return hotels_all

    # Loop pages
    seen_pages = 0
    while True:
        seen_pages += 1
        # Another block check each page
        if is_blocked(page):
            print(f"Blocked on page {seen_pages} of results: {page.url}")
            debug_dump(page, prefix="blocked_paged")
            break

        hotels_page = extract_hotels_from_page(page, cards_selector)
        hotels_all.extend(hotels_page)
        print(f"Collected {len(hotels_page)} hotels on page {seen_pages} (total {len(hotels_all)}).")
        human_wait(1.0, 2.2)

        # Try next page
        moved = paginate_next(page)
        if not moved:
            break

        # Re-accept consent if it appears again
        accept_consent_if_present(page)

        # Re-detect selector if DOM changes
        maybe_new_selector = wait_for_hotel_cards(page)
        if maybe_new_selector:
            cards_selector = maybe_new_selector

    return hotels_all

def main():
    os.makedirs(PROFILE_DIR, exist_ok=True)

    with sync_playwright() as p:
        context, page = launch_browser(p)

        try:
            # Step 1: City links
            cities = collect_city_links(page)
            if not cities:
                print("No city links found; aborting.")
                return

            # Step 2: Scrape first city
            city_url = cities[0]["url"]
            print(f"Scraping first city: {cities[0]['name']} -> {city_url}")
            hotels = scrape_first_city(page, city_url)

            # Save hotels CSV
            with open(OUTPUT_HOTELS, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "hotel_name", "view_details", "review_score",
                    "review_count", "distance", "description"
                ])
                writer.writeheader()
                writer.writerows(hotels)

            print(f"Saved {len(hotels)} hotels to {OUTPUT_HOTELS}")

        finally:
            try:
                context.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()