import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# ── تهيئة إعدادات الصفحة ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="In-Store Requests Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── تصميم الواجهة والألوان المتطورة (Modern UI/UX CSS) ─────────────────────────
st.markdown("""
<style>
    .stApp { background: #0d1117; color: #e6edf3; }
    .kpi-card {
        background: linear-gradient(135deg, #161b22 0%, #21262d 100%);
        border: 1px solid #30363d; border-radius: 14px;
        padding: 1rem 0.8rem; text-align: center;
        min-height: 120px; display: flex; flex-direction: column; justify-content: center;
    }
    .kpi-label { font-size: 0.68rem; letter-spacing: .1em; text-transform: uppercase; color: #8b949e; margin-bottom: .3rem; }
    .kpi-value { font-size: 1.4rem; font-weight: 800; background: linear-gradient(90deg, #58a6ff, #bc8cff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .kpi-sub { font-size: 0.72rem; margin-top: .2rem; }
    [data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
</style>
""", unsafe_allow_html=True)

THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9",
    margin=dict(l=10, r=10, t=40, b=10)
)

# ✅ دالة بناء الكروت مستقرة في الأعلى
def kpi(label, value, sub="", sub_color='#3fb950'):
    return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub" style="color: {sub_color}">{sub}</div></div>'

def time_to_minutes(s):
    try:
        parts = str(s).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except:
        return 0

def format_minutes_to_hhmmss(minutes_val):
    if pd.isna(minutes_val) or minutes_val <= 0:
        return "00:00:00"
    total_seconds = int(round(minutes_val * 60))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

@st.cache_data(ttl=600, show_spinner="Fetching live data from Google Sheets...")
def load_data_from_sheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
            sec_json = st.secrets["gspread"]["credentials"]
            creds_dict = json.loads(sec_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            st.error("❌ لم يتم العثور على جينات الصلاحيات في Secrets.")
            return pd.DataFrame()
        
        client = gspread.authorize(creds)
        spreadsheet = client.open("AlDawaa Tickets Data")
        all_dfs = []
        for worksheet in spreadsheet.worksheets():
            data = worksheet.get_all_values()
            if len(data) > 1:
                raw_cols = [str(c).strip() for c in data[0]]
                df_tab = pd.DataFrame(data[1:], columns=raw_cols)
                mapped_cols = {}
                assigned_targets = set()
                for col in df_tab.columns:
                    c_low = col.lower()
                    target = None
                    if "id" in c_low and "req" in c_low: target = "Request ID"
                    elif "date" in c_low: target = "Request Date"
                    elif "type" in c_low: target = "Request Type"
                    elif "status" in c_low: target = "Status"
                    elif "assigned" in c_low or "agent" in c_low: target = "Assigned By"
                    elif "response" in c_low and "take" in c_low: target = "Response Take"
                    elif "action" in c_low and "take" in c_low: target = "First Action Take"
                    elif "request" in c_low and "take" in c_low: target = "Request Take"
                    elif "email" in c_low or "special" in c_low: target = "Is Special Request(By Email)"
                    
                    if target and target not in assigned_targets:
                        mapped_cols[col] = target
                        assigned_targets.add(target)
                df_tab.rename(columns=mapped_cols, inplace=True)
                all_dfs.append(df_tab)

        if not all_dfs: return pd.DataFrame()
        df = pd.concat(all_dfs, ignore_index=True, sort=False)
        df.replace("", np.nan, inplace=True)
        req_cols = ["Request ID", "Request Date", "Request Type", "Status", "Request Take", "Response Take", "First Action Take", "Assigned By", "Is Special Request(By Email)"]
        for col in req_cols:
            if col not in df.columns: df[col] = np.nan

        df["Status"] = df["Status"].fillna("Unknown")
        df["Assigned By"] = df["Assigned By"].fillna("Unassigned")
        date_parsed = pd.to_datetime(df["Request Date"], errors="coerce")
        df["Request Date"] = date_parsed
        df["Date Only"] = date_parsed.dt.date
        df["Hour"] = date_parsed.dt.hour.fillna(0).astype(int)
        df["Day Name"] = date_parsed.dt.day_name().fillna("Unknown")
        df["Request Take (min)"] = df["Request Take"].apply(time_to_minutes).fillna(0)
        df["Response Take (min)"] = df["Response Take"].apply(time_to_minutes).fillna(0)
        df["First Action Take (min)"] = df["First Action Take"].apply(time_to_minutes).fillna(0)
        
        # وقت المعالجة الحقيقي الصافي للإجراء الأول
        df["AHT (min)"] = df["First Action Take (min)"]
        
        mail_col = df["Is Special Request(By Email)"].astype(str).str.strip().str.lower()
        df["Is Email"] = (mail_col == "yes")
        return df
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return pd.DataFrame()

def assign_time_tier(m):
    if m <= 15: return "Under 15 Mins"
    if m <= 30: return "15-30 Mins"
    if m <= 45: return "30-45 Mins"
    if m <= 60: return "45-60 Mins"
    return "Over 1 Hour"

# ── Sidebar Filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💊 Navigation & Filters")
    st.success("📡 Live Sync Active")
    if st.button("🔄 Refresh Data Now", use_container_width=True): load_data_from_sheets.clear()
    df_raw = load_data_from_sheets()
    if df_raw.empty:
        st.warning("Waiting for data configuration...")
        st.stop()
    st.divider()
    min_d = df_raw["Date Only"].dropna().min()
    max_d = df_raw["Date Only"].dropna().max()
    date_val = (min_d, max_d)
    date_range = st.date_input("Date Range", value=date_val, min_value=min_d, max_value=max_d)
    d_from, d_to = date_range if isinstance(date_range, (list, tuple)) and len(date_range) == 2 else (min_d, max_d)
    raw_agents = df_raw["Assigned By"].dropna().unique()
    sorted_agents = sorted(raw_agents)
    sel_agents = st.multiselect("Agent Filter", sorted_agents)

df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_agents: df = df[df["Assigned By"].isin(sel_agents)]

# ── العنوان الرئيسي ───────────────────────────────────────────────────────────
st.markdown("## 💊 Ticket Control Panel & Operational Analytics")
st.caption(f"Scannable views for performance metrics — {d_from} to {d_to}")

st.markdown("#### 🔍 Specific Filter Context")

col_check1, col_check2, col_check3 = st.columns(3)
with col_check1:
    email_filter = st.checkbox("🎯 Filter Dashboard Content by Special Email Requests Only", value=False)
with col_check2:
    escalated_only_filter = st.checkbox("🔥 Show Escalated Cases Only", value=False)
with col_check3:
    non_escalated_only_filter = st.checkbox("🟢 Show Non-Escalated Cases Only", value=False)

# تجميع وتصفية البيانات تبادلياً بشكل مأمن بالكامل من التعارض
df_metrics = df.copy()
if email_filter:
    df_metrics = df_metrics[df_metrics["Is Email"] == True]

if escalated_only_filter and not non_escalated_only_filter:
    df_metrics = df_metrics[df_metrics["Is Email"] == True]
elif non_escalated_only_filter and not escalated_only_filter:
    df_metrics = df_
