# data_pipeline.py
import os, requests, math
from typing import Dict, List, Optional
from dotenv import load_dotenv
from ticket_scraper import load_cached_ticket_totals


load_dotenv()
YT_KEY = os.getenv("YOUTUBE_API_KEY", "")

import os, re, requests
from dotenv import load_dotenv
from ticket_scraper import load_cached_ticket_totals

load_dotenv()
YT_KEY = os.getenv("YOUTUBE_API_KEY", "")

# --------------------------------------------------------------------
# Universal K/M/B text parser
# --------------------------------------------------------------------
_ABBREV_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*([KMBkmb]?)")

def parse_abbrev_count(raw: str) -> int:
    """Convert strings like '1.3M views' or '862K' or '2,345' to integer."""
    if not raw:
        return 0
    s = str(raw).replace(",", "").strip()
    m = _ABBREV_RE.search(s)
    if not m:
        return 0
    num = float(m.group(1))
    suf = m.group(2).upper()
    mult = 1
    if suf == "K": mult = 1_000
    elif suf == "M": mult = 1_000_000
    elif suf == "B": mult = 1_000_000_000
    return int(num * mult)

def extract_first_label(text: str, key_phrase: str) -> str | None:
    """Find first 'simpleText' or 'label' containing a key phrase like 'views'."""
    pat = re.compile(
        rf'"(?:simpleText|label)"\s*:\s*"([^"]*?\b{re.escape(key_phrase)}\b[^"]*)"',
        re.IGNORECASE,
    )
    m = pat.search(text or "")
    return m.group(1) if m else None

def extract_first_count_text(text: str, metric: str) -> str | None:
    """Extract YouTube count text for views / likes / comments / subscribers."""
    metric = metric.lower()
    if metric == "views":
        m = re.search(
            r'"(viewCountText|shortViewCountText)".*?"simpleText"\s*:\s*"([^"]+)"',
            text or "", re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(2)
        return extract_first_label(text, "views")
    elif metric == "likes":
        return extract_first_label(text, "likes")
    elif metric == "comments":
        return extract_first_label(text, "comments")
    elif metric == "subscribers":
        m = re.search(
            r'"subscriberCountText"\s*:\s*\{[^}]*"simpleText"\s*:\s*"([^"]+)"',
            text or "", re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1)
        return extract_first_label(text, "subscribers")
    return None

# --------------------------------------------------------------------
# YouTube API helpers (using the parser for numbers)
# --------------------------------------------------------------------
def _safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0

def resolve_channel_id(id_or_handle_or_name: str) -> str | None:
    """
    Accepts:
      - 'UC...' (channel ID)
      - '@handle'
      - 'Artist Name'
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

import json, time

# --- Robust like label finder on watch page ---
_LIKE_LABEL_PATTERNS = [
    # modern aria-label on the like button:
    re.compile(r'aria-label\s*=\s*"([^"]*?\blikes?\b[^"]*)"', re.IGNORECASE),
    # legacy accessibility label in ytInitialData:
    re.compile(r'"accessibilityData"\s*:\s*\{\s*"label"\s*:\s*"([^"]*?\blikes?\b[^"]*)"\s*\}', re.IGNORECASE),
    # generic "label":"1,234 likes"
    re.compile(r'"label"\s*:\s*"([^"]*?\blikes?\b[^"]*)"', re.IGNORECASE),
]

def _fetch_watch_html(video_id: str) -> str | None:
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def _extract_like_label(html: str) -> str | None:
    if not html: 
        return None
    for pat in _LIKE_LABEL_PATTERNS:
        m = pat.search(html)
        if m and re.search(r"\d", m.group(1)):
            return m.group(1)
    return None


def get_youtube_channel_stats(id_or_handle_or_name: str, debug=False) -> dict:
    """
    Fetch channel-level stats (views, subs, videos).
    Returns parsed integers and raw texts for verification.
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
        data = r.json()
        items = data.get("items", [])
        if not items:
            return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}

        stats = items[0].get("statistics", {})
        # Raw values as returned by API
        raw = {
            "viewCount": stats.get("viewCount"),
            "subscriberCount": stats.get("subscriberCount"),
            "videoCount": stats.get("videoCount"),
        }
        out = {
            "viewCount": _safe_int(stats.get("viewCount")),
            "subscriberCount": _safe_int(stats.get("subscriberCount")),
            "videoCount": _safe_int(stats.get("videoCount")),
            "_raw": raw
        }

        if debug:
            print("Raw YouTube stats:", raw)

        return out
    except Exception as e:
        if debug:
            print("YouTube fetch failed:", e)
        return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}

def yt_annual_stats(id_or_handle_or_name: str, year: int, include_comments: bool = True,
                    max_videos: int = 400, verify_with_html: bool = False, sample_n: int = 3) -> dict:
    if not YT_KEY:
        return {"views": 0, "likes": 0, "comments": 0, "video_count": 0, "_sample_raw": []}

    cid = resolve_channel_id(id_or_handle_or_name)
    if not cid:
        return {"views": 0, "likes": 0, "comments": 0, "video_count": 0, "_sample_raw": []}

    vid_ids = _yt_search_video_ids_for_year(cid, int(year), max_videos=max_videos)
    if not vid_ids:
        return {"views": 0, "likes": 0, "comments": 0, "video_count": 0, "_sample_raw": []}

    total_views = 0
    total_likes = 0
    total_comments = 0
    stats_items = _yt_fetch_video_stats(vid_ids)

    # map id -> likeCount we DID get from API (some will be None)
    api_like = {}
    for it in stats_items:
        vid = it.get("id")
        st = it.get("statistics", {}) or {}
        total_views    += _safe_int(st.get("viewCount", 0))
        lc = st.get("likeCount")
        api_like[vid] = _safe_int(lc) if lc is not None else None
        if include_comments:
            total_comments += _safe_int(st.get("commentCount", 0))

    # backfill likes by scraping ONLY where API returned None or 0
    backfill_targets = [vid for vid, lc in api_like.items() if not lc]
    for vid in backfill_targets:
        html = _fetch_watch_html(vid)
        like_label = _extract_like_label(html)
        parsed_likes = parse_abbrev_count(like_label or "")
        api_like[vid] = parsed_likes
        # be polite; avoid hammering
        time.sleep(0.2)

    # sum likes
    for vid in vid_ids:
        total_likes += _safe_int(api_like.get(vid, 0))

    result = {
        "views": total_views,
        "likes": total_likes,
        "comments": total_comments if include_comments else 0,
        "video_count": len(vid_ids),
    }

    if verify_with_html:
        samples = []
        for vid in vid_ids[:max(1, sample_n)]:
            html = _fetch_watch_html(vid) or ""
            raw_views = extract_first_count_text(html, "views")
            raw_likes = _extract_like_label(html) or extract_first_count_text(html, "likes")
            raw_comms = extract_first_count_text(html, "comments")
            samples.append({
                "videoId": vid,
                "views_raw": raw_views,   "views_parsed": parse_abbrev_count(raw_views or ""),
                "likes_raw": raw_likes,   "likes_parsed": parse_abbrev_count(raw_likes or ""),
                "comments_raw": raw_comms,"comments_parsed": parse_abbrev_count(raw_comms or ""),
            })
        result["_sample_raw"] = samples

    return result

def yt_annual_stats_multi(ids_or_handles_or_names, year: int, include_comments: bool = True,
                          max_videos: int = 400, verify_with_html: bool = False, sample_n: int = 3) -> dict:
    """
    Sum annual YouTube stats across multiple channels (IDs/handles/names separated by commas).
    """
    if isinstance(ids_or_handles_or_names, str):
        items = [s.strip() for s in ids_or_handles_or_names.split(",") if s.strip()]
    else:
        items = list(ids_or_handles_or_names or [])

    total = {"views": 0, "likes": 0, "comments": 0, "video_count": 0}
    samples = []
    for it in items:
        part = yt_annual_stats(it, int(year), include_comments=include_comments,
                               max_videos=max_videos, verify_with_html=verify_with_html, sample_n=sample_n)
        total["views"] += int(part.get("views", 0) or 0)
        total["likes"] += int(part.get("likes", 0) or 0)
        total["comments"] += int(part.get("comments", 0) or 0)
        total["video_count"] += int(part.get("video_count", 0) or 0)
        if verify_with_html and part.get("_sample_raw"):
            samples.extend(part["_sample_raw"])
    if verify_with_html:
        total["_sample_raw"] = samples[:sample_n]
    return total

# ---------- Spotify helpers (followers + monthly listeners as "streams") ----------
import base64, re

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

def _spotify_token() -> str | None:
    """Client Credentials token (no user login)."""
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
        return r.json().get("access_token")
    except Exception:
        return None

def spotify_resolve_artist_id(name_or_url: str) -> str | None:
    """Accepts artist name, artist URL, or artist ID; returns 22-char ID."""
    if not name_or_url:
        return None
    s = name_or_url.strip()
    # URL forms
    m = re.search(r"spotify\.com/artist/([A-Za-z0-9]{22})", s)
    if m:
        return m.group(1)
    # Raw ID
    if re.fullmatch(r"[A-Za-z0-9]{22}", s):
        return s

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
    """Return artist followers (official API; free)."""
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


def spotify_monthly_listeners_scrape(artist_id_or_name: str, return_raw: bool = False):
    """
    Scrape public artist page to get 'Monthly listeners' (text + parsed int).
    - Uses the same K/M/B parser as YouTube for correctness.
    - Returns int by default; returns dict {'raw': str, 'value': int} if return_raw=True.
    """
    aid = spotify_resolve_artist_id(artist_id_or_name)
    if not aid:
        return {"raw": None, "value": 0} if return_raw else 0

    url = f"https://open.spotify.com/artist/{aid}"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        html = r.text

        # Preferred JSON key (sometimes present in the page source)
        m_num_json = re.search(r'"monthlyListeners"\s*:\s*([0-9]+)', html)
        if m_num_json:
            raw_text = f"{m_num_json.group(1)} monthly listeners"
            val = int(m_num_json.group(1))
            return ({"raw": raw_text, "value": val} if return_raw else val)

        # Fallback textual pattern like: "Monthly listeners</span><span>55M"
        m_txt = re.search(r"Monthly listeners[^0-9KMBkmb]*([0-9][0-9,\.]*\s*[KkMmBb]?)", html)
        if m_txt:
            raw_chunk = m_txt.group(1).strip()
            val = parse_abbrev_count(raw_chunk)  # uses your universal K/M/B parser
            raw_text = f"{raw_chunk} monthly listeners"
            return ({"raw": raw_text, "value": val} if return_raw else val)

        # If not found
        return ({"raw": None, "value": 0} if return_raw else 0)
    except Exception:
        return ({"raw": None, "value": 0} if return_raw else 0)

def compute_spotify_conversions_monthly(
    tickets_total: int,
    followers: int,
    monthly_streams: int,
    clip_to_100: bool = True
) -> dict:
    """
    Conversions using MONTHLY listeners as 'streams' (as requested):
      - Streams → Followers (%) = followers / monthly_streams * 100
      - Followers → Sales (%)   = tickets_total / followers * 100
      - Streams → Sales (%)     = tickets_total / monthly_streams * 100

    Note: These can exceed 100% mathematically; clip to [0,100] by default for display.
    """
    def pct(n, d):
        if not d:
            return None
        v = (n / d) * 100.0
        if clip_to_100:
            if v < 0: v = 0.0
            if v > 100: v = 100.0
        return round(v, 6)

    return {
        "streams_to_followers_pct": pct(followers, monthly_streams),
        "followers_to_sales_pct":   pct(tickets_total, followers),
        "streams_to_sales_pct":     pct(tickets_total, monthly_streams),
    }



# # ---------------- General utils ----------------
# def _safe_int(x) -> int:
#     try:
#         return int(x)
#     except Exception:
#         return 0

def _div_pct(n: int, d: int) -> Optional[float]:
    return round((n / d) * 100, 6) if d else None

# # ---------------- Channel resolving ----------------
# def resolve_channel_id(id_or_handle_or_name: str) -> Optional[str]:
#     """
#     Accept:
#       - UC... channel ID -> returned as-is
#       - @handle or name  -> resolved via Search API (uses quota)
#     """
#     if not id_or_handle_or_name:
#         return None
#     s = id_or_handle_or_name.strip()
#     if s.startswith("UC") and len(s) >= 10:
#         return s
#     if not YT_KEY:
#         return None
#     try:
#         params = {
#             "part": "snippet",
#             "q": s,
#             "type": "channel",
#             "maxResults": 1,
#             "key": YT_KEY,
#         }
#         r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=20)
#         r.raise_for_status()
#         items = r.json().get("items", [])
#         if not items:
#             return None
#         return items[0]["id"]["channelId"]
#     except Exception:
#         return None

# # ---------------- LIGHT MODE (lifetime stats) ----------------
# def get_youtube_channel_stats(id_or_handle_or_name: str) -> dict:
#     """
#     Lifetime channel statistics (views, subscribers, videoCount).
#     Graceful zeros if missing key or cannot resolve.
#     """
#     if not YT_KEY:
#         return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}
#     cid = resolve_channel_id(id_or_handle_or_name)
#     if not cid:
#         return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}
#     try:
#         url = "https://www.googleapis.com/youtube/v3/channels"
#         params = {"part": "statistics", "id": cid, "key": YT_KEY}
#         r = requests.get(url, params=params, timeout=20)
#         r.raise_for_status()
#         items = r.json().get("items", [])
#         if not items:
#             return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}
#         st = items[0].get("statistics", {}) or {}
#         return {
#             "viewCount": _safe_int(st.get("viewCount", 0)),
#             "subscriberCount": _safe_int(st.get("subscriberCount", 0)),
#             "videoCount": _safe_int(st.get("videoCount", 0)),
#         }
#     except Exception:
#         return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}

# ---------- YouTube: annual totals via official API (accurate integers) ----------
from datetime import datetime, timezone

def _iso_year_bounds(year: int):
    start = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    end   = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return start, end

def _yt_search_video_ids_for_year(channel_id: str, year: int, max_videos: int = 400) -> list[str]:
    """List video IDs for a channel in the given year using search.list (paged)."""
    published_after, published_before = _iso_year_bounds(year)
    ids = []
    page_token = None
    while True:
        params = {
            "part": "id",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": 50,
            "publishedAfter": published_after,
            "publishedBefore": published_before,
            "key": YT_KEY,
        }
        if page_token:
            params["pageToken"] = page_token
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=20)
        r.raise_for_status()
        js = r.json()
        batch = [it["id"]["videoId"] for it in js.get("items", []) if it.get("id", {}).get("videoId")]
        ids.extend(batch)
        if len(ids) >= max_videos:
            ids = ids[:max_videos]
            break
        page_token = js.get("nextPageToken")
        if not page_token:
            break
    return ids

def _yt_fetch_video_stats(video_ids: list[str]) -> list[dict]:
    """Fetch statistics for up to 50 video IDs using videos.list."""
    out = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        params = {"part": "statistics", "id": ",".join(chunk), "key": YT_KEY}
        r = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=20)
        r.raise_for_status()
        out.extend(r.json().get("items", []))
    return out

def yt_annual_stats(id_or_handle_or_name: str, year: int, include_comments: bool = True,
                    max_videos: int = 400, verify_with_html: bool = False, sample_n: int = 3) -> dict:
    """
    Accurate yearly totals via YouTube Data API:
      returns {views, likes, comments, video_count, _sample_raw?}
    - Sums statistics for all channel videos published in `year`.
    - Uses official API integers (no K/M parsing needed for math).
    - Optional: verify_with_html -> scrape a few sample watch pages and return raw label strings
      ('1.3M views', '862K likes', etc.) using your parse helpers.
    """
    if not YT_KEY:
        return {"views": 0, "likes": 0, "comments": 0, "video_count": 0, "_sample_raw": []}

    cid = resolve_channel_id(id_or_handle_or_name)
    if not cid:
        return {"views": 0, "likes": 0, "comments": 0, "video_count": 0, "_sample_raw": []}

    # 1) enumerate video IDs within the year
    vid_ids = _yt_search_video_ids_for_year(cid, int(year), max_videos=max_videos)
    if not vid_ids:
        return {"views": 0, "likes": 0, "comments": 0, "video_count": 0, "_sample_raw": []}

    # 2) batch-fetch statistics and sum
    total_views = 0
    total_likes = 0
    total_comments = 0
    stats_items = _yt_fetch_video_stats(vid_ids)
    for it in stats_items:
        st = it.get("statistics", {}) or {}
        # API provides precise strings (no K/M); convert safely
        total_views    += _safe_int(st.get("viewCount", 0))
        total_likes    += _safe_int(st.get("likeCount", 0))
        if include_comments:
            total_comments += _safe_int(st.get("commentCount", 0))

    result = {
        "views": total_views,
        "likes": total_likes,
        "comments": total_comments if include_comments else 0,
        "video_count": len(vid_ids),
    }

    # 3) optional HTML verification sample (raw display labels)
    if verify_with_html:
        samples = []
        for vid in vid_ids[:max(0, sample_n)]:
            try:
                watch_url = f"https://www.youtube.com/watch?v={vid}"
                html = requests.get(watch_url, headers={"User-Agent":"Mozilla/5.0"}, timeout=20).text
                raw_views = extract_first_count_text(html, "views")
                raw_likes = extract_first_count_text(html, "likes")
                raw_comms = extract_first_count_text(html, "comments")
                samples.append({
                    "videoId": vid,
                    "views_raw": raw_views,   "views_parsed": parse_abbrev_count(raw_views or ""),
                    "likes_raw": raw_likes,   "likes_parsed": parse_abbrev_count(raw_likes or ""),
                    "comments_raw": raw_comms,"comments_parsed": parse_abbrev_count(raw_comms or ""),
                })
            except Exception:
                pass
        result["_sample_raw"] = samples

    return result


# # ---------------- FULL MODE (year-specific sums) ----------------
# def yt_annual_stats(id_or_handle_or_name: str, year: int = 2023, include_comments: bool = True, page_cap: int = 500) -> dict:
#     """
#     Sum views/likes/(comments) for all videos on the channel published in `year`.
#     Uses Search API with channelId + date filter, then Videos API for statistics.
#     - `page_cap`: max videos to fetch to protect quota (default 500)
#     Returns: {"views": int, "likes": int, "comments": int, "video_count": int}
#     """
#     if not YT_KEY:
#         return {"views": 0, "likes": 0, "comments": 0, "video_count": 0}

#     cid = resolve_channel_id(id_or_handle_or_name)
#     if not cid:
#         return {"views": 0, "likes": 0, "comments": 0, "video_count": 0}

#     published_after  = f"{year}-01-01T00:00:00Z"
#     published_before = f"{year}-12-31T23:59:59Z"

#     # 1) search: get list of video IDs in the year
#     video_ids: List[str] = []
#     next_page = None
#     while True:
#         params = {
#             "part": "id",
#             "type": "video",
#             "channelId": cid,
#             "publishedAfter": published_after,
#             "publishedBefore": published_before,
#             "order": "date",
#             "maxResults": 50,
#             "key": YT_KEY,
#         }
#         if next_page:
#             params["pageToken"] = next_page
#         try:
#             rs = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=20)
#             rs.raise_for_status()
#             js = rs.json()
#             for it in js.get("items", []):
#                 vid = (it.get("id") or {}).get("videoId")
#                 if vid:
#                     video_ids.append(vid)
#             next_page = js.get("nextPageToken")
#             if not next_page or len(video_ids) >= page_cap:
#                 break
#         except Exception:
#             break

#     if not video_ids:
#         return {"views": 0, "likes": 0, "comments": 0, "video_count": 0}

#     # 2) videos.list: batch stats for up to 50 per call
#     views = likes = comments = 0
#     for i in range(0, min(len(video_ids), page_cap), 50):
#         chunk = video_ids[i:i+50]
#         params = {"part": "statistics", "id": ",".join(chunk), "key": YT_KEY}
#         try:
#             rv = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=20)
#             rv.raise_for_status()
#             for it in rv.json().get("items", []):
#                 st = it.get("statistics", {}) or {}
#                 views    += _safe_int(st.get("viewCount", 0)) # changed!
#                 likes    += _safe_int(st.get("likeCount", 0)) # changed!
#                 if include_comments:
#                     comments += _safe_int(st.get("commentCount", 0))
#         except Exception:
#             continue

#     return {"views": views, "likes": likes, "comments": comments if include_comments else 0, "video_count": min(len(video_ids), page_cap)}

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
