# app.py — Light + Full Modes
import os, importlib
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
dp = importlib.import_module("data_pipeline")

st.set_page_config(page_title="2023 Artist Conversions — YouTube × TouringData", layout="wide")
st.title("2023 Artist Conversions — YouTube × TouringData")

with st.sidebar:
    st.header("Inputs")
    artist = st.text_input("Artist name", value="Beyoncé")
    yt_channel_input = st.text_input("YouTube (ID / @handle / name)", value="@beyonce")
    full_mode = st.toggle("Full Mode (2023 content)", value=False, help="Sum views/likes/comments for videos published in 2023")
    year = st.number_input("Year (Full Mode)", min_value=2006, max_value=2025, value=2023, step=1, disabled=not full_mode)
    go = st.button("Show Data")

def fmt_pct(v):
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

        if full_mode:
            st.caption("Mode: Full (2023-only content sums)")
            yt_year = dp.yt_annual_stats(yt_channel_input, int(year), include_comments=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tickets Sold (2023)", fmt_num(tickets_2023))
            c2.metric(f"Views ({year})", fmt_num(yt_year.get("views", 0)))
            c3.metric(f"Likes ({year})", fmt_num(yt_year.get("likes", 0)))
            c4.metric(f"Comments ({year})", fmt_num(yt_year.get("comments", 0)))

            conv = dp.compute_full_conversions_percent(yt_year, tickets_2023)
            st.subheader("Conversion Rates (%)")
            a, b, c = st.columns(3)
            a.metric("Views → Likes", fmt_pct(conv.get("views_to_likes_pct")))
            b.metric("Likes → Sales", fmt_pct(conv.get("likes_to_sales_pct")))
            c.metric("Comments → Sales", fmt_pct(conv.get("comments_to_sales_pct")))
        else:
            st.caption("Mode: Light (lifetime YouTube stats)")
            y_stats = dp.get_youtube_channel_stats(yt_channel_input)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tickets Sold (2023)", fmt_num(tickets_2023))
            c2.metric("YouTube Views (lifetime)", fmt_num(y_stats.get("viewCount", 0)))
            c3.metric("Subscribers", fmt_num(y_stats.get("subscriberCount", 0)))
            c4.metric("Videos", fmt_num(y_stats.get("videoCount", 0)))

            conv = dp.compute_conversions_percent(y_stats, tickets_2023)
            st.subheader("Conversion Rates (%)")
            a, b = st.columns(2)
            a.metric("Views → Sales", fmt_pct(conv.get("views_to_sales_pct")))
            b.metric("Subs → Sales", fmt_pct(conv.get("subs_to_sales_pct")))

            st.subheader("Convenience Ratios")
            d, e = st.columns(2)
            d.metric("Sales per 1M Views", "-" if conv.get("sales_per_1m_views") is None else f"{conv['sales_per_1m_views']:.2f}")
            e.metric("Sales per 10k Subs", "-" if conv.get("sales_per_10k_subs") is None else f"{conv['sales_per_10k_subs']:.2f}")

        if not os.getenv("YOUTUBE_API_KEY"):
            st.info("YouTube key not loaded from .env — YouTube numbers will be zero until you add a valid key.")

        st.caption("Tickets from TouringData’s 2023 year-end post (cached). In Full Mode we sum stats for videos published in the selected year.")

    except Exception as e:
        st.error(f"Error: {e}")



# app.py — Light Mode (formatted % to 2 decimals)
# import os
# import streamlit as st
# from dotenv import load_dotenv
# import importlib

# load_dotenv()
# dp = importlib.import_module("data_pipeline")

# st.set_page_config(page_title="2023 Artist Conversions — YouTube × TouringData", layout="wide")
# st.title("2023 Artist Conversions — YouTube × TouringData")
# st.caption("Mode: Light (lifetime YouTube stats)")

# with st.sidebar:
#     st.header("Inputs")
#     artist = st.text_input("Artist name", value="Beyoncé")
#     # Accepts UC… channel ID or @handle (your pipeline resolves @handle without using Search API)
#     yt_channel_input = st.text_input("YouTube (ID / @handle)", value="@beyonce")
#     go = st.button("Show Data")

# def fmt_pct(v):
#     """Render percentages to 2 decimals like 9.74% (or '-' if missing)."""
#     if v is None:
#         return "-"
#     try:
#         return f"{float(v):.2f}%"
#     except Exception:
#         return "-"

# def fmt_num(v):
#     return "-" if v in (None, 0) else f"{int(v):,}"

# if go:
#     try:
#         tickets_2023 = dp.get_2023_tickets_sold_for_artist(artist)
#         y_stats = dp.get_youtube_channel_stats(yt_channel_input)
#         conv = dp.compute_conversions_percent(y_stats, tickets_2023)

#         # KPIs
#         c1, c2, c3, c4 = st.columns(4)
#         c1.metric("Tickets Sold (2023)", fmt_num(tickets_2023))
#         c2.metric("YouTube Views (lifetime)", fmt_num(y_stats.get("viewCount", 0)))
#         c3.metric("Subscribers", fmt_num(y_stats.get("subscriberCount", 0)))
#         c4.metric("Videos", fmt_num(y_stats.get("videoCount", 0)))

#         st.subheader("Conversion Rates (%)")
#         c5, c6 = st.columns(2)
#         c5.metric("Views → Sales", fmt_pct(conv.get("views_to_sales_pct")))
#         c6.metric("Subs → Sales", fmt_pct(conv.get("subs_to_sales_pct")))

#         st.subheader("Convenience Ratios")
#         c7, c8 = st.columns(2)
#         c7.metric("Sales per 1M Views", "-" if conv.get("sales_per_1m_views") is None else f"{conv['sales_per_1m_views']:.2f}")
#         c8.metric("Sales per 10k Subs", "-" if conv.get("sales_per_10k_subs") is None else f"{conv['sales_per_10k_subs']:.2f}")

#         if not os.getenv("YOUTUBE_API_KEY"):
#             st.info("YouTube key not loaded from .env — YouTube numbers may be zero until you add a valid key.")

#         st.caption("Tickets from TouringData’s 2023 year-end post (cached). YouTube stats are lifetime channel totals (Light Mode).")

#     except Exception as e:
#         st.error(f"Error: {e}")



