"""
Browser-based business discovery using Playwright + Google Maps.

Tier 0: no API key required. Launches a real Chromium browser, searches
Google Maps, and extracts live business data (name, phone, address, website,
Google Maps URL). Falls back gracefully on per-business failures.
"""

import asyncio
import random
import time
from urllib.parse import quote_plus

from discovery import _check_website_health


async def browser_discover(
    city: str,
    business_type: str,
    neighborhood: str = "",
    max_results: int = 20,
    headless: bool = True,
) -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("Playwright is not installed. Run: pip install playwright && playwright install chromium")

    query = f"{business_type} near {neighborhood} {city} BC" if neighborhood else f"{business_type} in {city} BC"
    url = f"https://www.google.com/maps/search/{quote_plus(query)}"

    businesses = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-CA",
        )
        page = await ctx.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Captcha / block detection
            if "google.com/sorry" in page.url or "unusual traffic" in (await page.title()).lower():
                raise RuntimeError(
                    "Google Maps blocked the request. Try again later or set headless=False."
                )

            # Dismiss cookie/consent dialog if present
            try:
                await page.locator('button:has-text("Accept all")').click(timeout=4000)
            except Exception:
                pass

            # Wait for the results feed
            await page.wait_for_selector('div[role="feed"]', timeout=15000)

            # Scroll to load up to max_results cards
            feed = page.locator('div[role="feed"]')
            for _ in range(20):
                cards = await page.locator('div[role="article"]').count()
                if cards >= max_results:
                    break
                await feed.evaluate("el => el.scrollBy(0, 800)")
                await page.wait_for_timeout(600)

            cards = page.locator('div[role="article"]')
            count = min(await cards.count(), max_results)
            print(f"[browser_discovery] Found {count} result cards for: {query}")

            for i in range(count):
                try:
                    card = cards.nth(i)
                    await card.click()
                    # Wait for detail pane to load
                    await page.wait_for_selector("h1.DUwDvf, h1", timeout=8000)
                    await page.wait_for_timeout(random.randint(800, 1500))

                    # Re-check for captcha after navigation
                    if "google.com/sorry" in page.url:
                        raise RuntimeError(
                            "Google Maps blocked the request. Try again later or set headless=False."
                        )

                    name = await _text_or(page, ["h1.DUwDvf", "h1"])
                    if not name:
                        continue

                    address = await _aria_label_or(page, [
                        'button[data-item-id="address"]',
                        'button[aria-label*="Address"]',
                    ])
                    phone = await _aria_label_or(page, [
                        'button[data-item-id^="phone"]',
                        'button[aria-label*="Phone"]',
                    ])
                    website = await _href_or(page, [
                        'a[data-item-id="authority"]',
                        'a[aria-label*="website" i]',
                    ])
                    maps_url = page.url

                    rating_text = await _text_or(page, [
                        "div.F7nice span[aria-hidden]",
                        "span.ceNzKf[aria-hidden]",
                    ])
                    try:
                        rating = float(rating_text) if rating_text else None
                    except ValueError:
                        rating = None

                    review_text = await _text_or(page, [
                        'button[jsaction*="reviewChart"]',
                        'span[aria-label*="review" i]',
                    ])
                    try:
                        review_count = int("".join(c for c in (review_text or "") if c.isdigit()) or "0")
                    except ValueError:
                        review_count = 0

                    website_health = _check_website_health(website) if website else None

                    businesses.append({
                        "name": name.strip(),
                        "address": address or "",
                        "phone": phone or "",
                        "existing_website": website,
                        "rating": rating,
                        "review_count": review_count,
                        "photos_count": 0,
                        "category": business_type,
                        "city": city,
                        "neighborhood": neighborhood,
                        "google_maps_url": maps_url,
                        "website_health": website_health,
                        "source": "browser_maps",
                    })
                    print(f"[browser_discovery] ({i+1}/{count}) {name}")

                except RuntimeError:
                    raise
                except Exception as exc:
                    print(f"[browser_discovery] Skipping card {i}: {exc}")
                    continue

        finally:
            await browser.close()

    return businesses


async def _text_or(page, selectors: list[str]) -> str | None:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                text = (await el.inner_text(timeout=2000)).strip()
                if text:
                    return text
        except Exception:
            continue
    return None


async def _aria_label_or(page, selectors: list[str]) -> str | None:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                label = await el.get_attribute("aria-label", timeout=2000)
                if label:
                    # aria-label often prefixed with "Address: " or "Phone: "
                    for prefix in ("Address: ", "Phone: ", "address: ", "phone: "):
                        if label.startswith(prefix):
                            label = label[len(prefix):]
                    return label.strip()
        except Exception:
            continue
    return None


async def _href_or(page, selectors: list[str]) -> str | None:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                href = await el.get_attribute("href", timeout=2000)
                if href and href.startswith("http"):
                    return href.strip()
        except Exception:
            continue
    return None


def browser_discover_sync(
    city: str,
    business_type: str,
    neighborhood: str = "",
    max_results: int = 20,
    headless: bool = True,
) -> list[dict]:
    return asyncio.run(browser_discover(city, business_type, neighborhood, max_results, headless))
