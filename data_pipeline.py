# data_pipeline.py
import os, requests, math
from typing import Dict, List, Optional
from dotenv import load_dotenv
from ticket_scraper import load_cached_ticket_totals

load_dotenv()
YT_KEY = os.getenv("YOUTUBE_API_KEY", "")

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
                views    += _safe_int(st.get("viewCount", 0))
                likes    += _safe_int(st.get("likeCount", 0))
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
