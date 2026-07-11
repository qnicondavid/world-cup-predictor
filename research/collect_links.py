#!/usr/bin/env python3
"""
research/collect_links.py - collect ALL match URLs for a World Cup results page.

OddsHarvester's own collector stops at OddsPortal's first results page (~50
matches), so the tournament openers are missed. OddsPortal renders the results
list virtualized (only the visible rows are in the DOM), so this script scrolls
down in small steps, accumulating every /football/h2h/ link as rows mount, and
writes them to data/wc{season}_links.txt - which you then feed to OddsHarvester
in full mode (all bookmakers).

    python3 research/collect_links.py 2018
    python3 research/collect_links.py 2022

Needs playwright (already installed): python3 -m playwright install chromium
"""
import sys
import time
from playwright.sync_api import sync_playwright

SEASON = sys.argv[1] if len(sys.argv) > 1 else "2018"
# OddsPortal's slug varies by edition: 2018/2022 live at world-cup-YYYY, but the 2026
# finals are under world-championship-2026. Pass the exact results URL as the 2nd arg
# to override the default, e.g.:
#   python research/collect_links.py 2026 https://www.oddsportal.com/football/world/world-championship-2026/results/
RESULTS = (sys.argv[2] if len(sys.argv) > 2
           else f"https://www.oddsportal.com/football/world/world-cup-{SEASON}/results/")
OUT = f"data/wc{SEASON}_links.txt"


def dismiss_cookies(page):
    for sel in ("#onetrust-accept-btn-handler", "button:has-text('I Accept')",
                "button:has-text('Accept')", "button:has-text('AGREE')"):
        try:
            page.click(sel, timeout=2500)
            return
        except Exception:
            pass


def harvest(page, found):
    for h in page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)"):
        u = h.split("#")[0].rstrip("/")
        if "/football/h2h/" in u:
            found.add(u + "/")


def scrape_current(page, found):
    """Scroll the currently-loaded results page, harvesting every h2h link as
    virtualized rows mount."""
    at_bottom = 0
    for _ in range(80):
        harvest(page, found)
        scroll_y, inner_h, total_h = page.evaluate(
            "() => [window.scrollY, window.innerHeight, document.body.scrollHeight]")
        if scroll_y + inner_h >= total_h - 200:
            at_bottom += 1
            if at_bottom >= 4:
                break
        else:
            at_bottom = 0
        page.mouse.wheel(0, 800)
        time.sleep(0.5)
    harvest(page, found)


def load_results(page):
    """Load the results page and wait for the match list to actually render, retrying a
    few times since OddsPortal throttles headless hits. Returns True if matches appeared."""
    for attempt in range(1, 4):
        print(f"requesting (attempt {attempt}): {RESULTS}")
        page.goto(RESULTS, timeout=60000, wait_until="domcontentloaded")
        time.sleep(3)
        dismiss_cookies(page)
        try:
            page.wait_for_selector('a[href*="/football/h2h/"]', timeout=25000)
            print(f"landed on:  {page.url}\n  page title: {page.title()!r}")
            return True
        except Exception:
            print(f"  match list did not render (attempt {attempt}); waiting and retrying")
            time.sleep(6)
    print(f"landed on:  {page.url}\n  page title: {page.title()!r}")
    return False


def next_page(page, pg):
    """Advance to results page `pg`. OddsPortal's page-number controls are <a> tags with the
    number as text and NO href, wired by JS, so we click the matching element directly. The
    4-digit season links (2026, 2022, ...) do have hrefs, so filtering on empty href avoids
    them. Returns True if a control was clicked."""
    for _ in range(6):                              # bring the pagination bar into view
        page.mouse.wheel(0, 3000)
        time.sleep(0.3)
    # The page controls are the set of short-numeric anchors with no href (1..10, 20, ...).
    # Tag the one matching pg, then click it NATIVELY so the SPA's real click handler fires.
    tagged = page.evaluate("""(pg) => {
        const nums = [...document.querySelectorAll('a')].filter(el => {
            const t = (el.textContent || '').trim();
            return /^\\d{1,2}$/.test(t) && !el.getAttribute('href');
        });
        const target = nums.find(el => (el.textContent || '').trim() === String(pg));
        if (!target) return false;
        target.setAttribute('data-collect-target', '1');
        target.scrollIntoView({block: 'center'});
        return true;
    }""", pg)
    if not tagged:
        return False
    try:
        page.click('[data-collect-target="1"]', timeout=5000)
        ok = True
    except Exception:
        ok = False
    page.evaluate("() => { const e = document.querySelector('[data-collect-target]');"
                  " if (e) e.removeAttribute('data-collect-target'); }")
    return ok


def dump_pagination(page):
    """Print the short numeric/arrow clickables at the page bottom (the real page controls)."""
    cands = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('a,button,[role=button]').forEach(e => {
            const t = (e.textContent || '').trim();
            if (t && t.length <= 4 && /^[0-9»«<>]+$/.test(t))
                out.push(e.tagName + ' "' + t + '" testid=' + (e.getAttribute('data-testid') || '')
                         + ' href=' + (e.getAttribute('href') || ''));
        });
        return out.slice(0, 40);
    }""")
    print("  PAGINATION CANDIDATES (numeric/arrow clickables at bottom):")
    for c in (cands or ["(none found)"]):
        print("   ", c)


def main():
    found = set()
    with sync_playwright() as p:
        # Visible window: OddsPortal rate-limits/blocks headless Chromium, so a real window
        # is far more reliable (and lets you clear any cookie or anti-bot prompt by hand).
        # Flip to headless=True only if it is loading cleanly for you.
        browser = p.chromium.launch(headless=False, slow_mo=120)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        if not load_results(page):
            print("Results list never rendered; OddsPortal is likely throttling the headless "
                  "browser. Wait a minute and retry, or set headless=False (the chromium.launch "
                  "line) to pass it in a visible window. Leaving output untouched.")
            browser.close()
            return
        scrape_current(page, found)
        print(f"  page 1: {len(found)} match links")
        prev = len(found)
        for pg in range(2, 16):
            if not next_page(page, pg):
                print(f"  no clickable control for page {pg}.")
                dump_pagination(page)
                break
            time.sleep(3)
            scrape_current(page, found)
            print(f"  page {pg}: {len(found)} match links")
            if len(found) == prev:
                print(f"  page {pg} added nothing new; stopping")
                dump_pagination(page)
                break
            prev = len(found)
        browser.close()

    if not found:
        print(f"No match links collected; leaving {OUT} untouched.")
        return
    links = sorted(found)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(links) + "\n")
    print(f"\ncollected {len(links)} match links -> {OUT}")
    for l in links[:6]:
        print("   sample:", l)


if __name__ == "__main__":
    main()
