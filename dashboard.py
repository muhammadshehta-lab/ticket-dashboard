import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import urllib.parse

# ── 1. إعدادات الصفحة ──────────────────────────────────────────────────────────
st.set_page_config(page_title="In-Store Performance Hub", page_icon="💊", layout="wide", initial_sidebar_state="expanded")

# ── 2. تصميم الواجهة (CSS) ───────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background: #0d1117; color: #e6edf3; }
    .kpi-container { border-radius: 14px; padding: 1.2rem 0.8rem; text-align: center; min-height: 110px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 1rem; }
    .kpi-label { font-size: 0.72rem; letter-spacing: .1em; text-transform: uppercase; color: #8b949e; margin-bottom: .4rem; font-weight: 600; }
    .kpi-value { font-size: 1.5rem; font-weight: 800; }
    .card-total { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }
    .card-completed { background: #12221b; border: 1px solid #3fb950; color: #3fb950; }
    .card-issue { background: #261f12; border: 1px solid #d29922; color: #d29922; }
    .card-frt { background: #2b1c11; border: 1px solid #f0883e; color: #f0883e; }
    .card-aht { background: #221230; border: 1px solid #bc8cff; color: #bc8cff; }
    .card-tat { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #161b22; border-radius: 10px 10px 0 0; padding: 10px 20px; color: #8b949e; }
    .stTabs [aria-selected="true"] { background-color: #1e3a8a !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

THEME = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#c9d1d9", margin=dict(l=10, r=10, t=50, b=10))

# ── 3. دوال مساعدة ───────────────────────────────────────────────────────────
def kpi_colored(label, value, card_class): return f'<div class="kpi-container {card_class}"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>'
def time_to_minutes(s):
    try: return int(str(s).strip().split(":")[0]) * 60 + int(str(s).strip().split(":")[1])
    except: return 0
def format_minutes_to_hhmmss(m):
    if pd.isna(m) or m <= 0: return "00:00:00"
    ts = int(round(m * 60))
    return f"{ts//3600:02d}:{(ts%3600)//60:02d}:{ts%60:02d}"
def assign_time_tier(m): return "Under 15 Mins" if m <= 15 else "15-30 Mins" if m <= 30 else "30-45 Mins" if m <= 45 else "45-60 Mins" if m <= 60 else "Over 1 Hour"

DAYS_ARABIC = {"Saturday": "السبت", "Sunday": "الأحد", "Monday": "الإثنين", "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة"}

# ── 4. سحب البيانات ──────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner="Fetching live data from Google Sheets...")
def load_data_from_sheets():
    try:
        creds = Credentials.from_service_account_info(json.loads(st.secrets["gspread"]["credentials"]), scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        all_dfs = []
        for ws in client.open("AlDawaa Tickets Data").worksheets():
            data = ws.get_all_values()
            if len(data) > 1:
                df_tab = pd.DataFrame(data[1:], columns=[str(c).strip() for c in data[0]])
                mapped, assigned = {}, set()
                for col in df_tab.columns:
                    c_low = col.lower()
                    t = "Request ID" if "id" in c_low and "req" in c_low else "Request Date" if "date" in c_low else "Request Type" if "type" in c_low else "Status" if "status" in c_low else "Assigned By" if "agent" in c_low or "assigned" in c_low else "Response Take" if "response" in c_low and "take" in c_low else "First Action Take" if "action" in c_low and "take" in c_low else "Request Take" if "request" in c_low and "take" in c_low else "Is Email" if "email" in c_low or "special" in c_low else None
                    if t and t not in assigned: mapped[col], _ = t, assigned.add(t)
                all_dfs.append(df_tab.rename(columns=mapped))
        if not all_dfs: return pd.DataFrame()
        df = pd.concat(all_dfs, ignore_index=True).replace("", np.nan)
        for c in ["Request ID", "Request Date", "Request Type", "Status", "Request Take", "Response Take", "First Action Take", "Assigned By", "Is Email"]:
            if c not in df.columns: df[c] = np.nan
        df["Status"], df["Assigned By"], df["Request Type"] = df["Status"].fillna("Unknown"), df["Assigned By"].fillna("Unassigned"), df["Request Type"].fillna("Unknown Type")
        df["Request Date"] = pd.to_datetime(df["Request Date"], errors="coerce")
        df["Date Only"], df["Hour"] = df["Request Date"].dt.date, df
