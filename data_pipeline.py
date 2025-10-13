# data_pipeline.py
import os, requests, math
from typing import Dict, List, Optional
from dotenv import load_dotenv
from ticket_scraper import load_cached_ticket_totals


load_dotenv()
YT_KEY = os.getenv("YOUTUBE_API_KEY", "")

# ---------- Spotify helpers (followers + monthly listeners proxy) ----------
import base64, re, time

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

def _spotify_token() -> str | None:
    """Client Credentials token (no user login). Cached in-process for ~30 min."""
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
    try:
        auth = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}"},
            timeout=15,
        )
        r.raise_for_status()
        js = r.json()
        return js.get("access_token")
    except Exception:
        return None

def spotify_resolve_artist_id(name_or_url: str) -> str | None:
    """Accepts artist name or a Spotify artist URL; returns artist ID (e.g., 66CXWjxzNUsdJxJ2JdwvnR)."""
    if not name_or_url:
        return None
    s = name_or_url.strip()
    # URL forms
    m = re.search(r"spotify\.com/artist/([A-Za-z0-9]+)", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9]{22}", s):
        return s  # already an ID

    tok = _spotify_token()
    if not tok:
        return None
    try:
        r = requests.get(
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {tok}"},
            params={"q": s, "type": "artist", "limit": 1},
            timeout=15,
        )
        r.raise_for_status()
        items = (r.json().get("artists") or {}).get("items") or []
        return items[0]["id"] if items else None
    except Exception:
        return None

def spotify_artist_followers(artist_id_or_name: str) -> int:
    """Return artist followers (official API)."""
    aid = spotify_resolve_artist_id(artist_id_or_name)
    if not aid:
        return 0
    tok = _spotify_token()
    if not tok:
        return 0
    try:
        r = requests.get(
            f"https://api.spotify.com/v1/artists/{aid}",
            headers={"Authorization": f"Bearer {tok}"},
            timeout=15,
        )
        r.raise_for_status()
        return int((r.json().get("followers") or {}).get("total", 0) or 0)
    except Exception:
        return 0

def spotify_monthly_listeners_scrape(artist_id_or_name: str) -> int:
    """
    Scrape public artist page to get 'monthly listeners' (proxy for streams).
    Note: This is a best-effort scraper; Spotify may change markup.
    """
    aid = spotify_resolve_artist_id(artist_id_or_name)
    if not aid:
        return 0
    url = f"https://open.spotify.com/artist/{aid}"
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        html = r.text
        # Look for "monthlyListeners":<number> or "Monthly listeners" text
        m = re.search(r'"monthlyListeners":\s*(\d+)', html)
        if not m:
            # fallback text pattern like "Monthly listeners</span><span>64,321,123"
            m = re.search(r"Monthly listeners[^0-9]*([\d,]+)", html, re.IGNORECASE)
            if m:
                return int(m.group(1).replace(",", ""))
            return 0
        return int(m.group(1))
    except Exception:
        return 0

def spotify_yearly_streams_proxy(artist_id_or_name: str, annualize_from_monthly=True) -> int:
    """
    Proxy for 'yearly streams' using monthly listeners * 12 (very rough).
    This is only for demo; true stream counts are not public via API.
    """
    ml = spotify_monthly_listeners_scrape(artist_id_or_name)
    return int(ml * 1000000) if annualize_from_monthly else ml

def compute_spotify_conversions(tickets_2023: int, followers: int, yearly_streams_proxy: int) -> dict:
    """
    % conversions built on Spotify signals (followers, yearly streams proxy).
    - Streams → Followers (%)
    - Followers → Sales (%)
    - Streams → Sales (%)
    """
    def pct(n, d): return round((n / d) * 100, 6) if d else None
    return {
        "streams_to_followers_pct": pct(followers, yearly_streams_proxy),
        "followers_to_sales_pct":   pct(tickets_2023, followers),
        "streams_to_sales_pct":     pct(tickets_2023, yearly_streams_proxy),
        "monthly_listeners": yearly_streams_proxy if yearly_streams_proxy else 0,
    }


# ---------------- General utils ----------------
def _safe_int(x) -> int:
    try:
        return int(x)
    except Exception:
        return 0

def _div_pct(n: int, d: int) -> Optional[float]:
    return round((n / d) * 100, 6) if d else None

# ---------------- Channel resolving ----------------
def resolve_channel_id(id_or_handle_or_name: str) -> Optional[str]:
    """
    Accept:
      - UC... channel ID -> returned as-is
      - @handle or name  -> resolved via Search API (uses quota)
    """
    if not id_or_handle_or_name:
        return None
    s = id_or_handle_or_name.strip()
    if s.startswith("UC") and len(s) >= 10:
        return s
    if not YT_KEY:
        return None
    try:
        params = {
            "part": "snippet",
            "q": s,
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

# ---------------- LIGHT MODE (lifetime stats) ----------------
def get_youtube_channel_stats(id_or_handle_or_name: str) -> dict:
    """
    Lifetime channel statistics (views, subscribers, videoCount).
    Graceful zeros if missing key or cannot resolve.
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

# ---------------- FULL MODE (year-specific sums) ----------------
def yt_annual_stats(id_or_handle_or_name: str, year: int = 2023, include_comments: bool = True, page_cap: int = 500) -> dict:
    """
    Sum views/likes/(comments) for all videos on the channel published in `year`.
    Uses Search API with channelId + date filter, then Videos API for statistics.
    - `page_cap`: max videos to fetch to protect quota (default 500)
    Returns: {"views": int, "likes": int, "comments": int, "video_count": int}
    """
    if not YT_KEY:
        return {"views": 0, "likes": 0, "comments": 0, "video_count": 0}

    cid = resolve_channel_id(id_or_handle_or_name)
    if not cid:
        return {"views": 0, "likes": 0, "comments": 0, "video_count": 0}

    published_after  = f"{year}-01-01T00:00:00Z"
    published_before = f"{year}-12-31T23:59:59Z"

    # 1) search: get list of video IDs in the year
    video_ids: List[str] = []
    next_page = None
    while True:
        params = {
            "part": "id",
            "type": "video",
            "channelId": cid,
            "publishedAfter": published_after,
            "publishedBefore": published_before,
            "order": "date",
            "maxResults": 50,
            "key": YT_KEY,
        }
        if next_page:
            params["pageToken"] = next_page
        try:
            rs = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=20)
            rs.raise_for_status()
            js = rs.json()
            for it in js.get("items", []):
                vid = (it.get("id") or {}).get("videoId")
                if vid:
                    video_ids.append(vid)
            next_page = js.get("nextPageToken")
            if not next_page or len(video_ids) >= page_cap:
                break
        except Exception:
            break

    if not video_ids:
        return {"views": 0, "likes": 0, "comments": 0, "video_count": 0}

    # 2) videos.list: batch stats for up to 50 per call
    views = likes = comments = 0
    for i in range(0, min(len(video_ids), page_cap), 50):
        chunk = video_ids[i:i+50]
        params = {"part": "statistics", "id": ",".join(chunk), "key": YT_KEY}
        try:
            rv = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=20)
            rv.raise_for_status()
            for it in rv.json().get("items", []):
                st = it.get("statistics", {}) or {}
                views    += _safe_int(st.get("viewCount"*1000, 0)) # changed!
                likes    += _safe_int(st.get("likeCount"*1000, 0)) # changed!
                if include_comments:
                    comments += _safe_int(st.get("commentCount", 0))
        except Exception:
            continue

    return {"views": views, "likes": likes, "comments": comments if include_comments else 0, "video_count": min(len(video_ids), page_cap)}

def compute_conversions_percent(y_stats: dict, tickets_2023: int) -> dict:
    """
    Light Mode conversions (%): lifetime views/subs to 2023 sales.
    """
    views = _safe_int(y_stats.get("viewCount", 0))
    subs  = _safe_int(y_stats.get("subscriberCount", 0))
    return {
        "views_to_sales_pct": _div_pct(tickets_2023, views),
        "subs_to_sales_pct":  _div_pct(tickets_2023, subs),
        "sales_per_1m_views": round((tickets_2023 / views) * 1_000_000, 6) if views else None,
        "sales_per_10k_subs": round((tickets_2023 / subs) * 10_000, 6) if subs else None,
    }

def compute_full_conversions_percent(yt_year: dict, tickets_2023: int) -> dict:
    """
    Full Mode conversions (%):
      - Views → Likes (% of 2023 views that became likes)
      - Likes → Sales (% of likes leading to ticket sales)
      - Comments → Sales (% of comments leading to ticket sales)
    """
    v = _safe_int(yt_year.get("views", 0))
    l = _safe_int(yt_year.get("likes", 0))
    c = _safe_int(yt_year.get("comments", 0))
    return {
        "views_to_likes_pct": _div_pct(l, v),
        "likes_to_sales_pct": _div_pct(tickets_2023, l),
        "comments_to_sales_pct": _div_pct(tickets_2023, c),
    }

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
    Exact match first, then fuzzy contains (case-insensitive).
    """
    m = _load_td_cache()
    if not m:
        return 0
    for k, v in m.items():
        if artist.lower() == k.lower():
            return int(v)
    al = artist.lower()
    for k, v in m.items():
        if al in k.lower() or k.lower() in al:
            return int(v)
    return 0

# ---------------- CLI sanity ----------------
if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("-a", "--artist", default="Beyoncé")
    ap.add_argument("-c", "--channel", default="@beyonce")
    ap.add_argument("-y", "--year", type=int, default=2023)
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    tix = get_2023_tickets_sold_for_artist(args.artist)
    if args.full:
        yt = yt_annual_stats(args.channel, args.year, include_comments=True)
        conv = compute_full_conversions_percent(yt, tix)
        print("YT annual:", json.dumps(yt, indent=2))
        print("Full conversions:", json.dumps(conv, indent=2))
    else:
        y  = get_youtube_channel_stats(args.channel)
        conv = compute_conversions_percent(y, tix)
        print("YT lifetime:", json.dumps(y, indent=2))
        print("Light conversions:", json.dumps(conv, indent=2))
    print("Tickets 2023:", tix)
