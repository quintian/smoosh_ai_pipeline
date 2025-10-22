# Artist Value Converstion - From Social to Commercial

## Statement of Ownership
The methodology described for matching concert ticket sales and social media engagement metrics (including schema design, data sources, and conversion logic) is proprietary to the author Quinn Tian. It should not be disclosed, redistributed, or reused without any explicit written permission. Furthermore, the methodology may be experimental and not guaranteed to be accurate.

## Project Goal
This data pipeline is to demostrate the potential data sources and conversion metrics for Artist Value Converstion - from social interaction to commercial values.  

## Data Sources
- **Sales (2023) for Commercial Values:** Scrapes TouringData’s year-end 2023 list and extracts concert's ticket sales total for every artist.
- **YouTube (2023) for Social Interactions:** Uses Search API to list videos published in 2023 and sums per-video statistics (views/likes/comments).
- **Spotify Data for music streams:** Uses Spotify Aritist's followers and monthly listeners as streams (in future uses actual plays number as streams).
- **Note:** Because public APIs do not provide some numbers in Json files generated, the Youtube music video's likes and comments count are applied with webscraping*1000, which may not be exact numbers. Spotify monthly listeners number of artists are not scraped yet, which was to represent streams number. If partnering with Spotify, the actually plays of each artist can be obtained as streams values. This draft version is to demostrate the potential data sources and converstion metrics from social interaction to commercial values. Therefore, perfect webscraping is not necessary at this stage. 

## Conversion Metrics

This demo computes **annual conversions** for any top touring artist in **2023**:
- Data source for sales: **TouringData 2023 Top Touring Artists** (one source, year-end total).
- Data source for engagement: **YouTube Data API** (sum views/likes/comments for all videos **published in 2023**).
- Conversions:
  - Views → Likes  = Likes / Views
  - Views → Sales  = TicketsSold / Views
  - Likes → Sales  = TicketsSold / Likes
  - Comments → Sales = TicketsSold / Comments
  - Subscribers → Sales = TicketSold / Subscribers
  - Streams → Followers = Followers / Streams
  - Followers → Sales = TicketSold / Followers
  - Stream → Sales = TicketSold / Streams

## Setup
Run each command separately, one line at a time:

1. conda create -n pipeline python=3.10 -y → creates the environment
2. conda activate pipeline → activates it
3. pip install -r requirements.txt → installs your project libraries
4. python python data_pipeline.py → get tickets sold in cache
5. python -m streamlit run app.py → runs your dashboard
6. Input an artist's name and Youtube channals

## Usage
- In the left sidebar:
- Enter an **Artist name** (e.g., Coldplay, Beyoncé).
- Optionally paste a **YouTube Channel ID**; otherwise the app searches by name and uses the top channel.
- Click **Run**.

## Limitations
- TouringData’s list covers major artists; obscure artists may not appear (tickets sold = 0).
- YouTube API returns **lifetime** stats per video; we sum only videos **published in 2023** to approximate that year’s exposure.
- If the channel auto-search picks an unofficial channel, paste the correct Channel ID manually.



