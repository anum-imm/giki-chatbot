#!/usr/bin/env python3
"""
giki_selenium_scraper.py

Selenium-based crawler for https://www.giki.edu.pk

Outputs:
  data/raw/pages/*.json         per-page JSON
  data/raw/giki_scraped.json    aggregated pages
  data/raw/scraping_stats.json  stats
"""
from __future__ import annotations
import os, re, time, json, hashlib, logging
from urllib.parse import urljoin, urlparse, urlunparse, urlencode, parse_qsl
from typing import List, Set, Optional
from dataclasses import dataclass, asdict
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# Optional: load env
from dotenv import load_dotenv
load_dotenv()

# Config (overridable via env)
BASE_URL = os.getenv("BASE_URL", "https://giki.edu.pk")
MAX_PAGES = int(os.getenv("MAX_PAGES_TO_SCRAPE", "500"))
SAVE_DIR = os.getenv("SCRAPE_SAVE_DIR", "data/raw/pages")
AGG_PATH = os.getenv("AGG_OUT", "data/raw/giki_scraped.json")
STATS_PATH = os.getenv("STATS_OUT", "data/raw/scraping_stats.json")
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
SLEEP_BETWEEN_REQUESTS = float(os.getenv("SLEEP_BETWEEN_REQUESTS", "0.5"))
USE_RENDERER = bool(int(os.getenv("USE_RENDERER", "1")))  # default to use Selenium fallback
HEADLESS = bool(int(os.getenv("HEADLESS", "1")))

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("giki_selenium_scraper")

# Helpers ---------------------------------------------------------------------
def normalize_url(u: str) -> str:
    try:
        parsed = urlparse(u)
        if not parsed.scheme:
            parsed = parsed._replace(scheme="https")
        parsed = parsed._replace(fragment="")
        qs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
              if not (k.lower().startswith("utm_") or k.lower() in ("fbclid", "gclid", "trk"))]
        new_q = urlencode(qs, doseq=True)
        path = parsed.path.rstrip("/") or "/"
        parsed = parsed._replace(query=new_q, path=path)
        return urlunparse(parsed)
    except Exception:
        return u

def same_domain(url: str, base: str) -> bool:
    try:
        p = urlparse(url).netloc.lower()
        b = urlparse(base).netloc.lower()
        return p == b or p.endswith("." + b)
    except Exception:
        return False

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

# Data class -----------------------------------------------------------------
@dataclass
class PageRecord:
    url: str
    title: str
    description: str
    content: str
    word_count: int

    def to_json(self):
        return asdict(self)

# Scraper --------------------------------------------------------------------
class GIKIScraper:
    def __init__(self, base_url: str = BASE_URL, max_pages: int = MAX_PAGES):
        self.base_url = base_url.rstrip("/")
        self.max_pages = max_pages
        self.visited_urls: Set[str] = set()
        self.to_visit: List[str] = []
        self.records: List[PageRecord] = []
        self.seen_hashes: Set[str] = set()

        # requests session
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.session.max_redirects = 5

        # robots.txt
        self.rp = RobotFileParser()
        try:
            robots_url = urljoin(self.base_url, "/robots.txt")
            self.rp.set_url(robots_url)
            self.rp.read()
            logger.info(f"Loaded robots.txt from {robots_url}")
        except Exception:
            logger.warning("Failed to load robots.txt")

        # seeds
        self.to_visit = [normalize_url(self.base_url + "/events/")]  # start from events, or base
        os.makedirs(SAVE_DIR, exist_ok=True)

        # selenium driver setup
        self.driver = None
        self.driver_ready = False
        if USE_RENDERER:
            self._init_selenium()

    def _init_selenium(self):
        try:
            opts = Options()
            if HEADLESS:
                # new headless flag for modern Chrome can be used; this is common fallback
                opts.add_argument("--headless=new")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-gpu")
            opts.add_argument(f"user-agent={USER_AGENT}")
            # optional: more options for stability
            opts.add_argument("--window-size=1400,900")
            self.driver = webdriver.Chrome(service=webdriver.ChromeService(ChromeDriverManager().install()), options=opts)
            self.driver.set_page_load_timeout(30)
            self.driver_ready = True
            logger.info("Selenium Chrome driver initialized")
        except Exception as e:
            logger.warning(f"Failed to init Selenium driver: {e}")
            self.driver_ready = False

    def can_fetch(self, url: str) -> bool:
        try:
            return self.rp.can_fetch(self.session.headers.get("User-Agent", "*"), url)
        except Exception:
            return True

    def fetch_via_requests(self, url: str) -> Optional[str]:
        try:
            if not self.can_fetch(url):
                logger.debug("Blocked by robots.txt (requests): %s", url)
                return None
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code >= 400:
                logger.debug("Requests got status %s for %s", resp.status_code, url)
                return None
            # best-effort encoding fix
            if not resp.encoding or resp.encoding.lower() in ("iso-8859-1","latin-1"):
                resp.encoding = resp.apparent_encoding
            return resp.text
        except Exception as e:
            logger.debug("Requests fetch error %s : %s", url, e)
            return None

    def fetch_via_selenium(self, url: str, wait_seconds: float = 1.0) -> Optional[str]:
        if not self.driver_ready:
            return None
        try:
            if not self.can_fetch(url):
                logger.debug("Blocked by robots.txt (selenium): %s", url)
                return None
            self.driver.get(url)
            # small heuristic: scroll + wait to let JS/AJAX run
            self._scroll_page()
            time.sleep(wait_seconds)
            return self.driver.page_source
        except Exception as e:
            logger.debug("Selenium fetch error %s : %s", url, e)
            return None

    def _scroll_page(self, pause: float = 0.6, max_scrolls: int = 6):
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            for _ in range(max_scrolls):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(pause)
                new_h = self.driver.execute_script("return document.body.scrollHeight")
                if new_h == last_height:
                    break
                last_height = new_h
        except Exception:
            pass

    def extract_content(self, html: str, url: str) -> Optional[PageRecord]:
        try:
            soup = BeautifulSoup(html, "lxml")
            for el in soup(["script", "style", "noscript", "iframe", "header", "footer", "nav", "aside"]):
                el.decompose()

            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            main = (soup.find("main") or soup.find(attrs={"role":"main"}) or soup.find("article") or
                    soup.find("div", class_="content") or soup.find("div", id="content") or soup.body)
            content_text = main.get_text(separator=" ", strip=True) if main else soup.get_text(separator=" ", strip=True)
            content_text = re.sub(r"\s+", " ", content_text).strip()

            if not content_text:
                return None

            md = soup.find("meta", {"name": "description"}) or soup.find("meta", {"property": "og:description"})
            description = md["content"].strip() if (md and md.get("content")) else ""

            pr = PageRecord(url=url, title=title or "", description=description or "",
                            content=content_text, word_count=len(content_text.split()))
            return pr
        except Exception as e:
            logger.debug("extract_content failed for %s : %s", url, e)
            return None

    def extract_links(self, html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            full = urljoin(base_url, href.split("#")[0])
            norm = normalize_url(full)
            links.append(norm)
        uniq = []
        for l in links:
            if l not in uniq and same_domain(l, self.base_url):
                uniq.append(l)
        return uniq

    def save_page(self, record: PageRecord):
        key = record.url.replace("://", "_").replace("/", "__")
        fname = os.path.join(SAVE_DIR, f"{key[:200]}.json")
        try:
            with open(fname, "w", encoding="utf-8") as fw:
                json.dump(record.to_json(), fw, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug("Failed to save %s : %s", fname, e)

    def crawl(self):
        logger.info("Starting crawl at %s (max %d)", self.base_url, self.max_pages)
        pbar = tqdm(total=self.max_pages, desc="Pages")
        while self.to_visit and len(self.visited_urls) < self.max_pages:
            url = self.to_visit.pop(0)
            url = normalize_url(url)
            if url in self.visited_urls:
                continue
            if not same_domain(url, self.base_url):
                continue
            if not self.can_fetch(url):
                logger.debug("Blocked by robots.txt: %s", url)
                self.visited_urls.add(url)
                pbar.update(1)
                continue

            self.visited_urls.add(url)
            html = self.fetch_via_requests(url)
            # heuristics: if small HTML or contains 'load more' tokens, fall back to selenium
            if (not html or len(html) < 800 or any(tok in (html or "").lower() for tok in ["load more", "admin-ajax", "wp-json", "infinite"])) and USE_RENDERER:
                logger.debug("Falling back to Selenium for %s", url)
                shtml = self.fetch_via_selenium(url)
                if shtml:
                    html = shtml

            if not html:
                logger.debug("No HTML for %s", url)
                pbar.update(1)
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                continue

            page_record = self.extract_content(html, url)
            if page_record and page_record.word_count >= 30:
                h = content_hash(page_record.content)
                if h not in self.seen_hashes:
                    self.seen_hashes.add(h)
                    self.records.append(page_record)
                    self.save_page(page_record)
                    # extract links
                    new_links = self.extract_links(html, url)
                    for l in new_links:
                        if l not in self.visited_urls and l not in self.to_visit:
                            if any(x in l.lower() for x in ["/wp-admin", "/wp-content/", "/feed", "/?s="]):
                                continue
                            self.to_visit.append(l)

            pbar.update(1)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
        pbar.close()
        logger.info("Crawl finished: visited %d, collected %d records", len(self.visited_urls), len(self.records))
        return [r.to_json() for r in self.records]

    def save_aggregate(self, out_path: str = AGG_PATH):
        if not self.records:
            logger.warning("No records to aggregate")
            return
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([r.to_json() for r in self.records], f, ensure_ascii=False, indent=2)
        stats = {
            "total_pages": len(self.records),
            "total_words": sum(r.word_count for r in self.records),
            "urls_visited": len(self.visited_urls),
            "average_words_per_page": (sum(r.word_count for r in self.records) / len(self.records)) if self.records else 0
        }
        with open(STATS_PATH, "w", encoding="utf-8") as sf:
            json.dump(stats, sf, indent=2)
        logger.info("Saved aggregate to %s and stats to %s", out_path, STATS_PATH)

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass

# Entrypoint -----------------------------------------------------------------
def main():
    scraper = GIKIScraper(base_url=BASE_URL, max_pages=MAX_PAGES)
    try:
        results = scraper.crawl()
        scraper.save_aggregate()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        scraper.save_aggregate()
    except Exception as e:
        logger.exception("Fatal error during scraping")
        scraper.save_aggregate()
        raise
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
