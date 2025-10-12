# ticket_scraper.py
import re, sys, html, unicodedata, json, requests, pathlib
from bs4 import BeautifulSoup

# ---------- Cache paths ----------
CACHE_DIR = pathlib.Path("data")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_JSON = CACHE_DIR / "touringdata_2023_tickets.json"

# ---------- Your working sources/headers ----------
WP_API_URLS = [
    "https://touringdata.org/wp-json/wp/v2/posts?slug=2023-top-touring-artists&per_page=1",
    "https://touringdata.wordpress.com/wp-json/wp/v2/posts?slug=2023-top-touring-artists&per_page=1",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# ---------- Helpers (same as your file) ----------
def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip()

def parse_int(s: str):
    m = re.search(r"(\d{1,3}(?:,\d{3})+)", s or "")
    return int(m.group(1).replace(",", "")) if m else None

def fetch_post_html() -> str:
    for url in WP_API_URLS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            arr = r.json()
            if isinstance(arr, list) and arr:
                post = arr[0]
                rendered = post.get("content", {}).get("rendered", "")
                if rendered:
                    return rendered
        except Exception:
            continue
    return ""

def extract_pairs_from_soup(soup):
    # Your robust sentence-based extractor
    def parse_int_commas(s: str):
        m = re.search(r"(\d{1,3}(?:,\d{3})+)", s or "")
        return int(m.group(1).replace(",", "")) if m else None

    text = soup.get_text(" ", strip=True)
    text = text.replace("—", "-").replace("–", "-").replace("−", "-")
    sentences = re.split(r"(?<=[\.\!\?])\s+(?=[A-Z(])", text)

    EXCLUDE = {
        "The Tour", "Tour", "Tickets", "Million", "Millions", "List", "Calendar-Year",
        "Gross", "From", "With", "At", "Her", "His", "Their", "Band", "Act",
        "Surpassing Her Own Numbers At", "No", "No.", "Rank", "Ranking"
    }
    VERB_PAT = r"(?:earned|grossed|sold|generated|was|were|became|ranked|finished|placed)"
    TICKET_PAT = re.compile(rf"(?P<prefix>.+?)\bfrom\s+(?P<num>\d{{1,3}}(?:,\d{{3}})+)\s+tickets\b", re.IGNORECASE)

    mapping = {}
    for sent in sentences:
        m = TICKET_PAT.search(sent)
        if not m:
            continue
        tickets = parse_int_commas(m.group("num"))
        if not tickets or tickets <= 10000:
            continue
        prefix = m.group("prefix")

        m_name = re.search(
            rf"(?P<name>[A-Z][A-Za-z0-9&' .]+?)\s*(?:\(\s*No\.\s*\d+\s*\))?\s+{VERB_PAT}\b",
            prefix, re.IGNORECASE
        ) or re.search(
            rf"(?P<name>[A-Z][A-Za-z0-9&' .]+?)\s+{VERB_PAT}\b",
            prefix, re.IGNORECASE
        )

        if m_name:
            candidate = m_name.group("name").strip()
        else:
            toks = re.findall(r"[A-Za-z][A-Za-z0-9&']*", prefix)
            chunks, cur = [], []
            for t in toks:
                if t[:1].isupper():
                    cur.append(t)
                else:
                    if cur: chunks.append(" ".join(cur)); cur=[]
            if cur: chunks.append(" ".join(cur))
            candidate = chunks[-1].strip() if chunks else None

        if not candidate:
            continue

        candidate = re.sub(r"\s*(?:No\.?\s*\d+)\s*$", "", candidate).strip(" -:,")
        candidate = norm_name(candidate)

        if not candidate or len(candidate) < 2:
            continue
        if candidate in {x.lower() for x in EXCLUDE}:
            continue
        if any(candidate.lower().startswith(x.lower()) for x in ["million", "tickets", "surpassing", "calendar-year", "list"]):
            continue

        key = candidate.lower()
        mapping[key] = max(tickets, mapping.get(key, 0))

    # return dict with nice casing
    return {k.title(): v for k, v in mapping.items()}

# ---------- Public API ----------
def refresh_cache(verbose=True) -> dict:
    html_doc = fetch_post_html()
    if not html_doc:
        if verbose: print("[ERR] No HTML fetched from WP REST API.")
        return {}
    soup = BeautifulSoup(html_doc, "lxml")
    pairs = extract_pairs_from_soup(soup)
    if not pairs:
        if verbose:
            preview = soup.get_text("\n", strip=True)[:800]
            print("[ERR] Parsed 0 artists.\nPreview:\n", preview)
        return {}

    # Sort + save
    mapping = dict(sorted(pairs.items(), key=lambda kv: kv[1], reverse=True))
    with open(CACHE_JSON, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    if verbose:
        print(f"[OK] Cached {len(mapping)} artists → {CACHE_JSON}")
    return mapping

def load_cached_ticket_totals() -> dict:
    if CACHE_JSON.exists():
        with open(CACHE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return refresh_cache(verbose=False)

# ---------- CLI ----------
if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh_cache(verbose=True)
    else:
        d = load_cached_ticket_totals()
        print(f"Artists in cache: {len(d)}")
        # print top few
        for i, (a, t) in enumerate(list(d.items())[:15], 1):
            print(f"{i:02d}. {a} — {t:,}")
        # spot checks
        for q in ["Coldplay", "Beyoncé", "Ed Sheeran", "Taylor Swift", "U2"]:
            v = d.get(q)
            if v: print(f"{q}: {v:,}")


