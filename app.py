# app.py — Light Mode (formatted % to 2 decimals)
import os
import streamlit as st
from dotenv import load_dotenv
import importlib

load_dotenv()
dp = importlib.import_module("data_pipeline")

st.set_page_config(page_title="2023 Artist Conversions — YouTube × TouringData", layout="wide")
st.title("2023 Artist Conversions — YouTube × TouringData")
st.caption("Mode: Light (lifetime YouTube stats)")

with st.sidebar:
    st.header("Inputs")
    artist = st.text_input("Artist name", value="Beyoncé")
    # Accepts UC… channel ID or @handle (your pipeline resolves @handle without using Search API)
    yt_channel_input = st.text_input("YouTube (ID / @handle)", value="@beyonce")
    go = st.button("Show Data")

def fmt_pct(v):
    """Render percentages to 2 decimals like 9.74% (or '-' if missing)."""
    if v is None:
        return "-"
    try:
        return f"{float(v):.2f}%"
    except Exception:
        return "-"

def fmt_num(v):
    return "-" if v in (None, 0) else f"{int(v):,}"

if go:
    try:
        tickets_2023 = dp.get_2023_tickets_sold_for_artist(artist)
        y_stats = dp.get_youtube_channel_stats(yt_channel_input)
        conv = dp.compute_conversions_percent(y_stats, tickets_2023)

        # KPIs
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tickets Sold (2023)", fmt_num(tickets_2023))
        c2.metric("YouTube Views (lifetime)", fmt_num(y_stats.get("viewCount", 0)))
        c3.metric("Subscribers", fmt_num(y_stats.get("subscriberCount", 0)))
        c4.metric("Videos", fmt_num(y_stats.get("videoCount", 0)))

        st.subheader("Conversion Rates (%)")
        c5, c6 = st.columns(2)
        c5.metric("Views → Sales", fmt_pct(conv.get("views_to_sales_pct")))
        c6.metric("Subs → Sales", fmt_pct(conv.get("subs_to_sales_pct")))

        st.subheader("Convenience Ratios")
        c7, c8 = st.columns(2)
        c7.metric("Sales per 1M Views", "-" if conv.get("sales_per_1m_views") is None else f"{conv['sales_per_1m_views']:.2f}")
        c8.metric("Sales per 10k Subs", "-" if conv.get("sales_per_10k_subs") is None else f"{conv['sales_per_10k_subs']:.2f}")

        if not os.getenv("YOUTUBE_API_KEY"):
            st.info("YouTube key not loaded from .env — YouTube numbers may be zero until you add a valid key.")

        st.caption("Tickets from TouringData’s 2023 year-end post (cached). YouTube stats are lifetime channel totals (Light Mode).")

    except Exception as e:
        st.error(f"Error: {e}")



# ----------- original code -------------------
# with st.sidebar:
#     st.header("Inputs")
#     artist = st.text_input("Artist name", value="Coldplay")
#     channel_id = st.text_input("YouTube Channel ID (optional; blank = auto search)", value="")
#     light_mode = st.checkbox("Light mode (views+likes only)", value=True)
#     go = st.button("Run")

# if go:
#     try:
#         st.subheader("2023 Tickets Sold (TouringData)")
#         tickets = get_2023_tickets_sold_for_artist(artist)
#         if tickets == 0:
#             st.warning("No 2023 ticket total found for this artist in TouringData’s year-end list.")
#         st.metric("Tickets Sold in 2023", f"{tickets:,}")

#         st.subheader("YouTube Totals for 2023 (videos published in 2023)")
#         if not channel_id:
#             with st.spinner("Finding YouTube channel..."):
#                 channel_id = yt_find_channel_id(artist)
#         if not channel_id:
#             st.error("Could not find a YouTube channel. Please paste a Channel ID.")
#         else:
#             with st.spinner("Fetching YouTube stats..."):
#                 yt_totals = yt_annual_stats(channel_id, year=2023, light_mode=light_mode)

#             c1, c2, c3, c4 = st.columns(4)
#             c1.metric("Views (2023)", f"{yt_totals.get('views',0):,}")
#             c2.metric("Likes (2023)", f"{yt_totals.get('likes',0):,}")
#             c3.metric("Comments (2023)", "-" if light_mode else f"{yt_totals.get('comments',0):,}")
#             c4.metric("Videos Published (2023)", f"{yt_totals.get('video_count',0):,}")

#             st.subheader("Annual Conversions (2023)")
#             conv = compute_conversions_annual(yt_totals, tickets)
#             st.write({
#                 "Views → Likes (%)": conv["conv_views_likes_pct"],
#                 "Views → Sales (%)": conv["conv_views_sales_pct"],
#                 "Likes → Sales (%)": conv["conv_likes_sales_pct"],
#                 "Comments → Sales (%)": "-" if light_mode else conv["conv_comments_sales_pct"],
#             })
#     except Exception as e:
#         st.error(f"Error: {e}")

