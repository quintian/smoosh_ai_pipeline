# data_pipeline.py
import os, requests
from dotenv import load_dotenv
from ticket_scraper import load_cached_ticket_totals

load_dotenv()
YT_KEY = os.getenv("YOUTUBE_API_KEY", "")

# ---------------- YouTube helpers ----------------
def _safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0

def resolve_channel_id(id_or_handle_or_name: str) -> str | None:
    """
    Accepts:
      - 'UC...' (channel ID)  -> returns as-is
      - '@handle'             -> resolves via search
      - 'Artist Name'         -> resolves via search
    Graceful if key missing (returns None).
    """
    if not id_or_handle_or_name:
        return None
    s = id_or_handle_or_name.strip()
    if s.startswith("UC") and len(s) >= 10:
        return s  # already a channel ID
    if not YT_KEY:
        return None  # no key to resolve

    # Use Search API to find most relevant channel
    try:
        params = {
            "part": "snippet",
            "q": s,                    # works for @handle or name
            "type": "channel",
            "maxResults": 1,
            "key": YT_KEY,
        }
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=20)
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return None
        return items[0]["id"]["channelId"]
    except Exception:
        return None

def get_youtube_channel_stats(id_or_handle_or_name: str) -> dict:
    """
    Fetch lifetime channel stats: views, subscribers, videoCount.
    If key missing or cannot resolve -> returns zeros (no crash).
    """
    if not YT_KEY:
        return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}

    cid = resolve_channel_id(id_or_handle_or_name)
    if not cid:
        return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}

    try:
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {"part": "statistics", "id": cid, "key": YT_KEY}
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}
        st = items[0].get("statistics", {}) or {}
        return {
            "viewCount": _safe_int(st.get("viewCount", 0)),
            "subscriberCount": _safe_int(st.get("subscriberCount", 0)),
            "videoCount": _safe_int(st.get("videoCount", 0)),
        }
    except Exception:
        return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}

# ---------------- TouringData 2023 tickets (cached) ----------------
_TD_2023 = None

def _load_td_cache() -> dict:
    global _TD_2023
    if _TD_2023 is None:
        try:
            _TD_2023 = load_cached_ticket_totals()  # {ArtistPrettyName: tickets_int}
        except Exception:
            _TD_2023 = {}
    return _TD_2023 or {}

def get_2023_tickets_sold_for_artist(artist: str) -> int:
    """
    Lookup 2023 tickets for `artist` from cached TouringData JSON.
    Exact match first, then fuzzy (case-insensitive contains).
    """
    m = _load_td_cache()
    if not m:
        return 0
    # exact
    for k, v in m.items():
        if artist.lower() == k.lower():
            return int(v)
    # fuzzy
    al = artist.lower()
    for k, v in m.items():
        kl = k.lower()
        if al in kl or kl in al:
            return int(v)
    return 0

# ---------------- Conversions (all in %) ----------------
def compute_conversions_percent(y_stats: dict, tickets_2023: int) -> dict:
    """
    Returns conversion rates as PERCENT values where meaningful.
    Using lifetime channel aggregates as the YouTube source.
    """
    views = _safe_int(y_stats.get("viewCount", 0))
    subs  = _safe_int(y_stats.get("subscriberCount", 0))
    # videos not used for %; keep as KPI
    out = {
        "views_to_sales_pct": round((tickets_2023 / views) * 100, 6) if views else None,
        "subs_to_sales_pct":  round((tickets_2023 / subs) * 100, 6) if subs else None,
        # convenience rates (not %):
        "sales_per_1m_views": round((tickets_2023 / views) * 1_000_000, 6) if views else None,
        "sales_per_10k_subs": round((tickets_2023 / subs) * 10_000, 6) if subs else None,
    }
    return out

# ---------------- Simple CLI test ----------------
if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("-a", "--artist", default="Beyoncé")
    ap.add_argument("-c", "--channel", default="@beyonce")  # handle works
    args = ap.parse_args()

    print("\n=== data_pipeline quick test ===")
    tix = get_2023_tickets_sold_for_artist(args.artist)
    y   = get_youtube_channel_stats(args.channel)
    conv = compute_conversions_percent(y, tix)
    print("Tickets 2023:", tix)
    print("YT stats:", json.dumps(y, indent=2))
    print("Conversions:", json.dumps(conv, indent=2))


