# PA Policy Extraction — Results Viewer

A polished web dashboard for browsing Prior Authorization extraction results.
Reads a pre-computed `result.csv` (produced by the extraction notebook) from
the cloud and renders it with KPI cards, distribution charts, an interactive
filterable table, and per-row drill-down.

**No upload, no API key, no extraction** — just visualization on top of CSV
output the notebook already generated.

## What you see

- **Hero header** + 5 KPI cards (policies, brands, rows, median score, %
  covered)
- **Score distribution** — horizontal bar chart by access-score tier with
  FDA-anchored color coding
- **Restrictions overview** — frequency of TB test, phototherapy, specialist,
  quantity limits, reauth requirements
- **Per-brand profile** — top 15 brands with row counts (bars) overlaid with
  median score (line) on a dual axis
- **Filterable browse table** — brand multiselect, score range slider,
  filename search, color-coded Access Score progress bars
- **Row drill-down** — full criteria text, verbatim step-therapy and reauth
  rules, with tier label and color-coded score pill
- **CSV downloads** — full result or current filtered subset

## Configure your data source

The app tries these sources in order (first hit wins):

| Priority | Source | How to set |
|---|---|---|
| 1 | Streamlit secret | `.streamlit/secrets.toml` → `RESULT_CSV_URL = "..."` |
| 2 | Environment variable | `export RESULT_CSV_URL=...` |
| 3 | Local file path | `export RESULT_CSV_PATH=/path/to/result.csv` |
| 4 | Bundled sample | `sample_result.csv` (20 representative rows, ships with the app) |

`RESULT_CSV_URL` accepts:
- **Google Drive file** — `https://drive.google.com/file/d/<id>/view?usp=sharing`
  (the file must be set to "Anyone with the link → Viewer")
- **Direct HTTP(S)** — any URL returning a CSV (raw GitHub, public S3, etc.)

Drive URLs go through `gdown.download(fuzzy=True)` which handles the
virus-scan interstitial automatically.

## Local run

```bash
cd pa_results_viewer
pip install -r requirements.txt

# Option A: just run it on the bundled sample
streamlit run app.py

# Option B: point at your real CSV
export RESULT_CSV_URL="https://drive.google.com/file/d/YOUR_FILE_ID/view"
streamlit run app.py
```

## Deploy to Streamlit Cloud (free)

1. Push this folder to a GitHub repo
2. Go to https://share.streamlit.io → "New app" → point at `app.py`
3. Under **Advanced settings → Secrets**, paste:
   ```toml
   RESULT_CSV_URL = "https://drive.google.com/file/d/YOUR_FILE_ID/view"
   ```
4. Deploy. Live at `https://<your-name>-<repo>.streamlit.app`

## Sharing your Drive CSV

From your Colab notebook, the `result.csv` is at
`/content/drive/MyDrive/PA_Hackathon/outputs/result.csv`. To get a shareable
link:

1. Open Google Drive in a browser
2. Navigate to `PA_Hackathon/outputs/result.csv`
3. Right-click → **Share** → **Anyone with the link → Viewer**
4. Copy link — paste into `RESULT_CSV_URL`

When you re-run the notebook, the CSV in Drive updates automatically. The app
caches for 1 hour; click the **🔄 Refresh** button (top-right of the page)
to fetch the latest version immediately.

## Files

```
pa_results_viewer/
├── app.py             # The Streamlit dashboard (single file)
├── sample_result.csv  # 20-row demo CSV so the app works out of the box
├── requirements.txt
└── README.md
```
