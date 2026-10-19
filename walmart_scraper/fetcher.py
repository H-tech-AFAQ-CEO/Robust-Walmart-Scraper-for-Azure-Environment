"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Page fetching. BrowserFetcher uses Playwright; anything with .fetch()/.start()/.close() works.
"""
from __future__ import annotations
import json, logging, random, time
from dataclasses import dataclass, field

log = logging.getLogger("ws.fetch")


@dataclass
class Page:
    url: str
    status: int = 0
    next_data: dict | None = None
    blocked: bool = False
    reason: str = ""
    latency: float = 0.0
    sub_links: list[dict] = field(default_factory=list)   # [{'name','url'}] found in DOM
    logo: str = ""


BLOCK_MARKERS = ("px-captcha", "robot or human", "are you a human", "/blocked", "access denied")


def classify(status: int, url: str, html_lower: str, nd) -> tuple[bool, str]:
    if status in (403, 429, 503):
        return True, f"http_{status}"
    if "/blocked" in url or any(m in html_lower[:20000] for m in BLOCK_MARKERS):
        return True, "bot_challenge"
    if status >= 400:
        return True, f"http_{status}"
    if nd is None:
        return True, "no_next_data"
    return False, ""


class BrowserFetcher:
    def __init__(self, settings, location):
        self.s, self.loc = settings, location
        self._pw = self._browser = self.ctx = self.page = None

    def start(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        kw = {}
        if self.s.proxy_url:
            kw["proxy"] = {"server": self.s.proxy_url}
        self._browser = self._pw.chromium.launch(headless=self.s.headless, **kw)
        self.ctx = self._browser.new_context(
            locale="en-US", timezone_id="America/New_York", viewport={"width": 1366, "height": 900})
        self.page = self.ctx.new_page()

    def close(self):
        for o in (self.ctx, self._browser):
            try:
                o and o.close()
            except Exception:
                pass
        try:
            self._pw and self._pw.stop()
        except Exception:
            pass

    def fetch(self, url: str, want_links: bool = False) -> Page:
        t0 = time.time()
        pg = Page(url=url)
        try:
            resp = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            pg.status = resp.status if resp else 0
            try:
                self.page.wait_for_selector("script#__NEXT_DATA__", state="attached", timeout=15000)
            except Exception:
                pass
            # lazy-loaded content: scroll so DOM links/images hydrate (item data is already in JSON)
            for _ in range(3):
                self.page.mouse.wheel(0, 2500)
                self.page.wait_for_timeout(400)
            html = self.page.content()
            raw = self.page.evaluate("() => (document.getElementById('__NEXT_DATA__')||{}).textContent || ''")
            nd = json.loads(raw) if raw else None
            pg.blocked, pg.reason = classify(pg.status, self.page.url, html.lower(), nd)
            pg.next_data = nd
            if want_links and not pg.blocked:
                pg.sub_links = self.page.evaluate(
                    """() => [...document.querySelectorAll('a[href*="/browse/"],a[href*="/cp/"]')]
                       .map(a => ({name:(a.innerText||'').trim().split('\\n')[0], url:a.href}))
                       .filter(x => x.name && x.name.length < 80)""")
                pg.logo = self.page.evaluate(
                    "() => { const i=document.querySelector('header img[alt*=\"Walmart\" i]'); return i? i.src : ''; }")
        except Exception as e:  # network/timeouts are retryable failures, not empty results
            pg.blocked, pg.reason = True, f"exception:{type(e).__name__}"
        pg.latency = time.time() - t0
        return pg

    def screenshot(self, path: str):
        try:
            self.page.screenshot(path=path, full_page=False)
        except Exception:
            pass

    # ---- store selection (selectors are isolated here; calibrate with `probe`)
    def select_store(self):
        """Pre-seed store cookie, then drive the 'Pickup or delivery' UI by ZIP + store id.
        Verification is independent (runner.verify_store reads the payload) so a UI change
        causes a loud failure rather than silently wrong-store data."""
        self.ctx.add_cookies([{"name": "assortmentStoreId", "value": self.loc.store_id,
                               "domain": ".walmart.com", "path": "/"}])
        self.page.goto("https://www.walmart.com/", wait_until="domcontentloaded", timeout=60000)
        try:
            self.page.get_by_role("button", name="Pickup or delivery").first.click(timeout=8000)
            self.page.get_by_text("Pickup", exact=False).first.click(timeout=5000)
            self.page.get_by_label("Zip code", exact=False).first.fill(self.loc.zipcode, timeout=5000)
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(2500)
            sel = self.page.locator(f"[data-store-id='{self.loc.store_id}'], :text('#{self.loc.store_id}')").first
            sel.click(timeout=8000)
            self.page.wait_for_timeout(2000)
        except Exception as e:
            log.warning("store UI flow incomplete (%s); relying on cookie + verification", type(e).__name__)


def backoff_sleep(attempt: int, base: float = 8.0):
    time.sleep(min(300, base * (2 ** attempt)) * random.uniform(0.7, 1.3))
