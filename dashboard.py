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

# ── 1. إعدادات الصفحة ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="In-Store Performance Hub", 
    page_icon="💊", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# ── 2. تصميم الواجهة (CSS) ──────────────────────────────────────────────────
st.markdown(
    """
    <style>
        .stApp { background: #0d1117; color: #e6edf3; }
        .kpi-container {
            border-radius: 14px; padding: 1.2rem 0.8rem; text-align: center;
            min-height: 110px; display: flex; flex-direction: column;
            justify-content: center; margin-bottom: 1rem;
        }
        .kpi-label { 
            font-size: 0.72rem; letter-spacing: .1em; 
            text-transform: uppercase; color: #8b949e; 
            margin-bottom: .4rem; font-weight: 600; 
        }
        .kpi-value { font-size: 1.5rem; font-weight: 800; }
        .card-total { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }
        .card-completed { background: #12221b; border: 1px solid #3fb950; color: #3fb950; }
        .card-issue { background: #261f12; border: 1px solid #d29922; color: #d29922; }
        .card-frt { background: #2b1c11; border: 1px solid #f0883e; color: #f0883e; }
        .card-aht { background: #221230; border: 1px solid #bc8cff; color: #bc8cff; }
        .card-tat { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] { 
            background-color: #161b22; border-radius: 10px 10px 0 0; 
            padding: 10px 20px; color: #8b949e; 
        }
        .stTabs [aria-selected="true"] { 
            background-color: #1e3a8a !important; color: white !important; 
        }
    </style>
    """, 
    unsafe_allow_html=True
)

THEME = dict(
    template="plotly_dark", 
    paper_bgcolor="rgba(0,0,0,0)", 
    plot_bgcolor="rgba(0,0,0,0)", 
    font_color="#c9d1d9", 
    margin=dict(l=10, r=10, t=50, b=10)
)

# ── 3. دوال مساعدة ──────────────────────────────────────────────────────────
def kpi_colored(label, value, card_class):
    return (
        f'<div class="kpi-container {card_class}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'</div>'
    )

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

def assign_time_tier(m):
    if m <= 15: return "Under 15 Mins"
    if m <= 30: return "15-30 Mins"
    if m <= 45: return "30-45 Mins"
    if m <= 60: return "45-60 Mins"
    return "Over 1 Hour"

DAYS_ARABIC = {
    "Saturday": "السبت", "Sunday": "الأحد", "Monday": "الإثنين", 
    "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة"
}

# ── 4. سحب البيانات ─────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner="Fetching live data from Google Sheets...")
def load_data_from_sheets():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets", 
            "https://www.googleapis.com/auth/drive"
        ]
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
                    if "id" in c_low and "req" in c_low: 
                        target = "Request ID"
                    elif "date" in c_low: 
                        target = "Request Date"
                    elif "type" in c_low: 
                        target = "Request Type"
                    elif "status" in c_low: 
                        target = "Status"
                    elif "agent" in c_low or "assigned" in c_low: 
                        target = "Assigned By"
                    elif "response" in c_low and "take" in c_low: 
                        target = "Response Take"
                    elif "action" in c_low and "take" in c_low: 
                        target = "First Action Take"
                    elif "request" in c_low and "take" in c_low: 
                        target = "Request Take"
                    elif "email" in c_low or "special" in c_low: 
                        target = "Is Special Request(By Email)"
                    
                    if target and target not in assigned_targets:
                        mapped_cols[col] = target
                        assigned_targets.add(target)
                        
                df_tab.rename(columns=mapped_cols, inplace=True)
                all_dfs.append(df_tab)
                
        if not all_dfs: 
            return pd.DataFrame()
        
        df = pd.concat(all_dfs, ignore_index=True, sort=False)
        df.replace("", np.nan, inplace=True)
        
        req_cols = [
            "Request ID", "Request Date", "Request Type", "Status", 
            "Request Take", "Response Take", "First Action Take", 
            "Assigned By", "Is Special Request(By Email)"
        ]
        
        for col in req_cols:
            if col not in df.columns: 
                df[col] = np.nan

        df["Status"] = df["Status"].fillna("Unknown")
        df["Assigned By"] = df["Assigned By"].fillna("Unassigned")
        df["Request Type"] = df["Request Type"].fillna("Unknown Type")
        
        df["Request Date"] = pd.to_datetime(df["Request Date"], errors="coerce")
        df["Date Only"] = df["Request Date"].dt.date
        df["Hour"] = df["Request Date"].dt.hour.fillna(0).astype(int)
        
        df["Request Take (min)"] = df["Request Take"].apply(time_to_minutes).fillna(0)
        df["Response Take (min)"] = df["Response Take"].apply(time_to_minutes).fillna(0)
        df["First Action Take (min)"] = df["First Action Take"].apply(time_to_minutes).fillna(0)
        df["AHT (min)"] = df["First Action Take (min)"]
        
        mail_col = df["Is Special Request(By Email)"].astype(str).str.strip().str.lower()
        df["Is Email"] = (mail_col == "yes")
        
        return df
        
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return pd.DataFrame()

# ── 5. الفلاتر الجانبية ─────────────────────────────────────────────────────
df_raw = load_data_from_sheets()

with st.sidebar:
    st.markdown("## 💊 Navigation & Filters")
    st.success("📡 Live Sync Active")
    
    if st.button("🔄 Refresh Data Now", use_container_width=True): 
        load_data_from_sheets.clear()
        
    if df_raw.empty:
        st.warning("Waiting for data configuration...")
        st.stop()
        
    st.divider()
    
    min_d = df_raw["Date Only"].dropna().min()
    max_d = df_raw["Date Only"].dropna().max()
    date_val = (min_d, max_d)
    
    date_range = st.date_input("Date Range", value=date_val, min_value=min_d, max_value=max_d)
    
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        d_from, d_to = date_range
    else:
        d_from, d_to = min_d, max_d
    
    if d_from == d_to:
        day_en = pd.to_datetime(d_from).day_name()
        st.caption(f"📅 اليوم المحدد: **{DAYS_ARABIC.get(day_en, day_en)}**")
        
    st.divider()
    
    all_agents = sorted(df_raw["Assigned By"].dropna().unique())
    # استبعاد محمد حربي
    agents_for_filter = [a for a in all_agents if a not in ["Mohamed Harby"]]
    sel_agents = st.multiselect("Agent Filter", agents_for_filter)
    
    req_types = sorted(df_raw["Request Type"].dropna().unique())
    sel_types = st.multiselect("Request Type Filter", req_types)

df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()

if sel_agents: 
    df = df[df["Assigned By"].isin(sel_agents)]
else:
    df = df[df["Assigned By"] != "Mohamed Harby"]

if sel_types: 
    df = df[df["Request Type"].isin(sel_types)]

if d_from == d_to:
    day_name_en = pd.to_datetime(d_from).day_name()
    caption_text = f"🔍 Search Period: {d_from} ({DAYS_ARABIC.get(day_name_en, day_name_en)})"
else:
    caption_text = f"🔍 Search Period: {d_from} to {d_to}"

st.markdown("## 💊 In-Store Requests Dashboard")
st.caption(caption_text)

# ── 6. التابات ───────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📊 In-Store Overview", "👥 Team Performance & KPIs"])

# =============================================================================
# ── TAB 1: OVERVIEW ──────────────────────────────────────────────────────────
# =============================================================================
with tab1:
    col_check1, col_check2 = st.columns(2)
    with col_check1:
        escalated_only = st.checkbox("🔥 Show Escalated Cases Only", value=False)
    with col_check2:
        non_escalated_only = st.checkbox("🟢 Show Non-Escalated Cases Only", value=False)

    df_metrics = df.copy()
    if escalated_only and not non_escalated_only: 
        df_metrics = df_metrics[df_metrics["Is Email"] == True]
    elif non_escalated_only and not escalated_only: 
        df_metrics = df_metrics[df_metrics["Is Email"] == False]

    total_tickets = len(df_metrics)
    status_s = df_metrics["Status"].astype(str).str.strip().str.lower()
    
    comp_success = df_metrics[
        status_s.str.contains("closed", na=False) & ~status_s.str.contains("issue", na=False)
    ].shape[0]
    
    comp_with_issue = df_metrics[
        status_s.str.contains("closed", na=False) & status_s.str.contains("issue", na=False)
    ].shape[0]

    if not df_metrics.empty:
        mean_resp = df_metrics["Response Take (min)"].mean()
        mean_aht = df_metrics["AHT (min)"].mean()
        mean_tat = df_metrics["Request Take (min)"].mean()
    else:
        mean_resp, mean_aht, mean_tat = 0, 0, 0

    h_frt = format_minutes_to_hhmmss(mean_resp)
    h_aht = format_minutes_to_hhmmss(mean_aht)
    h_tat = format_minutes_to_hhmmss(mean_tat)

    r1, r2, r3, r4, r5, r6 = st.columns(6)
    r1.markdown(kpi_colored("Total Tickets", f"{total_tickets:,}", "card-total"), unsafe_allow_html=True)
    r2.markdown(kpi_colored("Closed Completed", f"{comp_success:,}", "card-completed"), unsafe_allow_html=True)
    r3.markdown(kpi_colored("Closed with Issue", f"{comp_with_issue:,}", "card-issue"), unsafe_allow_html=True)
    r4.markdown(kpi_colored("Avg Response", h_frt, "card-frt"), unsafe_allow_html=True)
    r5.markdown(kpi_colored("Avg Handling", h_aht, "card-aht"), unsafe_allow_html=True)
    r6.markdown(kpi_colored("Avg Service", h_tat, "card-tat"), unsafe_allow_html=True)

    st.write("")

    if not df_metrics.empty:
        df_metrics["Response Tier"] = df_metrics["Response Take (min)"].apply(assign_time_tier)
        df_metrics["Service Tier"] = df_metrics["Request Take (min)"].apply(assign_time_tier)
        
        r_data = df_metrics.groupby("Response Tier").size().reset_index(name="Tickets")
        r_data["SLA Category"] = "Response Time"
        r_data.rename(columns={"Response Tier": "SLA Tier"}, inplace=True)
        
        s_data = df_metrics.groupby("Service Tier").size().reset_index(name="Tickets")
        s_data["SLA Category"] = "Service Resolution"
        s_data.rename(columns={"Service Tier": "SLA Tier"}, inplace=True)
        
        sunburst_df = pd.concat([r_data, s_data], ignore_index=True)
        
        time_order = ["Under 15 Mins", "15-30 Mins", "30-45 Mins", "45-60 Mins", "Over 1 Hour"]
        cat_order = ["Response Time", "Service Resolution"]
        
        sunburst_df["SLA Category"] = pd.Categorical(sunburst_df["SLA Category"], categories=cat_order, ordered=True)
        sunburst_df["SLA Tier"] = pd.Categorical(sunburst_df["SLA Tier"], categories=time_order, ordered=True)
        sunburst_df = sunburst_df.sort_values(["SLA Category", "SLA Tier"]).reset_index(drop=True)
        
        sunburst_df["SLA Category"] = sunburst_df["SLA Category"].astype(str)
        sunburst_df["SLA Tier"] = sunburst_df["SLA Tier"].astype(str)
        
        color_map = {
            "Under 15 Mins": "#2ea44f",
