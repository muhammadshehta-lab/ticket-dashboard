"""
dashboard.py — In-Store Requests Dashboard (Standard Time Metrics Edition)
"""

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
    .kpi-value { font-size: 1.5rem; font-weight: 800; background: linear-gradient(90deg, #58a6ff, #bc8cff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .kpi-sub { font-size: 0.72rem; margin-top: .2rem; }
    [data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
    .stTabs [data-baseweb="tab-list"] { background-color: #161b22; border-radius: 8px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: bold; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom: 2px solid #58a6ff; }
    .form-container { background-color: #161b22; border: 1px solid #30363d; padding: 1.5rem; border-radius: 14px; margin-bottom: 1rem; }
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

# ── جلب البيانات والربط الديناميكي للأعمدة المتغيرة ─────────────────────────────
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
                for col in df_tab.columns:
                    c_low = col.lower()
                    if "id" in c_low and "req" in c_low: mapped_cols[col] = "Request ID"
                    elif "date" in c_low: mapped_cols[col] = "Request Date"
                    elif "type" in c_low: mapped_cols[col] = "Request Type"
                    elif "status" in c_low: mapped_cols[col] = "Status"
                    elif "assigned" in c_low or "agent" in c_low: mapped_cols[col] = "Assigned By"
                    elif "request" in c_low and "take" in c_low: mapped_cols[col] = "Request Take"
                    elif "response" in c_low and "take" in c_low: mapped_cols[col] = "Response Take"
                    elif "action" in c_low and "take" in c_low: mapped_cols[col] = "First Action Take"
                    elif "email" in c_low or "special" in c_low: mapped_cols[col] = "Is Special Request(By Email)"
                
                df_tab.rename(columns=mapped_cols, inplace=True)
                all_dfs.append(df_tab)

        if not all_dfs: 
            return pd.DataFrame()

        df = pd.concat(all_dfs, ignore_index=True, sort=False)
        df.replace("", np.nan, inplace=True)

        req_cols = [
            "Request ID", "Request Date", "Request Type", 
            "Status", "Request Take", "Response Take", 
            "First Action Take", "Assigned By", "Is Special Request(By Email)"
        ]
        for col in req_cols:
            if col not in df.columns:
                df[col] = np.nan

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
        
        df["AHT (min)"] = df["Response Take (min)"] + df["First Action Take (min)"]
        
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

# ── إدارة الحالات والبيانات اليدوية (Tab 2 States) ────────────────────────────
if "manual_values_log" not in st.session_state:
    st.session_state.manual_values_log = []
if "manual_cases_log" not in st.session_state:
    st.session_state.manual_cases_log = []

# ── Sidebar Filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Navigation & Filters")
    st.success("📡 Live Sync Active")
    if st.button("🔄 Refresh Data Now", use_container_width=True):
        load_data_from_sheets.clear()

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

# تطبيق الفلاتر الأساسية
df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_agents: 
    df = df[df["Assigned By"].isin(sel_agents)]

# ── العنوان الرئيسي ───────────────────────────────────────────────────────────
st.markdown("## 💊 Ticket Control Panel & Operational Analytics")
st.caption(f"Scannable views for performance metrics — {d_from} to {d_to}")

# ── تقسيم لوحة التحكم إلى التابات المطلوبة ────────────────────────────────────────
tab1, tab2 = st.tabs(["📊 Tab 1: Ticket Statistics & Core Metrics", "⚙️ Tab 2: Manual Inputs & Value Tracking"])

# ==============================================================================
# TAB 1: TICKET STATISTICS & CORE METRICS
# ==============================================================================
with tab1:
    def kpi(label, value, sub="", sub_color='#3fb950'):
        return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub" style="color: {sub_color}">{sub}</div></div>'

    st.markdown("#### 🔍 Specific Filter Context")
    email_filter = st.checkbox("🎯 Filter Dashboard Content by Special Email Requests Only", value=False)
    
    df_metrics = df[df["Is Email"] == True].copy() if email_filter else df.copy()

    # حساب الـ KPIs الأساسية للنظام الآلي
    total_tickets = len(df_metrics)
    status_series = df_metrics["Status"].astype(str).str.strip()
    
    comp_success = df_metrics[
        status_series.str.contains("Closed", na=False, case=False) & 
        ~status_series.str.contains("issue", na=False, case=False)
    ].shape[0]
    
    comp_with_issue = df_metrics[
        status_series.str.contains("Closed", na=False, case=False) & 
        status_series.str.contains("issue", na=False, case=False)
    ].shape[0]
    
    escalated_cases = df_metrics[df_metrics["Is Email"] == True].shape[0]
    
    # حساب المتوسطات والمجاميع الزمنية المطلوبة بدقة للفلاش كاردز المجمعة
    avg_response_global = df_metrics["Response Take (min)"].mean() if not df_metrics.empty else 0
    avg_aht_global = df_metrics["AHT (min)"].mean() if not df_metrics.empty else 0
    
    total_cumulative_minutes = df_metrics["Request Take (min)"].sum()
    total_cumulative_hours = total_cumulative_minutes / 60

    # حساب مجاميع القيم اليدوية من Tab 2
    total_logged_manual_cases = len(st.session_state.manual_cases_log)
    total_support_value_sum = sum([float(str(item["Value"]).replace(",", "")) for item in st.session_state.manual_values_log])

    # ── [A] الصف العلوي: الـ 8 فلاش كاردز (عرض مؤشرات الوقت الثلاثة متجاورة FRT, AHT, TAT)
    r1_c1, r1_c2, r1_c3, r1_c4, r1_c5, r1_c6, r1_c7, r1_c8 = st.columns(8)
    
    r1_c1.markdown(kpi("Total Tickets", f"{total_tickets:,}", "Automated entries", '#58a6ff'), unsafe_allow_html=True)
    r1_c2.markdown(kpi("Closed Completed", f"{comp_success:,}", "Resolved clean", '#3fb950'), unsafe_allow_html=True)
    r1_c3.markdown(kpi("Closed with Issue", f"{comp_with_issue:,}", "With complications", '#d29922'), unsafe_allow_html=True)
    r1_c4.markdown(kpi("Escalated Cases", f"{escalated_cases:,}", "Email Yes volume", '#f85149'), unsafe_allow_html=True)
    
    # 🎯 صف مقاييس الوقت الثلاثية الموحدة جنباً إلى جنب كما طلبت بالظبط:
    r1_c5.markdown(kpi("Avg Response (FRT)", f"{avg_response_global:.1f} Min", "First Response Time", '#f0883e'), unsafe_allow_html=True)
    r1_c6.markdown(kpi("Avg Handling (AHT)", f"{avg_aht_global:.1f} Min", "Actual Process Time", '#bc8cff'), unsafe_allow_html=True)
