"""
PA Policy Extraction — Results Viewer.

Fetches a pre-computed `result.csv` from a cloud location (Google Drive link,
raw URL, or local file) and renders an interactive dashboard.

Configuration (any of these works):
  - Streamlit secret:  RESULT_CSV_URL = "https://drive.google.com/..."
  - Env var:           RESULT_CSV_URL=...
  - Env var:           RESULT_CSV_PATH=/path/to/result.csv
  - Fallback:          ./sample_result.csv (bundled with the app)

Run:
    streamlit run app.py
"""
from __future__ import annotations

import io
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# =============================================================================
# Page config + custom styling
# =============================================================================
st.set_page_config(
    page_title="PA Policy Extraction — Results",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* Tighten default Streamlit padding */
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }
    header[data-testid="stHeader"] { background: transparent; }

    /* Hero banner */
    .hero {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #ec4899 100%);
        color: white;
        padding: 2.2rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 25px rgba(79, 70, 229, 0.2);
    }
    .hero h1 { color: white; font-size: 2.1rem; margin: 0 0 0.4rem 0; font-weight: 700; }
    .hero p  { color: rgba(255, 255, 255, 0.92); margin: 0; font-size: 1.05rem; }

    /* KPI cards */
    .kpi-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 1.15rem 1.3rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        height: 100%;
    }
    .kpi-label  { color: #6b7280; font-size: 0.82rem; font-weight: 600;
                  text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.35rem; }
    .kpi-value  { color: #111827; font-size: 2rem; font-weight: 700; line-height: 1.1; }
    .kpi-sub    { color: #9ca3af; font-size: 0.78rem; margin-top: 0.25rem; }

    /* Score pills */
    .score-pill {
        display: inline-block; padding: 3px 11px; border-radius: 999px;
        font-weight: 600; font-size: 0.85em; color: white;
    }
    .score-0   { background: #6b7280; }
    .score-low { background: #dc2626; }
    .score-mid { background: #f59e0b; }
    .score-ok  { background: #10b981; }
    .score-hi  { background: #2563eb; }

    /* Section headers */
    h2.section-header {
        color: #1f2937;
        margin-top: 1.5rem !important; margin-bottom: 0.8rem !important;
        font-size: 1.25rem; font-weight: 600;
        border-left: 4px solid #4f46e5; padding-left: 0.7rem;
    }

    /* Hide default Streamlit footer */
    footer { visibility: hidden; }

    /* Tab styling */
    button[data-baseweb="tab"] { font-weight: 500; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# Data loading — cached
# =============================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_csv_from_drive(url_or_id: str) -> pd.DataFrame:
    """Resolve a Google Drive URL/ID and fetch as DataFrame.
    Uses gdown to handle the virus-scan interstitial that Drive shows on larger
    files. Falls back to direct HTTP fetch for non-Drive URLs.
    """
    is_drive = "drive.google.com" in url_or_id or "docs.google.com" in url_or_id

    if not is_drive:
        # Treat as a plain HTTP(S) URL (raw GitHub, S3 public, etc.)
        return pd.read_csv(url_or_id)

    try:
        import gdown
    except ImportError:
        raise RuntimeError("gdown is required for Drive URLs. Add 'gdown' to requirements.")

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        out_path = tmp.name
    gdown.download(url=url_or_id, output=out_path, quiet=True, fuzzy=True)
    return pd.read_csv(out_path)


@st.cache_data(ttl=3600, show_spinner=False)
def load_local_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def load_results() -> tuple[pd.DataFrame, str]:
    """Try configured sources in priority order. Returns (df, source_description)."""
    # Streamlit secret
    secret_url = None
    try:
        secret_url = st.secrets.get("RESULT_CSV_URL")
    except (FileNotFoundError, AttributeError):
        pass

    url = secret_url or os.environ.get("RESULT_CSV_URL")
    if url:
        return fetch_csv_from_drive(url), f"cloud ({_short_source(url)})"

    local = os.environ.get("RESULT_CSV_PATH")
    if local and os.path.exists(local):
        return load_local_csv(local), f"local file ({os.path.basename(local)})"

    sample_path = Path(__file__).parent / "sample_result.csv"
    if sample_path.exists():
        return load_local_csv(str(sample_path)), "bundled sample (configure RESULT_CSV_URL for live data)"

    raise FileNotFoundError(
        "No data source configured. Set RESULT_CSV_URL in Streamlit secrets "
        "or RESULT_CSV_PATH env var, or place a sample_result.csv alongside app.py."
    )


def _short_source(url: str) -> str:
    if "drive.google.com" in url:
        m = re.search(r"/(?:d|folders)/([\w-]+)", url) or re.search(r"id=([\w-]+)", url)
        return f"Drive · {m.group(1)[:10]}…" if m else "Google Drive"
    if "github" in url:
        return "GitHub"
    return url.split("//")[-1].split("/")[0]


# =============================================================================
# Helpers
# =============================================================================
def score_tier(score: int) -> str:
    if score == 0:    return "0 — Not covered"
    if score < 25:    return "1–24 — Very restricted"
    if score < 50:    return "25–49 — Restricted vs FDA"
    if score < 75:    return "50–74 — FDA parity"
    return "75–100 — Favorable"


def score_color(score: int) -> str:
    if score == 0:    return "#6b7280"
    if score < 25:    return "#dc2626"
    if score < 50:    return "#f59e0b"
    if score < 75:    return "#10b981"
    return "#2563eb"


TIER_ORDER = ["0 — Not covered", "1–24 — Very restricted", "25–49 — Restricted vs FDA",
              "50–74 — FDA parity", "75–100 — Favorable"]
TIER_COLORS = {t: score_color({"0 — Not covered": 0,
                               "1–24 — Very restricted": 12,
                               "25–49 — Restricted vs FDA": 35,
                               "50–74 — FDA parity": 62,
                               "75–100 — Favorable": 90}[t]) for t in TIER_ORDER}


def kpi_card(label: str, value, sub: str = "") -> str:
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """


# =============================================================================
# Hero header
# =============================================================================
st.markdown("""
<div class="hero">
    <h1>💊 Prior Authorization Policy Extraction</h1>
    <p>Structured PA criteria extracted from payer policies for plaque psoriasis. Powered by Gemini 2.5 Flash.</p>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# Load data
# =============================================================================
try:
    df, source = load_results()
except Exception as e:
    st.error(f"Couldn't load results: {e}")
    st.stop()

# Refresh button + source indicator (small, top-right)
col_src, col_refresh = st.columns([6, 1])
with col_src:
    st.caption(f"📡 Data source: **{source}**  ·  loaded {datetime.now().strftime('%H:%M:%S')}  ·  {len(df):,} rows")
with col_refresh:
    if st.button("🔄 Refresh", use_container_width=True, help="Re-fetch from source"):
        st.cache_data.clear()
        st.rerun()


# =============================================================================
# KPI row
# =============================================================================
total_rows = len(df)
unique_pdfs = df["Filename"].nunique()
unique_brands = df["Brand"].nunique()
median_score = int(df["Access Score"].median()) if total_rows else 0
covered_rows = (df["Access Score"] > 0).sum()
zero_score_rows = (df["Access Score"] == 0).sum()

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(kpi_card("📄 Policies", f"{unique_pdfs:,}", "unique PDF documents"), unsafe_allow_html=True)
with k2:
    st.markdown(kpi_card("💊 Brands", f"{unique_brands:,}", "with documented PA criteria"), unsafe_allow_html=True)
with k3:
    st.markdown(kpi_card("📊 Rows", f"{total_rows:,}", "file × brand combinations"), unsafe_allow_html=True)
with k4:
    st.markdown(kpi_card("⭐ Median Score", f"{median_score}", "out of 100 (FDA parity = 50)"), unsafe_allow_html=True)
with k5:
    pct = 100 * covered_rows / total_rows if total_rows else 0
    st.markdown(kpi_card("✅ Covered", f"{pct:.0f}%", f"{covered_rows:,} with criteria"), unsafe_allow_html=True)


# =============================================================================
# Charts row
# =============================================================================
st.markdown('<h2 class="section-header">📈 Score & Restrictions Overview</h2>', unsafe_allow_html=True)

c1, c2 = st.columns([3, 2])

with c1:
    # Score distribution by tier
    df["_tier"] = df["Access Score"].apply(score_tier)
    tier_counts = (df["_tier"].value_counts()
                   .reindex(TIER_ORDER, fill_value=0).reset_index())
    tier_counts.columns = ["Tier", "Count"]

    fig = px.bar(
        tier_counts, x="Count", y="Tier",
        orientation="h",
        color="Tier",
        color_discrete_map=TIER_COLORS,
        text="Count",
    )
    fig.update_traces(textposition="outside", textfont_size=12)
    fig.update_layout(
        showlegend=False,
        height=320,
        margin=dict(l=10, r=30, t=30, b=10),
        title=dict(text="Access Score Distribution", font=dict(size=15)),
        xaxis=dict(title="", showgrid=True, gridcolor="#f3f4f6"),
        yaxis=dict(title="", categoryorder="array", categoryarray=TIER_ORDER[::-1]),
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)

with c2:
    # Restrictions usage (how often each restriction shows up)
    restrictions = {
        "TB Test required": (df["TB Test required"].astype(str).str.strip().str.lower() == "yes").sum(),
        "Phototherapy step": (df["Step through-Phototherapy"].astype(str).str.strip().str.lower() == "yes").sum(),
        "Specialist required": df["Specialist Types"].astype(str).str.strip().str.lower().apply(
            lambda v: v not in ("", "na", "nan", "no", "none", "unspecified")).sum(),
        "Quantity limits": df["Quantity Limits"].astype(str).str.strip().str.lower().apply(
            lambda v: v not in ("", "na", "nan", "no", "none", "unspecified")).sum(),
        "Reauthorization": (df["Reauthorization Required"].astype(str).str.strip().str.lower() == "yes").sum(),
    }
    rdf = pd.DataFrame({"Restriction": list(restrictions.keys()),
                        "Count": list(restrictions.values())})
    rdf["Pct"] = (rdf["Count"] / len(df) * 100).round(1)

    fig = px.bar(
        rdf, x="Restriction", y="Count",
        text=rdf["Pct"].astype(str) + "%",
        color="Count",
        color_continuous_scale=["#ddd6fe", "#7c3aed"],
    )
    fig.update_traces(textposition="outside", textfont_size=11)
    fig.update_layout(
        showlegend=False, coloraxis_showscale=False,
        height=320, margin=dict(l=10, r=10, t=30, b=10),
        title=dict(text="Restrictions by Frequency", font=dict(size=15)),
        xaxis=dict(title="", tickangle=-25),
        yaxis=dict(title="", showgrid=True, gridcolor="#f3f4f6"),
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Brand-level summary
# =============================================================================
with st.expander("📊 Per-brand score profile (click to expand)", expanded=False):
    brand_summary = (df.groupby("Brand")
                       .agg(rows=("Brand", "count"),
                            median_score=("Access Score", "median"),
                            min_score=("Access Score", "min"),
                            max_score=("Access Score", "max"))
                       .sort_values("rows", ascending=False)
                       .head(15))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=brand_summary.index, y=brand_summary["rows"],
        name="Row count", marker_color="#a5b4fc",
        yaxis="y", text=brand_summary["rows"], textposition="outside",
    ))
    fig.add_trace(go.Scatter(
        x=brand_summary.index, y=brand_summary["median_score"],
        name="Median score", mode="markers+lines",
        marker=dict(size=11, color="#dc2626"),
        line=dict(color="#dc2626", width=2),
        yaxis="y2",
    ))
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=40, b=10),
        title=dict(text="Top 15 brands — row count vs median Access Score", font=dict(size=15)),
        xaxis=dict(title="", tickangle=-30),
        yaxis=dict(title="Row count", side="left", showgrid=False),
        yaxis2=dict(title="Median Access Score", side="right", overlaying="y",
                    range=[0, 100], showgrid=True, gridcolor="#f3f4f6"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Filter + table section
# =============================================================================
st.markdown('<h2 class="section-header">🔍 Browse Extracted Criteria</h2>', unsafe_allow_html=True)

fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 1.5])
with fc1:
    brand_filter = st.multiselect("Brand", options=sorted(df["Brand"].unique()), default=[])
with fc2:
    score_min, score_max = st.slider("Access Score range", 0, 100, (0, 100))
with fc3:
    file_search = st.text_input("Filename contains", "")
with fc4:
    show_only_covered = st.toggle("Hide zero-score rows", value=False)

filt = df.copy()
if brand_filter:
    filt = filt[filt["Brand"].isin(brand_filter)]
filt = filt[(filt["Access Score"] >= score_min) & (filt["Access Score"] <= score_max)]
if file_search:
    filt = filt[filt["Filename"].str.contains(file_search, case=False, na=False)]
if show_only_covered:
    filt = filt[filt["Access Score"] > 0]

st.caption(f"Showing **{len(filt):,}** of {len(df):,} rows")

# Main table — abbreviated columns for readability
display_cols = [
    "Filename", "Brand", "Age",
    "Number of Steps through Brands", "Number of Steps through Generic",
    "TB Test required", "Specialist Types",
    "Initial Authorization Duration(in-months)", "Reauthorization Required",
    "Access Score",
]

st.dataframe(
    filt[display_cols],
    use_container_width=True,
    height=440,
    column_config={
        "Filename": st.column_config.TextColumn("Filename", width="medium"),
        "Brand": st.column_config.TextColumn("Brand", width="small"),
        "Number of Steps through Brands":  st.column_config.NumberColumn("Brand steps",  width="small"),
        "Number of Steps through Generic": st.column_config.NumberColumn("Generic steps", width="small"),
        "TB Test required":                st.column_config.TextColumn("TB test", width="small"),
        "Initial Authorization Duration(in-months)": st.column_config.TextColumn("Init auth", width="small"),
        "Reauthorization Required":        st.column_config.TextColumn("Reauth", width="small"),
        "Access Score": st.column_config.ProgressColumn(
            "Access Score", min_value=0, max_value=100, format="%d", width="medium",
        ),
    },
    hide_index=True,
)


# =============================================================================
# Row drill-down
# =============================================================================
if len(filt):
    st.markdown('<h2 class="section-header">🔬 Row Detail</h2>', unsafe_allow_html=True)

    row_idx = st.selectbox(
        "Select a row to inspect",
        options=filt.index.tolist(),
        format_func=lambda i: (
            f"{filt.loc[i, 'Filename']}  ·  {filt.loc[i, 'Brand']}  "
            f"(score {filt.loc[i, 'Access Score']})"
        ),
        label_visibility="collapsed",
    )
    row = filt.loc[row_idx]
    score = int(row["Access Score"])

    with st.container(border=True):
        # Header strip
        hdr_l, hdr_r = st.columns([3, 1])
        with hdr_l:
            st.markdown(f"### {row['Brand']} in `{row['Filename']}`")
        with hdr_r:
            st.markdown(
                f'<div style="text-align:right; padding-top:0.6rem;">'
                f'<span class="score-pill" style="background:{score_color(score)}; font-size:1rem;">'
                f'Access Score: {score}</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown(f"_Tier: **{score_tier(score)}**_")

        d1, d2, d3 = st.columns(3)
        with d1:
            st.markdown("**👤 Eligibility**")
            st.write(f"Age: `{row['Age']}`")
            st.write(f"Specialist: `{row['Specialist Types']}`")
            st.write(f"TB Test: `{row['TB Test required']}`")
        with d2:
            st.markdown("**🔢 Step Therapy**")
            st.write(f"Brand steps: `{row['Number of Steps through Brands']}`")
            st.write(f"Generic steps: `{row['Number of Steps through Generic']}`")
            st.write(f"Phototherapy: `{row['Step through-Phototherapy']}`")
        with d3:
            st.markdown("**⏱ Authorization**")
            st.write(f"Initial: `{row['Initial Authorization Duration(in-months)']}`")
            st.write(f"Reauthorization: `{row['Reauthorization Required']}`")
            st.write(f"Reauth duration: `{row['Reauthorization Duration(in-months)']}`")

        if row["Quantity Limits"] and str(row["Quantity Limits"]).strip().lower() not in ("nan", "na", ""):
            st.markdown(f"**📦 Quantity limits:** {row['Quantity Limits']}")

        st.markdown("**📋 Step therapy requirements (verbatim from policy)**")
        st.info(row["Step Therapy Requirements Documented in Policy"] or "_No criteria documented_")

        reauth_text = row["Reauthorization Requirements Documented in Policy"]
        if reauth_text and str(reauth_text).strip().lower() not in ("nan", "na", ""):
            st.markdown("**🔄 Reauthorization requirements**")
            st.info(reauth_text)


# =============================================================================
# Export
# =============================================================================
st.markdown('<h2 class="section-header">💾 Export</h2>', unsafe_allow_html=True)
e1, e2, e3 = st.columns([1, 1, 4])
with e1:
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Full CSV", csv_bytes,
        file_name="result.csv", mime="text/csv",
        use_container_width=True, type="primary",
    )
with e2:
    if len(filt):
        filt_bytes = filt.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Filtered CSV", filt_bytes,
            file_name=f"result_filtered_{len(filt)}rows.csv", mime="text/csv",
            use_container_width=True,
        )
