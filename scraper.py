import json
import random
import re
import time

from playwright.sync_api import sync_playwright
from playwright_stealth.stealth import Stealth

SHOW_BROWSER = False
MAX_RESULTS = 100


def _safe_text(locator):
    if locator.count() == 0:
        return None
    text = locator.first.text_content()
    return text.strip() if text else None


def _parse_rating_and_reviews(text):
    if not text:
        return None, None
    rating_match = re.search(r"([0-9]+[\.,]?[0-9]*)\s*(stars?|étoiles?|etoiles?)", text, re.IGNORECASE)
    reviews_match = re.search(r"([0-9][0-9,]*)\s*(reviews?|avis)", text, re.IGNORECASE)

    if not rating_match and not reviews_match:
        inline_match = re.search(r"([0-9]+\.?[0-9]*)\s*\(([^)]+)\)", text)
        if inline_match:
            rating_match = inline_match
            reviews_match = re.search(r"([0-9][0-9,]*)", inline_match.group(2))

    rating = float(rating_match.group(1).replace(",", ".")) if rating_match else None
    reviews = int(reviews_match.group(1).replace(",", "")) if reviews_match else None
    return rating, reviews


def _clean_phone(text):
    if not text:
        return None
    cleaned = re.sub(r"[^0-9+]+", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def scrape_google_maps(
    query,
    location,
    log_callback,
    max_results=MAX_RESULTS,
    show_browser=SHOW_BROWSER,
    stop_event=None,
    deep_search=False,
):
    leads = []
    seen = set()

    def log(message):
        if log_callback:
            log_callback(message)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not show_browser,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(locale="en-US")
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        log("Opening Google Maps...")
        page.goto("https://www.google.com/maps", wait_until="domcontentloaded", timeout=60000)

        for text in ["Accept all", "I agree", "Accept"]:
            button = page.locator(f"button:has-text('{text}')")
            if button.count() > 0:
                button.first.click()
                break

        search_box = None
        for selector in ["input#searchboxinput", "input[aria-label*='Search']", "input[placeholder*='Search']"]:
            candidate = page.locator(selector)
            try:
                candidate.wait_for(state="visible", timeout=15000)
                search_box = candidate
                break
            except Exception:
                continue

        if not search_box:
            log("Search box not found. Falling back to direct search URL...")
            search_query = f"{query} in {location}".replace(" ", "+")
            page.goto(
                f"https://www.google.com/maps/search/{search_query}",
                wait_until="domcontentloaded",
                timeout=60000,
            )
        else:
            search_box.fill(f"{query} in {location}")
            page.keyboard.press("Enter")

        feed = page.locator("div[role='feed']")
        try:
            feed.wait_for(state="visible", timeout=15000)
        except Exception:
            log("No results feed found.")
            browser.close()
            return leads

        current_index = 0
        last_count = 0
        stagnant_rounds = 0

        while True:
            if stop_event and stop_event.is_set():
                log("Scrape stopped by user.")
                break
            items = feed.locator("div[role='article']")
            count = items.count()

            while current_index < min(count, max_results):
                if stop_event and stop_event.is_set():
                    log("Scrape stopped by user.")
                    break

                item = items.nth(current_index)
                try:
                    item.scroll_into_view_if_needed()
                    item.click()
                    page.wait_for_timeout(500)

                    name = _safe_text(page.locator("h1.DUwDvf"))
                    if not name:
                        name = _safe_text(page.locator("h1[aria-level='1']"))
                    if not name:
                        card_text = item.inner_text().splitlines()
                        name = card_text[0].strip() if card_text else None

                    rating_label = None
                    card_rating = item.locator(
                        "[aria-label*='stars'], [aria-label*='reviews'], "
                        "[aria-label*='étoile'], [aria-label*='etoile'], [aria-label*='avis']"
                    )
                    for idx in range(min(card_rating.count(), 3)):
                        candidate = card_rating.nth(idx).get_attribute("aria-label")
                        if candidate and any(
                            key in candidate.lower()
                            for key in ["star", "review", "étoile", "etoile", "avis"]
                        ):
                            rating_label = candidate
                            break

                    if not rating_label:
                        details_root = page.locator("div[role='main']")
                        rating_locator = details_root.locator(
                            "[aria-label*='stars'], [aria-label*='reviews'], "
                            "[aria-label*='étoile'], [aria-label*='etoile'], [aria-label*='avis']"
                        )
                        for idx in range(min(rating_locator.count(), 5)):
                            candidate = rating_locator.nth(idx).get_attribute("aria-label")
                            if candidate and any(
                                key in candidate.lower()
                                for key in ["star", "review", "étoile", "etoile", "avis"]
                            ):
                                rating_label = candidate
                                break
                    rating, review_count = _parse_rating_and_reviews(rating_label)
                    if rating is None and review_count is None:
                        card_text = item.inner_text()
                        rating, review_count = _parse_rating_and_reviews(card_text)

                    phone = _safe_text(page.locator("button[data-item-id^='phone:']"))
                    if not phone:
                        phone = _safe_text(page.locator("button[data-item-id*='phone']"))
                    phone = _clean_phone(phone)

                    website = None
                    website_link = page.locator("a[data-item-id='authority']")
                    if website_link.count() > 0:
                        website = website_link.first.get_attribute("href")
                    else:
                        website_button = page.locator("button[data-item-id='authority']")
                        if website_button.count() > 0:
                            website = website_button.first.get_attribute("data-url")

                    if not website:
                        log("Website not found")

                    if name:
                        lead_key = f"{name}|{phone}|{website}"
                        if lead_key not in seen:
                            social_links = []
                            email = None
                            if deep_search and website:
                                try:
                                    detail_page = context.new_page()
                                    detail_page.goto(website, wait_until="domcontentloaded", timeout=30000)
                                    time.sleep(random.uniform(1, 2))

                                    page_text = detail_page.content()
                                    social_matches = re.findall(
                                        r"https?://(?:www\.)?(?:instagram\.com|facebook\.com|linkedin\.com)/[^\"\'\s>]+",
                                        page_text,
                                        re.IGNORECASE,
                                    )
                                    social_links.extend(social_matches)

                                    email_match = re.search(
                                        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                                        page_text,
                                    )
                                    if email_match:
                                        email = email_match.group(0)

                                    detail_page.close()
                                except Exception:
                                    email = None

                                social_links = list(dict.fromkeys(social_links))

                            lead = {
                                "Name": name,
                                "Phone": phone,
                                "Website": website,
                                "Rating": rating,
                                "Review Count": review_count,
                                "Social Links": social_links if social_links else None,
                                "Email": email,
                            }
                            leads.append(lead)
                            seen.add(lead_key)
                            log(f"Captured: {name}")
                            log(f"__LEAD__:{json.dumps(lead, ensure_ascii=False)}")
                            if deep_search:
                                log(
                                    "__ENRICH__:" + json.dumps(
                                        {
                                            "Name": name,
                                            "Email": email,
                                            "Social Links": social_links,
                                        },
                                        ensure_ascii=False,
                                    )
                                )

                except Exception as e:
                    log(f"Lead extraction failed: {str(e)}")

                current_index += 1

            if stop_event and stop_event.is_set():
                break

            if current_index >= max_results:
                break

            if count == last_count:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
                last_count = count

            if stagnant_rounds >= 3:
                break

            if count > 0:
                items.nth(count - 1).scroll_into_view_if_needed()
            feed.evaluate("el => { el.scrollTop = el.scrollHeight; }")
            time.sleep(random.uniform(1, 3))
            page_number = max(1, (current_index // 20) + 1)
            log(f"__PROGRESS__:Scanning page {page_number}...")

        browser.close()

    return leads
