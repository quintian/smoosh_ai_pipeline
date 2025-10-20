# app.py — presentation-first; robust to missing optional helpers

import os
import importlib
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
dp = importlib.import_module("data_pipeline")

# -------------- UI helpers --------------
st.set_page_config(page_title="Artist Value Conversion — From Social to Commercial", layout="wide")
st.title("Artist Value Conversion - From Social to Commercial")

def fmt_pct(v):
    if v is None:
        return "-"
    try:
        return f"{float(v):.2f}%"
    except Exception:
        return "-"

def fmt_num(v):
    try:
        iv = int(v)
        return f"{iv:,}"
    except Exception:
        return "-"

def row(label, value):
    st.markdown(
        f"<div style='display:flex; justify-content:space-between; "
        f"border-bottom:1px solid rgba(255,255,255,0.08); padding:8px 0;'>"
        f"<div style='font-weight:600;'>{label}</div>"
        f"<div style='font-size:20px; font-weight:500;'>{value}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

def safe_full_conversions(yt_year: dict, tickets_2023: int):
    """
    Prefer data_pipeline.compute_full_conversions_percent if present.
    Otherwise compute the three full-mode % locally (simple + transparent).
    """
    if hasattr(dp, "compute_full_conversions_percent"):
        try:
            return dp.compute_full_conversions_percent(yt_year, tickets_2023)
        except Exception:
            pass
    # Fallback math (only if pipeline helper missing)
    views = int(yt_year.get("views", 0) or 0)
    likes = int(yt_year.get("likes", 0) or 0)
    comments = int(yt_year.get("comments", 0) or 0)
    tix = int(tickets_2023 or 0)

    def pct(n, d):
        return round((n / d) * 100, 6) if d else None

    return {
        "views_to_likes_pct": pct(likes, views),
        "likes_to_sales_pct": pct(tix, likes),
        "comments_to_sales_pct": pct(tix, comments),
    }

# -------------- Sidebar inputs --------------
with st.sidebar:
    st.header("Inputs")
    artist = st.text_input("Artist name", value="Beyoncé")
     # in sidebar
    yt_channel_input = st.text_input("YouTube (ID / @handle / name) — comma-separated for multiple",
                                            value="@beyonce, @BeyonceVEVO")

    # yt_channel_input = st.text_input("YouTube (ID / @handle / name)", value="@beyonce")
    full_mode = st.toggle("Full Mode (2023 content)", value=True)
    year = st.number_input("Year (Full Mode)", min_value=2006, max_value=2030, value=2023, step=1, disabled=not full_mode)
    show_raw_labels = st.toggle("Debug: show raw YouTube labels", value=False, help="Show a few sample '1.3M views' labels parsed from watch pages.")
    go = st.button("Show Data")
     # in sidebar
   


# -------------- Main --------------
if go:
    try:
        # Tickets (TouringData cache)
        tickets_2023 = dp.get_2023_tickets_sold_for_artist(artist)

        if full_mode:
            st.caption("Mode: Full (2023-only YouTube stats)")
            
           
            # in full mode block, replace yt_year call:
            yt_year = dp.yt_annual_stats_multi(
                yt_channel_input,
                int(year),
                include_comments=True,
                verify_with_html=show_raw_labels,
                max_videos=400
            )


            # Accurate annual totals via official API (your updated pipeline)
            # yt_year = dp.yt_annual_stats(
            #     yt_channel_input,
            #     int(year),
            #     include_comments=True,
            #     verify_with_html=show_raw_labels,  # optional sample of raw labels
            #     max_videos=400
            # )

            # Lifetime (for auxiliary conversions shown below)
            yt_life = dp.get_youtube_channel_stats(yt_channel_input)

            # Conversions (prefer pipeline; otherwise safe fallback)
            conv_full  = safe_full_conversions(yt_year, tickets_2023)
            conv_light = dp.compute_conversions_percent(yt_life, tickets_2023)

            # ----- Stats -----
            st.subheader("📊 Stats")
            row("Tickets Sold (2023)", fmt_num(tickets_2023))
            row(f"Views ({year})", fmt_num(yt_year.get("views", 0)))
            row(f"Likes ({year})", fmt_num(yt_year.get("likes", 0)))
            row(f"Comments ({year})", fmt_num(yt_year.get("comments", 0)))
            row(f"Videos in {year}", fmt_num(yt_year.get("video_count", 0)))

            # Optional raw samples table
            if show_raw_labels and yt_year.get("_sample_raw"):
                import pandas as pd
                st.markdown("<div style='margin-top:8px; opacity:0.8;'>Raw sample labels from watch pages (verification only)</div>", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(yt_year["_sample_raw"]), use_container_width=True, hide_index=True)

            # ----- Conversion Rates -----
            st.subheader("📈 Conversion Rates")
            row("Views → Likes", fmt_pct(conv_full.get("views_to_likes_pct")))
            row("Likes → Sales", fmt_pct(conv_full.get("likes_to_sales_pct")))
            row("Comments → Sales", fmt_pct(conv_full.get("comments_to_sales_pct")))
            row("Views → Sales (lifetime views)", fmt_pct(conv_light.get("views_to_sales_pct")))
            row("Subs → Sales (lifetime subs)", fmt_pct(conv_light.get("subs_to_sales_pct")))
            row("Sales per 1M Views (lifetime)", f"{conv_light['sales_per_1m_views']:.2f}" if conv_light.get("sales_per_1m_views") is not None else "-")
            row("Sales per 10k Subs (lifetime)", f"{conv_light['sales_per_10k_subs']:.2f}" if conv_light.get("sales_per_10k_subs") is not None else "-")

        else:
            st.caption("Mode: Light (lifetime YouTube stats)")
            yt_life = dp.get_youtube_channel_stats(yt_channel_input)
            conv_light = dp.compute_conversions_percent(yt_life, tickets_2023)

            st.subheader("📊 Stats")
            row("Tickets Sold (2023)", fmt_num(tickets_2023))
            row("YouTube Views (lifetime)", fmt_num(yt_life.get("viewCount", 0)))
            row("Subscribers (lifetime)", fmt_num(yt_life.get("subscriberCount", 0)))
            row("Videos (lifetime)", fmt_num(yt_life.get("videoCount", 0)))

            st.subheader("📈 Conversion Rates")
            row("Views → Sales", fmt_pct(conv_light.get("views_to_sales_pct")))
            row("Subs → Sales", fmt_pct(conv_light.get("subs_to_sales_pct")))
            row("Sales per 1M Views", f"{conv_light['sales_per_1m_views']:.2f}" if conv_light.get("sales_per_1m_views") is not None else "-")
            row("Sales per 10k Subs", f"{conv_light['sales_per_10k_subs']:.2f}" if conv_light.get("sales_per_10k_subs") is not None else "-")

        # ----- Spotify block (monthly listeners as streams) -----
        with st.expander("🎧 Spotify (followers + monthly listeners as streams)", expanded=True):
            sp_followers = dp.spotify_artist_followers(artist)
            ml_info = dp.spotify_monthly_listeners_scrape(artist, return_raw=True)
            monthly_listeners = ml_info.get("value", 0)
            monthly_listeners_raw = ml_info.get("raw") or "-"

            sp_conv = dp.compute_spotify_conversions_monthly(
                tickets_total=tickets_2023,
                followers=sp_followers,
                monthly_streams=monthly_listeners,
                clip_to_100=True
            )

            st.subheader("Stats")
            row("Followers (Spotify)", fmt_num(sp_followers))
            row("Monthly Listeners (raw)", monthly_listeners_raw)
            row("Monthly Listeners (parsed)", fmt_num(monthly_listeners))

            st.subheader("Conversion Rates")
            row("Streams → Followers", fmt_pct(sp_conv.get("streams_to_followers_pct")))
            row("Followers → Sales",   fmt_pct(sp_conv.get("followers_to_sales_pct")))
            row("Streams → Sales",     fmt_pct(sp_conv.get("streams_to_sales_pct")))

        # Footnote
        st.caption(
            "Tickets from TouringData’s 2023 year-end post (cached). "
            "Full Mode uses YouTube Data API per-video statistics for the selected year; "
            "Light Mode uses lifetime channel aggregates. "
            "Spotify followers from Web API; monthly listeners scraped from public artist page."
        )

        # Friendly env hints
        if not os.getenv("YOUTUBE_API_KEY"):
            st.info("YouTube key not loaded from .env — YouTube numbers will be zero until you add a valid key.")
        if not (os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET")):
            st.info("Spotify client credentials not found in .env — followers may show as zero.")

    except Exception as e:
        st.error(f"Error: {e}")


# # app.py — aligned two-column layout, new title
# import os, importlib
# import streamlit as st
# from dotenv import load_dotenv

# load_dotenv()
# dp = importlib.import_module("data_pipeline")

# st.set_page_config(page_title="Artist Value Conversion - From Social to Commercial", layout="wide")
# st.title("Artist Value Conversion - From Social to Commercial")

# with st.sidebar:
#     st.header("Inputs")
#     artist = st.text_input("Artist name", value="Beyoncé")
#     yt_channel_input = st.text_input("YouTube (ID / @handle / name)", value="@beyonce")
#     full_mode = st.toggle("Full Mode (2023 content)", value=True)
#     year = st.number_input("Year (Full Mode)", min_value=2006, max_value=2025, value=2023, step=1, disabled=not full_mode)
#     go = st.button("Show Data")

#     # ... keep your current imports and setup ...

# # def fmt_pct(v):
# #     if v is None: return "-"
# #     try: return f"{float(v):.2f}%"
# #     except: return "-"

# # def fmt_num(v):
# #     return "-" if v in (None, 0) else f"{int(v):,}"

# # def row(label, value):
# #     st.markdown(
# #         f"<div style='display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); padding:6px 0;'>"
# #         f"<div style='font-weight:600;'>{label}</div>"
# #         f"<div style='font-size:22px; font-weight:500;'>{value}</div>"
# #         f"</div>",
# #         unsafe_allow_html=True,
# #     )
    
# def fmt_pct(v):
#     if v is None:
#         return "-"
#     try:
#         return f"{float(v):.2f}%"
#     except Exception:
#         return "-"

# def fmt_num(v):
#     return "-" if v in (None, 0) else f"{int(v):,}"

# def row(label, value):
#     st.markdown(
#         f"<div style='display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); padding:6px 0;'>"
#         f"<div style='font-weight:600;'>{label}</div>"
#         f"<div style='font-size:22px; font-weight:500;'>{value}</div>"
#         f"</div>",
#         unsafe_allow_html=True,
#     )

# if go:
#     try:
#         tickets_2023 = dp.get_2023_tickets_sold_for_artist(artist)

#         if full_mode:
#             st.caption("Mode: Full (2023-only YouTube stats)")
#             yt_year = dp.yt_annual_stats(yt_channel_input, int(year), include_comments=True)
#             y_stats = dp.get_youtube_channel_stats(yt_channel_input)
#             conv_full  = dp.compute_full_conversions_percent(yt_year, tickets_2023)
#             conv_light = dp.compute_conversions_percent(y_stats, tickets_2023)

#             # --- Top block ---
#             st.subheader("📊 Stats")
#             row("Tickets Sold (2023)", fmt_num(tickets_2023))
#             row(f"Views ({year})", fmt_num(yt_year.get("views", 0)))
#             row(f"Likes ({year})", fmt_num(yt_year.get("likes", 0)))
#             row(f"Comments ({year})", fmt_num(yt_year.get("comments", 0)))

#             # --- Bottom block ---
#             st.subheader("📈 Conversion Rates")
#             row("Views → Likes", fmt_pct(conv_full.get("views_to_likes_pct")))
#             row("Likes → Sales", fmt_pct(conv_full.get("likes_to_sales_pct")))
#             row("Comments → Sales", fmt_pct(conv_full.get("comments_to_sales_pct")))
#             row("Views → Sales (lifetime views)", fmt_pct(conv_light.get("views_to_sales_pct")))
#             row("Subs → Sales (lifetime subs)", fmt_pct(conv_light.get("subs_to_sales_pct")))
#             row("Sales per 1M Views", "-" if conv_light.get("sales_per_1m_views") is None else f"{conv_light['sales_per_1m_views']:.2f}")
#             row("Sales per 10k Subs", "-" if conv_light.get("sales_per_10k_subs") is None else f"{conv_light['sales_per_10k_subs']:.2f}")

#             # inside your `if go:` block, AFTER your current sections:
#             with st.expander("🎧 Spotify (followers & monthly listeners proxy)", expanded=True):
#                 sp_followers = dp.spotify_artist_followers(artist)                      # name or artist URL/ID
#                 sp_year_streams = dp.spotify_yearly_streams_proxy(artist, True)         # monthly listeners * 12
#                 sp_conv = dp.compute_spotify_conversions(tickets_2023, sp_followers, sp_year_streams)

#                 # Stats (aligned rows)
#                 st.subheader("Stats")
#                 row("Followers (Spotify)", fmt_num(sp_followers))
#                 row("Monthly Listeners (proxy)", fmt_num(sp_conv.get("monthly_listeners", 0)))
#                 row("Yearly Streams (proxy = monthly * 12)", fmt_num(sp_year_streams))

#                 # Conversion Rates
#                 st.subheader("Conversion Rates")
#                 row("Streams → Followers", fmt_pct(sp_conv.get("streams_to_followers_pct")))
#                 row("Followers → Sales",   fmt_pct(sp_conv.get("followers_to_sales_pct")))
#                 row("Streams → Sales",     fmt_pct(sp_conv.get("streams_to_sales_pct")))
            
#         else:
#             st.caption("Mode: Light (lifetime YouTube stats)")
#             y_stats = dp.get_youtube_channel_stats(yt_channel_input)
#             conv = dp.compute_conversions_percent(y_stats, tickets_2023)
#             st.subheader("📊 Stats")
#             row("Tickets Sold (2023)", fmt_num(tickets_2023))
#             row("YouTube Views (lifetime)", fmt_num(y_stats.get("viewCount", 0)))
#             row("Subscribers", fmt_num(y_stats.get("subscriberCount", 0)))
#             row("Videos", fmt_num(y_stats.get("videoCount", 0)))

#             st.subheader("📈 Conversion Rates")
#             row("Views → Sales", fmt_pct(conv.get("views_to_sales_pct")))
#             row("Subs → Sales", fmt_pct(conv.get("subs_to_sales_pct")))
#             row("Sales per 1M Views", "-" if conv.get("sales_per_1m_views") is None else f"{conv['sales_per_1m_views']:.2f}")
#             row("Sales per 10k Subs", "-" if conv.get("sales_per_10k_subs") is None else f"{conv['sales_per_10k_subs']:.2f}")
            

#         if not os.getenv("YOUTUBE_API_KEY"):
#             st.info("YouTube key not loaded from .env — YouTube numbers will be zero until you add a valid key.")

#         st.caption(
#             "Tickets from TouringData’s 2023 year-end post (cached). "
#             "Full Mode sums YouTube stats for videos published in the selected year; "
#             "Light conversions use lifetime channel aggregates."
#         )

#     except Exception as e:
#         st.error(f"Error: {e}")
        





