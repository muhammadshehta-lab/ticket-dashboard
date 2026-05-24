"""
dashboard.py — In-Store Requests Dashboard (24 Hours Rush Analysis Edition)
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path

# ── تهيئة إعدادات الصفحة ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="In-Store Requests Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── تصميم الواجهة والألوان (CSS) ──────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background: #0d1117; color: #e6edf3; }
    .kpi-card {
        background: linear-gradient(135deg, #161b22 0%, #21262d 100%);
        border: 1px solid #30363d; border-radius: 14px;
        padding: 1.3rem 1.2rem; text-align: center;
    }
    .kpi-label { font-size: 0.72rem; letter-spacing: .13em; text-transform: uppercase; color: #8b949e; margin-bottom: .4rem; }
    .kpi-value { font-size: 2rem; font-weight: 800; background: linear-gradient(90deg, #58a6ff, #bc8cff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .kpi-sub { font-size: 0.78rem; margin-top: .2rem; }
    [data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
    .stTabs [data-baseweb="tab-list"] { background-color: #161b22; border-radius: 8px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: bold; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom: 2px solid #58a6ff; }
</style>
""", unsafe_allow_html=True)

THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9",
    margin=dict(l=10, r=10, t=40, b=10)
)

def time_to_minutes(s):
    try:
        parts = str(s).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except:
        return 0

# ── جلب البيانات من جوجل شيت ──────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner="Fetching live data from Google Sheets...")
def load_data_from_sheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
            import json
            creds_dict = json.loads(st.secrets["gspread"]["credentials"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            credentials_path = str(Path(__file__).parent / "credentials.json")
            creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        
        client = gspread.authorize(creds)
        spreadsheet = client.open("AlDawaa Tickets Data")

        all_dfs = []
        for worksheet in spreadsheet.worksheets():
            data = worksheet.get_all_values()
            if len(data) > 1:
                df_tab = pd.DataFrame(data[1:], columns=data[0])
                all_dfs.append(df_tab)

        if not all_dfs: 
            return pd.DataFrame()

        df = pd.concat(all_dfs, ignore_index=True)
        df.replace("", np.nan, inplace=True)

        required_cols = ["Request Date", "Assigned By", "Request Type", "Status", "Request Take", "Response Take"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = np.nan

        df["Status"] = df["Status"].fillna("Unknown")
        df["Assigned By"] = df["Assigned By"].fillna("Unassigned")
        df["Request Date"] = pd.to_datetime(df["Request Date"], errors="coerce")
        df["Date Only"] = df["Request Date"].dt.date
        df["Hour"] = df["Request Date"].dt.hour.fillna(0).astype(int)
        df["Day Name"] = df["Request Date"].dt.day_name().fillna("Unknown")
        df["Request Take (min)"] = df["Request Take"].apply(time_to_minutes).fillna(0)
        df["Response Take (min)"] = df["Response Take"].apply(time_to_minutes).fillna(0)
        
        # رصد الـ Reopened Tickets
        df["Is Reopened"] = df["Status"].astype(str).str.lower().str.contains("reopen") | \
                            df["Request Type"].astype(str).str.lower().str.contains("reopen")

        invalid_ins = ["nan", "none", "n/a", "null", "-", "لا يوجد", "unknown", ""]
        if "Insurance Company" in df.columns:
            df["Has Insurance"] = df["Insurance Company"].astype(str).str.strip().str.lower().apply(
                lambda x: False if x in invalid_ins or pd.isna(x) else True
            )
        else:
            df["Has Insurance"] = False

        if "Is Special Request(By Email)" in df.columns:
            df["Is Email"] = df["Is Special Request(By Email)"].astype(str).str.strip().str.upper() == "YES"
        else:
            df["Is Email"] = False

        return df
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال أو الصلاحيات: {e}")
        return pd.DataFrame()

def calc_attendance(df, min_cases=20):
    if df.empty or "Assigned By" not in df.columns or "Date Only" not in df.columns:
        return pd.DataFrame(columns=["Assigned By", "Attendance Days", "Total Handled Cases"])
        
    daily_per_agent = df.groupby(["Assigned By", "Date Only"]).size().reset_index(name="Daily Cases")
    attendance = daily_per_agent[daily_per_agent["Daily Cases"] >= min_cases].groupby("Assigned By").size().reset_index(name="Attendance Days")
    total_agent = df.groupby("Assigned By").size().reset_index(name="Total Handled Cases")
    
    agent_stats = total_agent.merge(attendance, on="Assigned By", how="left").fillna(0)
    agent_stats["Attendance Days"] = agent_stats["Attendance Days"].astype(int)
    return agent_stats

# ── Sidebar Filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💊 Dashboard")
    st.success("📡 Live sync Active")
    if st.button("🔄 Refresh Data Now", use_container_width=True):
        load_data_from_sheets.clear()

    df_raw = load_data_from_sheets()
    if df_raw.empty:
        st.warning("Waiting for data...")
        st.stop()

    st.divider()
    st.subheader("🔍 Filters")
    min_d, max_d = df_raw["Date Only"].dropna().min(), df_raw["Date Only"].dropna().max()
    
    if pd.isna(min_d) or pd.isna(max_d):
        st.error("Date values are completely missing in the sheet.")
        st.stop()
        
    date_range = st.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    d_from, d_to = date_range if isinstance(date_range, (list, tuple)) and len(date_range) == 2 else (min_d, max_d)

    sel_agents = st.multiselect("Agent", sorted(df_raw["Assigned By"].dropna().unique()))
    sel_types = st.multiselect("Request Type", sorted(df_raw["Request Type"].dropna().unique()))
    
    st.divider()
    min_cases = st.number_input("Min cases for Attendance Day", min_value=1, max_value=100, value=20)

# تصفية البيانات
df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_agents: df = df[df["Assigned By"].isin(sel_agents)]
if sel_types:  df = df[df["Request Type"].isin(sel_types)]

# ── العنوان الرئيسي ───────────────────────────────────────────────────────────
st.markdown("## 💊 In-Store Requests Dashboard")
st.caption(f"Showing **{len(df):,}** requests out of {len(df_raw):,} — {d_from} to {d_to}")

# ── تابات العرض ──────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Tickets Stats & Overview", "👥 Agents Performance", "🗃 Raw Data"])

# ==============================================================================
# TAB 1: TICKETS STATS & OVERVIEW
# ==============================================================================
with tab1:
    def kpi(label, value, sub="", sub_color='#3fb950'):
        return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub" style="color: {sub_color}">{sub}</div></div>'

    total_tickets = len(df)
    total_emails =
