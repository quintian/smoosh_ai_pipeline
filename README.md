# Statement of Ownership
The methodology described for matching concert ticket sales and social media engagement metrics (including schema design, data sources, and conversion logic) is proprietary to the author Quinn Tian. It should not be disclosed, redistributed, or reused without your explicit written permission. Furthermore, the methodology may be experimental and not guaranteed to be accurate.

# 2023 Artist Conversions — YouTube × TouringData (Single-year, Single-source)

This demo computes **annual conversions** for any top touring artist in **2023**:
- Data source for sales: **TouringData 2023 Top Touring Artists** (one source, year-end total).
- Data source for engagement: **YouTube Data API** (sum views/likes/comments for all videos **published in 2023**).
- Conversions:
  - Views → Likes  = Likes / Views
  - Views → Sales  = TicketsSold / Views
  - Likes → Sales  = TicketsSold / Likes
  - Comments → Sales = TicketsSold / Comments

## Setup
Yes ✅ — you run each command separately, one line at a time:

1️⃣ conda create -n pipeline python=3.10 -y → creates the environment
2️⃣ conda activate pipeline → activates it
3️⃣ pip install -r requirements.txt → installs your project libraries
4️⃣ python -m streamlit run app.py → runs your dashboard

1. Install Python 3.10+ and create a virtual/conda env.
2. `pip install -r requirements.txt`
3. Create `.env` with your key:
YOUTUBE_API_KEY=YOUR_YOUTUBE_API_KEY

4. Run:


python -m streamlit run app.py


## How it works
- **Sales (2023):** Scrapes TouringData’s year-end 2023 list and extracts ticket totals per artist.
- **YouTube (2023):** Uses Search API to list videos published in 2023 and sums per-video statistics (views/likes/comments).
- **No double counting:** One single source for sales; one fixed year (2023) for both datasets.

## Usage
- In the left sidebar:
- Enter an **Artist name** (e.g., Coldplay, Beyoncé).
- Optionally paste a **YouTube Channel ID**; otherwise the app searches by name and uses the top channel.
- Click **Run**.

## Limitations
- TouringData’s list covers major artists; obscure artists may not appear (tickets sold = 0).
- YouTube API returns **lifetime** stats per video; we sum only videos **published in 2023** to approximate that year’s exposure.
- If the channel auto-search picks an unofficial channel, paste the correct Channel ID manually.


