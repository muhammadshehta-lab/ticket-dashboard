"""
dashboard.py — In-Store Requests & Ticket Analytics Dashboard (SLA Performance Edition)
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
        padding: 1.3rem 1.2rem; text-align: center;
    }
    .kpi-label { font-size: 0.72rem; letter-spacing: .13em; text-transform: uppercase; color: #8b949e; margin-bottom: .4rem; }
    .kpi-value { font-size: 1.8rem; font-weight: 800; background: linear-gradient(90deg, #58a6ff, #bc8cff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .kpi-sub { font-size: 0.78rem; margin-top: .2rem; }
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

# ── جلب البيانات من جوجل شيت (عبر الـ Secrets حصرياً) ──────────────────────────
@st.cache_data(ttl=600, show_spinner="Fetching live data from Google Sheets...")
def load_data_from_sheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
            creds_dict = json.loads(st.secrets["gspread"]["credentials"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            st.error("❌ لم يتم العثور على جينات الصلاحيات gspread.credentials في إعدادات Secrets.")
            return pd.DataFrame()
        
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

        required_cols = ["Request ID", "Request Date", "Request Type", "Status", "Request Take", "Response Take", "First Action Take"]
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
        df["First Action Take (min)"] = df["First Action Take"].apply(time_to_minutes).fillna(0)
        
        df["AHT (min)"] = df["Response Take (min)"] + df["First Action Take (min)"]
        
        if "Is Special Request(By Email)" in df.columns:
            df["Is Email"] = df["Is Special Request(By Email)"].astype(str).str.strip().str.lower() == "yes"
        else:
            df["Is Email"] = False

        return df
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return pd.DataFrame()

# ── إدارة الحالات والبيانات اليدوية (Tab 2 States) ────────────────────────────
if "manual_values_log" not in st.session_state:
    st.session_state.manual_values_log = []
if "manual_cases_log" not in st.session_state:
    st.session_state.manual_cases_log = []

# ── Sidebar Filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💊 Navigation & Filters")
    st.success("📡 Live Sync Active")
    if st.button("🔄 Refresh Data Now", use_container_width=True):
        load_data_from_sheets.clear()

    df_raw = load_data_from_sheets()
    if df_raw.empty:
        st.warning("Waiting for data configuration...")
        st.stop()

    st.divider()
    min_d, max_d = df_raw["Date Only"].dropna().min(), df_raw["Date Only"].dropna().max()
    date_range = st.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    d_from, d_to = date_range if isinstance(date_range, (list, tuple)) and len(date_range) == 2 else (min_d, max_d)

    sel_agents = st.multiselect("Agent Filter", sorted(df_raw["Assigned By"].dropna().unique()))

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

    # 1. فلترة الإيميل الخاصة
    st.markdown("#### 🔍 Specific Filter Context")
    email_filter = st.checkbox("🎯 Filter Dashboard Content by Special Email Requests Only", value=False)
    
    df_metrics = df[df["Is Email"] == True].copy() if email_filter else df.copy()

    # حساب الـ KPIs الأساسية
    total_tickets = len(df_metrics)
    closed_df = df_metrics[df_metrics["Status"].astype(str).str.contains("Closed", na=False, case=False)]
    
    comp_success = closed_df[~closed_df["Status"].astype(str).str.lower().str.contains("issue")].shape[0]
    comp_with_issue = closed_df[closed_df["Status"].astype(str).str.lower().str.contains("issue")].shape[0]
    
    escalated_cases = total_tickets - (comp_success + comp_with_issue)
    avg_aht_global = df_metrics["AHT (min)"].mean() if not df_metrics.empty else 0
    
    total_cumulative_minutes = df_metrics["Request Take (min)"].sum()
    total_cumulative_hours = total_cumulative_minutes / 60

    # عرض كروت الـ KPI الرئيسية
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi("Total Number of Tickets", f"{total_tickets:,}", "All registered cases", '#58a6ff'), unsafe_allow_html=True)
    c2.markdown(kpi("Closed Completed", f"{comp_success:,}", f"{((comp_success/total_tickets*100) if total_tickets else 0):.1f}% resolved", '#3fb950'), unsafe_allow_html=True)
    c3.markdown(kpi("Closed With Issue", f"{comp_with_issue:,}", f"{((comp_with_issue/total_tickets*100) if total_tickets else 0):.1f}% complications", '#d29922'), unsafe_allow_html=True)
    c4.markdown(kpi("Escalated Cases", f"{escalated_cases:,}", "Pending / Open status", '#f85149'), unsafe_allow_html=True)

    st.write("")
    st.markdown(f"⚡ **Average Handling Time (Response + First Action) Across Team:** {avg_aht_global:.1f} Minutes per ticket.")
    st.write("")

    # 💡 2. قسم الـ SLA ومعدل السرعة والحل الفوري (طلبك الجديد هنا بالظبط)
    st.markdown("### 🎯 SLA Velocity & Response vs. Resolution Analysis")
    st.caption("التحليل التالي يوضح النسبة المئوية للحالات التي تم الرد عليها وحلها في أوقات قياسية.")
    
    # تحديد عتبات السرعة (مثلاً الرد السريع <= 15 دقيقة، والحل السريع <= 30 دقيقة)
    threshold_response = 15
    threshold_resolution = 30
    
    if not df_metrics.empty:
        fast_response_count = df_metrics[df_metrics["Response Take (min)"] <= threshold_response].shape[0]
        fast_resolution_count = df_metrics[df_metrics["Request Take (min)"] <= threshold_resolution].shape[0]
        
        pct_fast_response = (fast_response_count / total_tickets * 100) if total_tickets else 0
        pct_fast_resolution = (fast_resolution_count / total_tickets * 100) if total_tickets else 0
        
        # كروت SLA سريعة
        cs1, cs2 = st.columns(2)
        cs1.markdown(kpi("Fast Response Rate", f"{pct_fast_response:.1f}%", f"Tickets acknowledged within {threshold_response} mins ({fast_response_count:,} cases)", '#3fb950'), unsafe_allow_html=True)
        cs2.markdown(kpi("Fast Resolution Rate", f"{pct_fast_resolution:.1f}%", f"Tickets fully resolved within {threshold_resolution} mins ({fast_resolution_count:,} cases)", '#bc8cff'), unsafe_allow_html=True)
        
        st.write("")
        
        # رسمة الـ Scatter الموضحة لتوزيع السرعة
        fig_sla_scatter = px.scatter(
            df_metrics, 
            x="Response Take (min)", 
            y="Request Take (min)",
            color="Request Type",
            hover_data=["Request ID", "Assigned By", "Status"],
            title="Correlation Matrix: Response Time vs. Service Resolution Time",
            labels={"Response Take (min)": "Response Time (Minutes)", "Request Take (min)": "Service Resolution Time (Minutes)"}
        )
        # إضافة خطوط إرشادية لتحديد الحالات السريعة بصرياً
        fig_sla_scatter.add_vline(x=threshold_response, line_dash="dash", line_color="#3fb950", annotation_text="Fast Response Border")
        fig_sla_scatter.add_hline(y=threshold_resolution, line_dash="dash", line_color="#bc8cff", annotation_text="Fast Resolution Border")
        fig_sla_scatter.update_layout(**THEME)
        st.plotly_chart(fig_sla_scatter, use_container_width=True)
    else:
        st.info("No data available to calculate SLA velocities.")

    st.write("")

    # 3. تحليل الوقت الـ Rush Hours 
    st.markdown("### 📈 24-Hour Rush Hours Curve & Cumulative Volume")
    full_hours = list(range(24))
    hourly_data = df_metrics.groupby("Hour").size().reindex(full_hours).fillna(0).reset_index(name="Volume")
    
    hourly_data["Hour Label"] = hourly_data["Hour"].apply(lambda h: "12 AM" if h==0 else ("12 PM" if h==12 else (f"{h} AM" if h<12 else f"{h-12} PM")))
    
    fig_rush = px.area(hourly_data, x="Hour Label", y="Volume", color_discrete_sequence=["#58a6ff"], title="Fluctuations to identify peak hours")
    fig_rush.update_layout(**THEME)
    st.plotly
