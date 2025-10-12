import streamlit as st
import pandas as pd
from data_pipeline import get_ticketmaster_events, get_youtube_channel_stats, compute_simple_metrics

st.set_page_config(page_title="Artist Insights Dashboard", layout="wide")
st.title("Artist Insights Dashboard (Ticketmaster + YouTube)")

with st.sidebar:
    st.header("Inputs")
    artist = st.text_input("Artist name", value="Imagine Dragons")
    # Example channel IDs to try: Ed Sheeran = UC0C-w0YjGpqDXGB8IHb662A , Billie Eilish = UCiGm_E4ZwYSHV3bcW1pnSeQ
    yt_channel_id = st.text_input("YouTube Channel ID", value="UCiGm_E4ZwYSHV3bcW1pnSeQ")
    size = st.number_input("Max events to fetch", min_value=1, max_value=200, value=25, step=1)
    go = st.button("Fetch Data")

if go:
    try:
        with st.spinner("Fetching Ticketmaster events..."):
            events_df = get_ticketmaster_events(artist, size=size)

        with st.spinner("Fetching YouTube stats..."):
            y_stats = get_youtube_channel_stats(yt_channel_id)

        metrics = compute_simple_metrics(y_stats, events_df)

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("YouTube Views", f"{metrics['youtube_views_total']:,}")
        col2.metric("Subscribers", f"{metrics['youtube_subscribers']:,}")
        col3.metric("Videos", f"{metrics['youtube_videos']:,}")
        col4.metric("Events Listed", f"{metrics['events_listed']:,}")
        col5.metric("Views per Event", "-" if metrics['views_per_event'] is None else f"{metrics['views_per_event']:,}")

        st.subheader("Upcoming Events")
        if events_df.empty:
            st.info("No events found for this artist/filters.")
        else:
            # clickable links
            show_df = events_df.copy()
            show_df["link"] = show_df["url"].apply(lambda u: f"[Open]({u})" if pd.notna(u) else "")
            st.dataframe(show_df[["event_name","city","country","venue","start","link"]], use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")

st.caption("Tip: replace the YouTube Channel ID with the artist’s official channel; add more sources later (SeatGeek, Spotify, Shopify) using the same pattern.")
