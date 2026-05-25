"""
dashboard.py — In-Store Requests & Ticket Analytics Dashboard (UX/UI Edition)
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

        required_cols = ["Request ID", "Request Date", "Request Type", "Status", "Request Take", "Response Take"]
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
        
        if "Is Special Request(By Email)" in df.columns:
            df["Is Email"] = df["Is Special Request(By Email)"].astype(str).str.strip().str.upper() == "YES"
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
        st.warning("Waiting for data...")
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

    # 1. UI Specific Filter Component: Filter by Special Email
    st.markdown("#### 🔍 Specific Filter Context")
    email_filter = st.checkbox("🎯 Filter Dashboard Content by Special Email Requests Only", value=False)
    
    df_metrics = df[df["Is Email"] == True].copy() if email_filter else df.copy()

    # حساب الـ KPIs المطلوبة بالظبط لـ Top Row Summary
    total_tickets = len(df_metrics)
    closed_df = df_metrics[df_metrics["Status"].astype(str).str.contains("Closed", na=False, case=False)]
    
    comp_success = closed_df[~closed_df["Status"].astype(str).str.lower().str.contains("issue")].shape[0]
    comp_with_issue = closed_df[closed_df["Status"].astype(str).str.lower().str.contains("issue")].shape[0]
    
    # حساب الحالات المصعدة (المفتوحة/المعلقة حالياً)
    escalated_cases = total_tickets - (comp_success + comp_with_issue)
    
    # حساب الوقت التراكمي الكلي (Total Cumulative Service Time)
    total_cumulative_minutes = df_metrics["Request Take (min)"].sum()
    total_cumulative_hours = total_cumulative_minutes / 60

    # عرض كروت الـ KPI
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi("Total Number of Tickets", f"{total_tickets:,}", "All registered cases", '#58a6ff'), unsafe_allow_html=True)
    c2.markdown(kpi("Closed Completed", f"{comp_success:,}", f"{((comp_success/total_tickets*100) if total_tickets else 0):.1f}% resolved", '#3fb950'), unsafe_allow_html=True)
    c3.markdown(kpi("Closed With Issue", f"{comp_with_issue:,}", f"{((comp_with_issue/total_tickets*100) if total_tickets else 0):.1f}% complications", '#d29922'), unsafe_allow_html=True)
    c4.markdown(kpi("Escalated Cases", f"{escalated_cases:,}", "Pending / Open status", '#f85149'), unsafe_allow_html=True)

    st.write("")

    # 2. Time Segmentation & Analytics (Charts)
    col_an1, col_an2 = st.columns([1, 1], gap="large")
    
    with col_an1:
        st.markdown("### ⏳ Time Segmentation Distribution Curve")
        st.caption("Side-by-side distribution analysis for Response Time vs. Service Time.")
        
        fig_curves = go.Figure()
        if not df_metrics.empty:
            fig_curves.add_trace(go.Histogram(x=df_metrics["Response Take (min)"], name="Response Time (Touchpoint)", marker_color="#58a6ff", opacity=0.75))
            fig_curves.add_trace(go.Histogram(x=df_metrics["Request Take (min)"], name="Service Time (Resolution)", marker_color="#bc8cff", opacity=0.75))
        fig_curves.update_layout(**THEME, barmode='overlay', xaxis_title="Minutes", yaxis_title="Ticket Count")
        st.plotly_chart(fig_curves, use_container_width=True)

    with col_an2:
        st.markdown("### 📈 24-Hour Rush Hours Curve & Cumulative Volume")
        full_hours = list(range(24))
        hourly_data = df_metrics.groupby("Hour").size().reindex(full_hours).fillna(0).reset_index(name="Volume")
        
        # تنسيق الساعات لـ AM/PM
        hourly_data["Hour Label"] = hourly_data["Hour"].apply(lambda h: "12 AM" if h==0 else ("12 PM" if h==12 else (f"{h} AM" if h<12 else f"{h-12} PM")))
        
        fig_rush = px.area(hourly_data, x="Hour Label", y="Volume", color_discrete_sequence=["#58a6ff"], title="Fluctuations to identify peak hours")
        fig_rush.update_layout(**THEME)
        st.plotly_chart(fig_rush, use_container_width=True)

    # عرض كرت إحصائية الوقت التراكمي المستقل
    st.info(f"⏱️ **Total Cumulative Service Time Spent Across All Tickets:** {total_cumulative_hours:,.1f} Active Operational Hours")

    st.write("")

    # 3. Request Breakdown Table & Insights
    st.markdown("### 📋 Detailed Request Type Breakdown & Handling SLA")
    if not df_metrics.empty:
        breakdown = df_metrics.groupby("Request Type").agg(
            Count=("Request ID", "count"),
            Avg_Service=("Request Take (min)", "mean")
        ).reset_index()
        
        breakdown["Percentage of Total"] = (breakdown["Count"] / total_tickets * 100).round(1).astype(str) + "%"
        breakdown["Avg Service Time"] = breakdown["Avg_Service"].round(1).astype(str) + " min"
        
        # إعادة ترتيب وتجميل الأعمدة للعرض
        display_breakdown = breakdown[["Request Type", "Count", "Percentage of Total", "Avg Service Time"]].sort_values("Count", ascending=False)
        st.dataframe(display_breakdown, hide_index=True, use_container_width=True)


# ==============================================================================
# TAB 2: MANUAL INPUTS & VALUE TRACKING
# ==============================================================================
with tab2:
    st.markdown("## 🛠️ Operational Logging & Value Adjustments")
    st.caption("Track financial weights, direct walk-ins, or off-system tasks that lack automation.")
    
    col_f1, col_f2 = st.columns(2, gap="large")
    
    # 1. Support Value Entry Form
    with col_f1:
        st.markdown("<div class='form-container'>", unsafe_allow_html=True)
        st.subheader("💰 1. Support Value Entry Form")
        
        with st.form("support_value_form", clear_on_submit=True):
            val_amount = st.number_input("Support Value amount (Saved Cost / Weight)", min_value=0.0, step=10.0, value=0.0)
            val_type = st.selectbox("Value Category", ["Monetary Saved ($)", "Resource Cost Optimization", "Tier Weight Factor"])
            val_notes = st.text_area("Justification / Strategic Notes")
            
            submit_val = st.form_submit_button("💾 Save / Submit Value")
            if submit_val:
                st.session_state.manual_values_log.append({
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Value": f"{val_amount:,.1f}",
                    "Category": val_type,
                    "Justification": val_notes
                })
                st.toast("✅ Support Value Saved Successfully!", icon="💰")
        st.markdown("</div>", unsafe_allow_html=True)
        
        # عرض سجل تاريخ القيم المدخلة مسبقاً (History Log)
        st.markdown("##### 📜 Historical Support Values Log")
        if st.session_state.manual_values_log:
            st.dataframe(pd.DataFrame(st.session_state.manual_values_log), hide_index=True, use_container_width=True)
        else:
            st.caption("No custom values logged in this session yet.")

    # 2. Manual Support Cases Logger
    with col_f2:
        st.markdown("<div class='form-container'>", unsafe_allow_html=True)
        st.subheader("📞 2. Manual Support Cases Logger")
        
        with st.form("manual_case_form", clear_on_submit=True):
            case_title = st.text_input("Case Title (e.g., Direct Call, Walk-In)")
            case_desc = st.text_area("Detailed Description of request")
            case_date = st.date_input("Date of Occurrence", value=datetime.today())
            case_owner = st.text_input("Logged By (Owner)")
            
            submit_case = st.form_submit_button("📝 Register Manual Case")
            if submit_case:
                if case_title.strip() == "":
                    st.error("Validation Error: Case Title cannot be empty.")
                else:
                    st.session_state.manual_cases_log.append({
                        "Date": case_date.strftime("%Y-%m-%d"),
                        "Case Title": case_title,
                        "Description": case_desc,
                        "Owner": case_owner if case_owner else "Anonymous"
                    })
                    st.toast("✅ Off-System Case Logged Successfully!", icon="📞")
        st.markdown("</div>", unsafe_allow_html=True)
        
        # عرض سجل تاريخ الحالات المضافة يدوياً
        st.markdown("##### 📋 Registered Off-System Cases Table")
        if st.session_state.manual_cases_log:
            st.dataframe(pd.DataFrame(st.session_state.manual_cases_log), hide_index=True, use_container_width=True)
        else:
            st.caption("No manual off-system cases tracked yet.")
