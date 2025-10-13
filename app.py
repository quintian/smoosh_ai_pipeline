# app.py — aligned two-column layout, new title
import os, importlib
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
dp = importlib.import_module("data_pipeline")

st.set_page_config(page_title="Artist Value Conversion - From Social to Commercial", layout="wide")
st.title("Artist Value Conversion - From Social to Commercial")

with st.sidebar:
    st.header("Inputs")
    artist = st.text_input("Artist name", value="Beyoncé")
    yt_channel_input = st.text_input("YouTube (ID / @handle / name)", value="@beyonce")
    full_mode = st.toggle("Full Mode (2023 content)", value=True)
    year = st.number_input("Year (Full Mode)", min_value=2006, max_value=2025, value=2023, step=1, disabled=not full_mode)
    go = st.button("Show Data")

    # ... keep your current imports and setup ...

# def fmt_pct(v):
#     if v is None: return "-"
#     try: return f"{float(v):.2f}%"
#     except: return "-"

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
    
def fmt_pct(v):
    if v is None:
        return "-"
    try:
        return f"{float(v):.2f}%"
    except Exception:
        return "-"

def fmt_num(v):
    return "-" if v in (None, 0) else f"{int(v):,}"

def row(label, value):
    st.markdown(
        f"<div style='display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); padding:6px 0;'>"
        f"<div style='font-weight:600;'>{label}</div>"
        f"<div style='font-size:22px; font-weight:500;'>{value}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

if go:
    try:
        tickets_2023 = dp.get_2023_tickets_sold_for_artist(artist)

        if full_mode:
            st.caption("Mode: Full (2023-only YouTube stats)")
            yt_year = dp.yt_annual_stats(yt_channel_input, int(year), include_comments=True)
            y_stats = dp.get_youtube_channel_stats(yt_channel_input)
            conv_full  = dp.compute_full_conversions_percent(yt_year, tickets_2023)
            conv_light = dp.compute_conversions_percent(y_stats, tickets_2023)

            # --- Top block ---
            st.subheader("📊 Stats")
            row("Tickets Sold (2023)", fmt_num(tickets_2023))
            row(f"Views ({year})", fmt_num(yt_year.get("views", 0)))
            row(f"Likes ({year})", fmt_num(yt_year.get("likes", 0)))
            row(f"Comments ({year})", fmt_num(yt_year.get("comments", 0)))

            # --- Bottom block ---
            st.subheader("📈 Conversion Rates")
            row("Views → Likes", fmt_pct(conv_full.get("views_to_likes_pct")))
            row("Likes → Sales", fmt_pct(conv_full.get("likes_to_sales_pct")))
            row("Comments → Sales", fmt_pct(conv_full.get("comments_to_sales_pct")))
            row("Views → Sales (lifetime views)", fmt_pct(conv_light.get("views_to_sales_pct")))
            row("Subs → Sales (lifetime subs)", fmt_pct(conv_light.get("subs_to_sales_pct")))
            row("Sales per 1M Views", "-" if conv_light.get("sales_per_1m_views") is None else f"{conv_light['sales_per_1m_views']:.2f}")
            row("Sales per 10k Subs", "-" if conv_light.get("sales_per_10k_subs") is None else f"{conv_light['sales_per_10k_subs']:.2f}")

            # inside your `if go:` block, AFTER your current sections:
            with st.expander("🎧 Spotify (followers & monthly listeners proxy)", expanded=True):
                sp_followers = dp.spotify_artist_followers(artist)                      # name or artist URL/ID
                sp_year_streams = dp.spotify_yearly_streams_proxy(artist, True)         # monthly listeners * 12
                sp_conv = dp.compute_spotify_conversions(tickets_2023, sp_followers, sp_year_streams)

                # Stats (aligned rows)
                st.subheader("Stats")
                row("Followers (Spotify)", fmt_num(sp_followers))
                row("Monthly Listeners (proxy)", fmt_num(sp_conv.get("monthly_listeners", 0)))
                row("Yearly Streams (proxy = monthly * 12)", fmt_num(sp_year_streams))

                # Conversion Rates
                st.subheader("Conversion Rates")
                row("Streams → Followers", fmt_pct(sp_conv.get("streams_to_followers_pct")))
                row("Followers → Sales",   fmt_pct(sp_conv.get("followers_to_sales_pct")))
                row("Streams → Sales",     fmt_pct(sp_conv.get("streams_to_sales_pct")))
            
        else:
            st.caption("Mode: Light (lifetime YouTube stats)")
            y_stats = dp.get_youtube_channel_stats(yt_channel_input)
            conv = dp.compute_conversions_percent(y_stats, tickets_2023)
            st.subheader("📊 Stats")
            row("Tickets Sold (2023)", fmt_num(tickets_2023))
            row("YouTube Views (lifetime)", fmt_num(y_stats.get("viewCount", 0)))
            row("Subscribers", fmt_num(y_stats.get("subscriberCount", 0)))
            row("Videos", fmt_num(y_stats.get("videoCount", 0)))

            st.subheader("📈 Conversion Rates")
            row("Views → Sales", fmt_pct(conv.get("views_to_sales_pct")))
            row("Subs → Sales", fmt_pct(conv.get("subs_to_sales_pct")))
            row("Sales per 1M Views", "-" if conv.get("sales_per_1m_views") is None else f"{conv['sales_per_1m_views']:.2f}")
            row("Sales per 10k Subs", "-" if conv.get("sales_per_10k_subs") is None else f"{conv['sales_per_10k_subs']:.2f}")
            

        if not os.getenv("YOUTUBE_API_KEY"):
            st.info("YouTube key not loaded from .env — YouTube numbers will be zero until you add a valid key.")

        st.caption(
            "Tickets from TouringData’s 2023 year-end post (cached). "
            "Full Mode sums YouTube stats for videos published in the selected year; "
            "Light conversions use lifetime channel aggregates."
        )

    except Exception as e:
        st.error(f"Error: {e}")
        






# # app.py — Light + Full Modes with single-column lists in Full Mode
# import os, importlib
# import streamlit as st
# from dotenv import load_dotenv

# load_dotenv()
# dp = importlib.import_module("data_pipeline")

# st.set_page_config(page_title="2023 Artist Conversions — YouTube × TouringData", layout="wide")
# st.title("2023 Artist Conversions — YouTube × TouringData")

# with st.sidebar:
#     st.header("Inputs")
#     artist = st.text_input("Artist name", value="Beyoncé")
#     yt_channel_input = st.text_input("YouTube (ID / @handle / name)", value="@beyonce")
#     full_mode = st.toggle("Full Mode (2023 content)", value=True, help="Sum views/likes/comments for videos published in the selected year")
#     year = st.number_input("Year (Full Mode)", min_value=2006, max_value=2025, value=2023, step=1, disabled=not full_mode)
#     go = st.button("Show Data")

# def fmt_pct(v):
#     if v is None:
#         return "-"
#     try:
#         return f"{float(v):.2f}%"
#     except Exception:
#         return "-"

# def fmt_num(v):
#     return "-" if v in (None, 0) else f"{int(v):,}"

# def line(label: str, value: str):
#     st.markdown(
#         f"<div style='padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.08)'>"
#         f"<div style='font-weight:600'>{label}</div>"
#         f"<div style='font-size:26px; line-height:1.2'>{value}</div>"
#         f"</div>",
#         unsafe_allow_html=True,
#     )

# if go:
#     try:
#         tickets_2023 = dp.get_2023_tickets_sold_for_artist(artist)

#         if full_mode:
#             st.caption("Mode: Full (2023-only content sums)")
#             # year-specific YT totals
#             yt_year = dp.yt_annual_stats(yt_channel_input, int(year), include_comments=True)
#             # lifetime YT (needed for Light conversions)
#             y_stats = dp.get_youtube_channel_stats(yt_channel_input)

#             # --- Top: Stats (single column) ---
#             st.subheader("Stats")
#             line("Tickets Sold (2023)", fmt_num(tickets_2023))
#             line(f"Views ({year})", fmt_num(yt_year.get("views", 0)))
#             line(f"Likes ({year})", fmt_num(yt_year.get("likes", 0)))
#             line(f"Comments ({year})", fmt_num(yt_year.get("comments", 0)))

#             # --- Bottom: Conversion rates (Full + Light in one list) ---
#             conv_full  = dp.compute_full_conversions_percent(yt_year, tickets_2023)
#             conv_light = dp.compute_conversions_percent(y_stats, tickets_2023)

#             st.subheader("Conversion Rates")
#             line("Views → Likes", fmt_pct(conv_full.get("views_to_likes_pct")))
#             line("Likes → Sales", fmt_pct(conv_full.get("likes_to_sales_pct")))
#             line("Comments → Sales", fmt_pct(conv_full.get("comments_to_sales_pct")))
#             line("Views → Sales (lifetime views)", fmt_pct(conv_light.get("views_to_sales_pct")))
#             line("Subs → Sales (lifetime subs)", fmt_pct(conv_light.get("subs_to_sales_pct")))
#             # convenience ratios (not %)
#             sales_per_1m = conv_light.get("sales_per_1m_views")
#             sales_per_10k = conv_light.get("sales_per_10k_subs")
#             line("Sales per 1M Views", "-" if sales_per_1m is None else f"{sales_per_1m:.2f}")
#             line("Sales per 10k Subs", "-" if sales_per_10k is None else f"{sales_per_10k:.2f}")

#         else:
#             # Light mode unchanged (grid KPIs + conversions)
#             st.caption("Mode: Light (lifetime YouTube stats)")
#             y_stats = dp.get_youtube_channel_stats(yt_channel_input)
#             c1, c2, c3, c4 = st.columns(4)
#             c1.metric("Tickets Sold (2023)", fmt_num(tickets_2023))
#             c2.metric("YouTube Views (lifetime)", fmt_num(y_stats.get("viewCount", 0)))
#             c3.metric("Subscribers", fmt_num(y_stats.get("subscriberCount", 0)))
#             c4.metric("Videos", fmt_num(y_stats.get("videoCount", 0)))
#             conv = dp.compute_conversions_percent(y_stats, tickets_2023)
#             st.subheader("Conversion Rates (%)")
#             a, b = st.columns(2)
#             a.metric("Views → Sales", fmt_pct(conv.get("views_to_sales_pct")))
#             b.metric("Subs → Sales", fmt_pct(conv.get("subs_to_sales_pct")))
#             st.subheader("Convenience Ratios")
#             d, e = st.columns(2)
#             d.metric("Sales per 1M Views", "-" if conv.get("sales_per_1m_views") is None else f"{conv['sales_per_1m_views']:.2f}")
#             e.metric("Sales per 10k Subs", "-" if conv.get("sales_per_10k_subs") is None else f"{conv['sales_per_10k_subs']:.2f}")

#         if not os.getenv("YOUTUBE_API_KEY"):
#             st.info("YouTube key not loaded from .env — YouTube numbers will be zero until you add a valid key.")

#         st.caption(
#             "Tickets from TouringData’s 2023 year-end post (cached). "
#             "Full Mode sums YouTube stats for videos published in the selected year; "
#             "Light conversions use lifetime channel aggregates."
#         )

#     except Exception as e:
#         st.error(f"Error: {e}")


# # app.py — Light + Full Modes
# import os, importlib
# import streamlit as st
# from dotenv import load_dotenv

# load_dotenv()
# dp = importlib.import_module("data_pipeline")

# st.set_page_config(page_title="2023 Artist Conversions — YouTube × TouringData", layout="wide")
# st.title("2023 Artist Conversions — YouTube × TouringData")

# with st.sidebar:
#     st.header("Inputs")
#     artist = st.text_input("Artist name", value="Beyoncé")
#     yt_channel_input = st.text_input("YouTube (ID / @handle / name)", value="@beyonce")
#     full_mode = st.toggle("Full Mode (2023 content)", value=False, help="Sum views/likes/comments for videos published in 2023")
#     year = st.number_input("Year (Full Mode)", min_value=2006, max_value=2025, value=2023, step=1, disabled=not full_mode)
#     go = st.button("Show Data")

# def fmt_pct(v):
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

#         if full_mode:
#             st.caption("Mode: Full (2023-only content sums)")
#             yt_year = dp.yt_annual_stats(yt_channel_input, int(year), include_comments=True)
#             c1, c2, c3, c4 = st.columns(4)
#             c1.metric("Tickets Sold (2023)", fmt_num(tickets_2023))
#             c2.metric(f"Views ({year})", fmt_num(yt_year.get("views", 0)))
#             c3.metric(f"Likes ({year})", fmt_num(yt_year.get("likes", 0)))
#             c4.metric(f"Comments ({year})", fmt_num(yt_year.get("comments", 0)))

#             conv = dp.compute_full_conversions_percent(yt_year, tickets_2023)
#             st.subheader("Conversion Rates (%)")
#             a, b, c = st.columns(3)
#             a.metric("Views → Likes", fmt_pct(conv.get("views_to_likes_pct")))
#             b.metric("Likes → Sales", fmt_pct(conv.get("likes_to_sales_pct")))
#             c.metric("Comments → Sales", fmt_pct(conv.get("comments_to_sales_pct")))
#         else:
#             st.caption("Mode: Light (lifetime YouTube stats)")
#             y_stats = dp.get_youtube_channel_stats(yt_channel_input)
#             c1, c2, c3, c4 = st.columns(4)
#             c1.metric("Tickets Sold (2023)", fmt_num(tickets_2023))
#             c2.metric("YouTube Views (lifetime)", fmt_num(y_stats.get("viewCount", 0)))
#             c3.metric("Subscribers", fmt_num(y_stats.get("subscriberCount", 0)))
#             c4.metric("Videos", fmt_num(y_stats.get("videoCount", 0)))

#             conv = dp.compute_conversions_percent(y_stats, tickets_2023)
#             st.subheader("Conversion Rates (%)")
#             a, b = st.columns(2)
#             a.metric("Views → Sales", fmt_pct(conv.get("views_to_sales_pct")))
#             b.metric("Subs → Sales", fmt_pct(conv.get("subs_to_sales_pct")))

#             st.subheader("Convenience Ratios")
#             d, e = st.columns(2)
#             d.metric("Sales per 1M Views", "-" if conv.get("sales_per_1m_views") is None else f"{conv['sales_per_1m_views']:.2f}")
#             e.metric("Sales per 10k Subs", "-" if conv.get("sales_per_10k_subs") is None else f"{conv['sales_per_10k_subs']:.2f}")

#         if not os.getenv("YOUTUBE_API_KEY"):
#             st.info("YouTube key not loaded from .env — YouTube numbers will be zero until you add a valid key.")

#         st.caption("Tickets from TouringData’s 2023 year-end post (cached). In Full Mode we sum stats for videos published in the selected year.")

#     except Exception as e:
#         st.error(f"Error: {e}")



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



