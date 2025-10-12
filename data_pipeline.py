import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
TM_KEY = os.getenv("TICKETMASTER_API_KEY", "")
YT_KEY = os.getenv("YOUTUBE_API_KEY", "")

def get_ticketmaster_events(artist: str, size: int = 25) -> pd.DataFrame:
    """Fetch upcoming events for an artist from Ticketmaster Discovery API."""
    if not TM_KEY:
        raise RuntimeError("Missing TICKETMASTER_API_KEY in .env")
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": TM_KEY,
        "keyword": artist,
        "size": size
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    payload = r.json()
    events = payload.get("_embedded", {}).get("events", [])
    if not events:
        return pd.DataFrame(columns=["event_id","event_name","city","country","venue","start","url"])
    rows = []
    for ev in events:
        venues = ev.get("_embedded", {}).get("venues", [{}])
        v = venues[0] if venues else {}
        city = (v.get("city") or {}).get("name")
        country = (v.get("country") or {}).get("name")
        venue = v.get("name")
        start = (ev.get("dates") or {}).get("start", {}).get("dateTime") or (ev.get("dates") or {}).get("start", {}).get("localDate")
        rows.append({
            "event_id": ev.get("id"),
            "event_name": ev.get("name"),
            "city": city,
            "country": country,
            "venue": venue,
            "start": start,
            "url": ev.get("url")
        })
    return pd.DataFrame(rows)

def get_youtube_channel_stats(channel_id: str) -> dict:
    """Fetch basic YouTube channel statistics (views, subscribers, videoCount)."""
    if not YT_KEY:
        raise RuntimeError("Missing YOUTUBE_API_KEY in .env")
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {"part": "statistics", "id": channel_id, "key": YT_KEY}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json().get("items", [])
    if not data:
        return {"viewCount": 0, "subscriberCount": 0, "videoCount": 0}
    stats = data[0].get("statistics", {})
    return {
        "viewCount": int(stats.get("viewCount", 0)),
        "subscriberCount": int(stats.get("subscriberCount", 0)),
        "videoCount": int(stats.get("videoCount", 0))
    }

def compute_simple_metrics(y_stats: dict, events_df: pd.DataFrame) -> dict:
    """Compute simple artist-level ratios that look like conversions (no user IDs)."""
    views = y_stats.get("viewCount", 0) or 0
    subs = y_stats.get("subscriberCount", 0) or 0
    vids = y_stats.get("videoCount", 0) or 0
    ev = len(events_df.index) if events_df is not None else 0
    return {
        "youtube_views_total": views,
        "youtube_subscribers": subs,
        "youtube_videos": vids,
        "events_listed": ev,
        "views_per_event": round(views / ev, 2) if ev else None
    }
