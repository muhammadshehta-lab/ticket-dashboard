"""
dashboard.py — In-Store Requests & Ticket Analytics Dashboard (SLA Layout & Response Curve Fixed)
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
            st.error("❌ لم يتم العثور على بيانات الاعتماد gspread.credentials في إعدادات Secrets.")
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

def assign_time_tier(minutes):
    if minutes <= 15: return "01. Under 15 Mins"
    if minutes <= 30: return "02. 15 to 30 Mins"
    if minutes <= 45: return "03. 30 to 45 Mins"
    if minutes <= 60: return "04. 45 to 60 Mins"
    return "05. Over 1 Hour"

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

    # ── [A] كروت الـ KPI الرئيسية في القمة
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi("Total Number of Tickets", f"{total_tickets:,}", "All registered cases", '#58a6ff'), unsafe_allow_html=True)
    c2.markdown(kpi("Closed Completed", f"{comp_success:,}", f"{((comp_success/total_tickets*100) if total_tickets else 0):.1f}% resolved", '#3fb950'), unsafe_allow_html=True)
    c3.markdown(kpi("Closed With Issue", f"{comp_with_issue:,}", f"{((comp_with_issue/total_tickets*100) if total_tickets else 0):.1f}% complications", '#d29922'), unsafe_allow_html=True)
    c4.markdown(kpi("Escalated Cases", f"{escalated_cases:,}", "Pending / Open status", '#f85149'), unsafe_allow_html=True)

    st.write("")
    st.markdown(f"⚡ **Average Handling Time (Response + First Action) Across Team:** {avg_aht_global:.1f} Minutes per ticket.")
    st.write("")

    # ── [B] الـ SLA Time Tiers مباشرة تحت فلاش كاردز
    st.markdown("### 🎯 SLA Service & Response Tiers Percentage")
    st.caption("يوضح المخطط أدناه النسبة المئوية الدقيقة لتوزيع الحالات عبر فترات زمنية محددة.")
    
    if not df_metrics.empty:
        df_metrics["Response Tier"] = df_metrics["Response Take (min)"].apply(assign_time_tier)
        df_metrics["Service Tier"] = df_metrics["Request Take (min)"].apply(assign_time_tier)
        
        all_tiers = ["01. Under 15 Mins", "02. 15 to 30 Mins", "03. 30 to 45 Mins", "04. 45 to 60 Mins", "05. Over 1 Hour"]
        
        resp_counts = df_metrics.groupby("Response Tier").size().reindex(all_tiers, fill_value=0).reset_index(name="Tickets")
        resp_counts["Metric Type"] = "01. Response Time"
        resp_counts.rename(columns={"Response Tier": "Time Tier"}, inplace=True)
        
        serv_counts = df_metrics.groupby("Service Tier").size().reindex(all_tiers, fill_value=0).reset_index(name="Tickets")
        serv_counts["Metric Type"] = "02. Service (Resolution) Time"
        serv_counts.rename(columns={"Service Tier": "Time Tier"}, inplace=True)
        
        sla_combined = pd.concat([resp_counts, serv_counts], ignore_index=True)
        
        total_per_metric = sla_combined.groupby("Metric Type")["Tickets"].transform("sum")
        sla_combined["Percentage"] = np.where(total_per_metric > 0, (sla_combined["Tickets"] / total_per_metric * 100).round(1), 0.0)
        sla_combined["Label"] = np.where(sla_combined["Percentage"] > 0, sla_combined["Percentage"].astype(str) + "%", "")
        
        fig_tiers = px.bar(
            sla_combined, 
            y="Metric Type", 
            x="Percentage", 
            color="Time Tier",
            orientation="h",
            text="Label",
            category_orders={"Time Tier": all_tiers},
            color_discrete_map={
                "01. Under 15 Mins": "#2ea44f",
                "02. 15 to 30 Mins": "#2188ff",
                "03. 30 to 45 Mins": "#bc8cff",
                "04. 45 to 60 Mins": "#f9c513",
                "05. Over 1 Hour": "#ea4a5a"
            }
        )
        
        fig_tiers.update_layout(
            **THEME,
            barmode="stack",
            xaxis_title="Percentage Allocation (%)",
            yaxis_title="",
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
        )
        fig_tiers.update_traces(textposition="inside")
        st.plotly_chart(fig_tiers, use_container_width=True)
        
    else:
        st.info("No data available to calculate time tier percentages.")

    st.divider()

    # ── [C] كيرف الـ Rush Hours المزدوج مع منحنى الـ Response Time ──
    st.markdown("### 📈 24-Hour Rush Hours Curve & Response Time Trend")
    st.caption("يوضح المنحنى حجم ضغط الحالات الكلي (المساحة المظللة) مقارنة بمتوسط سرعة الـ Response Time بالدقائق لكل ساعة (الخط البرتقالي).")
    
    if not df_metrics.empty:
        full_hours = list(range(24))
        hourly_stats = df_metrics.groupby("Hour").agg(
            Volume=("Request ID", "count"),
            Avg_Response=("Response Take (min)", "mean")
        ).reindex(full_hours).fillna(0).reset_index()
        
        hourly_stats["Hour Label"] = hourly_stats["Hour"].apply(lambda h: "12 AM" if h==0 else ("12 PM" if h==12 else (f"{h} AM" if h<12 else f"{h-12} PM")))
        
        fig_rush_mobi = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig_rush_mobi.add_trace(
            go.Scatter(
                x=hourly_stats["Hour Label"],
                y=hourly_stats["Volume"],
                name="Ticket Volume (Rush Hours)",
                fill='tozeroy',
                line=dict(color="#58a6ff", width=2),
                hovertemplate="Hour: %{x}<br>Volume: %{y:,} Tickets<extra></extra>"
            ),
            secondary_y=False
        )
        
        fig_rush_mobi.add_trace(
            go.Scatter(
                x=hourly_stats["Hour Label"],
                y=hourly_stats["Avg_Response"],
                name="Avg Response Time (Minutes)",
                mode="lines+markers",
                line=dict(color="#f0883e", width=4, shape="spline"),
                hovertemplate="Hour: %{x}<br>Response: %{y:.1f} Mins<extra></extra>"
            ),
            secondary_y
