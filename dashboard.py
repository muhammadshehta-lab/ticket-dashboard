"""
dashboard.py — In-Store Requests Dashboard (Total Service Time KPI Edition)
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

# ── جلب البيانات من جوجل شيت (يدعم قراءة أي تابات جديدة تلقائياً) ───────────────
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
                cols = [str(c).strip() for c in data[0]]
                df_tab = pd.DataFrame(data[1:], columns=cols)
                all_dfs.append(df_tab)

        if not all_dfs: 
            return pd.DataFrame()

        df = pd.concat(all_dfs, ignore_index=True, sort=False)
        df.replace("", np.nan, inplace=True)

        req_cols = [
            "Request ID", "Request Date", "Request Type", 
            "Status", "Request Take", "Response Take", 
            "First Action Take", "Assigned By"
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
        
        if "Is Special Request(By Email)" in df.columns:
            mail_col = df["Is Special Request(By Email)"]
            has_mail = mail_col.astype(str).str.strip().str.lower()
            df["Is Email"] = (has_mail == "yes")
        else:
            df["Is Email"] = False

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
    st.markdown("## 💊 Navigation & Filters")
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
    
    # 1. Closed Completed: الحالات المغلقة بدون مشاكل
    comp_success = df_metrics[
        status_series.str.contains("Closed", na=False, case=False) & 
        ~status_series.str.contains("issue", na=False, case=False)
    ].shape[0]
    
    # 2. Closed with Issue: الحالات المغلقة ولكن كان بها مشكلة
    comp_with_issue = df_metrics[
        status_series.str.contains("Closed", na=False, case=False) & 
        status_series.str.contains("issue", na=False, case=False)
    ].shape[0]
    
    # 3. Escalated Cases
    escalated_cases = df_metrics[df_metrics["Is Email"] == True].shape[0]
    
    # حساب متوسط الـ Response والـ AHT المطلوبين للفلاش كاردز
    avg_response_global = df_metrics["Response Take (min)"].mean() if not df_metrics.empty else 0
    avg_aht_global = df_metrics["AHT (min)"].mean() if not df_metrics.empty else 0
    
    # 🎯 الحسبة الجديدة المطلوبة: حساب الـ Total Service Time التراكمي لـ Request Take بالدقائق وتحويلها لساعات
    total_cumulative_minutes = df_metrics["Request Take (min)"].sum()
    total_cumulative_hours = total_cumulative_minutes / 60

    # حساب مجاميع القيم اليدوية من Tab 2
    total_logged_manual_cases = len(st.session_state.manual_cases_log)
    total_support_value_sum = sum([float(str(item["Value"]).replace(",", "")) for item in st.session_state.manual_values_log])

    # ── [A] الصف العلوي: الـ 8 فلاش كاردز المحدثة بـ Total Service Time ذكياً
    r1_c1, r1_c2, r1_c3, r1_c4, r1_c5, r1_c6, r1_c7, r1_c8 = st.columns(8)
    
    # دمج الـ Total Tickets والـ Total Service Time في عمود واحد متناسق جداً للمقارنة الإدارية
    ticket_sub_text = f"Total Service: {total_cumulative_hours:,.1f} Hours"
    r1_c1.markdown(kpi("Total Tickets", f"{total_tickets:,}", ticket_sub_text, '#58a6ff'), unsafe_allow_html=True)
    
    r1_c2.markdown(kpi("Closed Completed", f"{comp_success:,}", "Resolved clean", '#3fb950'), unsafe_allow_html=True)
    r1_c3.markdown(kpi("Closed with Issue", f"{comp_with_issue:,}", "With complications", '#d29922'), unsafe_allow_html=True)
    r1_c4.markdown(kpi("Escalated Cases", f"{escalated_cases:,}", "Email Yes volume count", '#f85149'), unsafe_allow_html=True)
    
    r1_c5.markdown(kpi("Avr Response Time", f"{avg_response_global:.1f} m", "Avg acknowledgement", '#f0883e'), unsafe_allow_html=True)
    r1_c6.markdown(kpi("Avr Handling Time", f"{avg_aht_global:.1f} m", "Response + First Action", '#bc8cff'), unsafe_allow_html=True)
    
    r1_c7.markdown(kpi("Total Support Value", f"{total_support_value_sum:,.1f}", "Saved weight sum", '#2ea44f'), unsafe_allow_html=True)
    r1_c8.markdown(kpi("Manual Support Cases", f"{total_logged_manual_cases:,}", "Off-system logging", '#bc8cff'), unsafe_allow_html=True)

    st.write("")

    # ── [B] المخطط الدائري التفاعلي (SLA Interactive Sunburst Chart)
    st.markdown("### 🌀 SLA Performance Breakdown Sunburst Matrix")
    st.caption("اضغط على أي حلقة داخلية للتكبير وعرض النسب المئوية الدقيقة للتوزيع التراكمي للسرعة.")
    
    if not df_metrics.empty:
        df_metrics["Response Tier"] = df_metrics["Response Take (min)"].apply(assign_time_tier)
        df_metrics["Service Tier"] = df_metrics["Request Take (min)"].apply(assign_time_tier)
        
        all_tiers = ["Under 15 Mins", "15-30 Mins", "30-45 Mins", "45-60 Mins", "Over 1 Hour"]
        
        r_data = df_metrics.groupby("Response Tier").size().reset_index(name="Tickets")
        r_data["SLA Category"] = "Response Time"
        r_data.rename(columns={"Response Tier": "SLA Tier"}, inplace=True)
        
        s_data = df_metrics.groupby("Service Tier").size().reset_index(name="Tickets")
        s_data["SLA Category"] = "Service Resolution"
        s_data.rename(columns={"Service Tier": "SLA Tier"}, inplace=True)
        
        sunburst_df = pd.concat([r_data, s_data], ignore_index=True)
        
        fig_sunburst = px.sunburst(
            sunburst_df,
            path=["SLA Category", "SLA Tier"],
            values="Tickets",
            color="SLA Tier",
            color_discrete_map={
                "Under 15 Mins": "#2ea44f",
                "15-30 Mins": "#2188ff",
                "30-45 Mins": "#bc8cff",
                "45-60 Mins": "#f9c513",
                "Over 1 Hour": "#ea4a5a"
            },
            branchvalues="total"
        )
        
        fig_sunburst.update_layout(**THEME, height=500)
        fig_sunburst.update_traces(
            textinfo="label+percent parent",
            hovertemplate="<b>%{label}</b><br>Tickets: %{value:,}<br>Percentage: %{percentParent:.1%}"
        )
        st.plotly_chart(fig_sunburst, use_container_width=True)
        
    else:
        st.info("No data available to calculate SLA Sunburst tiers.")

    st.divider()

    # ── [C] كيرف الـ Rush Hours المزدوج مع منحنى الـ Response Time ──
    st.markdown("### 📈 24-Hour Rush Hours Curve & Response Time Trend")
    st.caption("يوضح المنحنى حجم ضغط الحالات الكلي مقارنة بمتوسط سرعة الـ Response Time بالدقائق لكل ساعة.")
    
    if not df_metrics.empty:
        full_hours = list(range(24))
        hourly_stats = df_metrics.groupby("Hour").agg(
            Volume=("Request ID", "count"),
            Avg_Response=("Response Take (min)", "mean")
        ).reindex(full_hours).fillna(0).reset_index()
        
        h_labels = []
        for h in hourly_stats["Hour"]:
            if h == 0: lbl = "12 AM"
            elif h == 12: lbl = "12 PM"
            elif h < 12: lbl = f"{h} AM"
            else: lbl = f"{h-12} PM"
            h_labels.append(lbl)
            
        hourly_stats["Hour Label"] = h_labels
        
        fig_rush_mobi = make_subplots(specs=[[{"secondary_y": True}]])
        
        t1_x = hourly_stats["Hour Label"]
        t1_y = hourly_stats["Volume"]
        t1_trace = go.Scatter(
            x=t1_x, y=t1_y,
            name="Ticket Volume (Rush Hours)", fill='tozeroy',
            line=dict(color="#58a6ff", width=2),
            hovertemplate="Volume: %{y:,}<extra></extra>"
        )
        fig_rush_mobi.add_trace(t1_trace, secondary_y=False)
        
        t2_x = hourly_stats["Hour Label"]
        t2_y = hourly_stats["Avg_Response"]
        t2_trace = go.Scatter(
            x=t2_x, y=t2_y,
            name="Avg Response Time (Minutes)", mode="lines+markers",
            line=dict(color="#f0883e", width=4, shape="spline"),
            hovertemplate="Response: %{y:.1f} Min<extra></extra>"
        )
        fig_rush_mobi.add_trace(t2_trace, secondary_y=True)
        
        fig_rush_mobi.update_layout(
            **THEME,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
        )
        
        fig_rush_mobi.update_xaxes(title_text="24-Hour Shift Timeline", tickmode="array", tickvals=hourly_stats["Hour Label"])
        fig_rush_mobi.update_yaxes(title_text="Number of Tickets (Volume)", secondary_y=False)
        fig_rush_mobi.update_yaxes(title_text="Avg Response Speed (Minutes)", secondary_y=True, showgrid=False)
        
        st.plotly_chart(fig_rush_mobi, use_container_width=True)
    else:
        st.info("No data available for timeline analysis.")

    # تم الحفاظ على السطر التوضيحي بالأسفل
    st.info(f"⏱️ **Total Cumulative Service Time Spent Across All Tickets:** {total_cumulative_hours:,.1f} Active Operational Hours")
    st.write("")

    # ── [D] جدول الـ Request Breakdown بالتفصيل في الأسفل
    st.markdown("### 📋 Detailed Request Type Breakdown & Handling SLA")
    if not df_metrics.empty:
        breakdown = df_metrics.groupby("Request Type").agg(
            Count=("Request ID", "count"),
            Avg_Service=("Request Take (min)", "mean"),
            Avg_AHT=("AHT (min)", "mean")
        ).reset_index()
        
        breakdown["Percentage of Total"] = (breakdown["Count"] / total_tickets * 100).round(1).astype(str) + "%"
        breakdown["Average Handling Time (AHT)"] = breakdown["Avg_AHT"].round(1).astype(str) + " min"
        breakdown["Avg Service Time"] = breakdown["Avg_Service"].round(1).astype(str) + " min"
        
        display_breakdown = breakdown[["Request Type", "Count", "Percentage of Total", "Average Handling Time (AHT)", "Avg Service Time"]].sort_values("Count", ascending=False)
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
            val_amount = st.number_input("Support Value amount", min_value=0.0, step=10.0, value=0.0)
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
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
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
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("##### 📋 Registered Off-System Cases Table")
        if st.session_state.manual_cases_log:
            st.dataframe(pd.DataFrame(st.session_state.manual_cases_log), hide_index=True, use_container_width=True)
        else:
            st.caption("No manual off-system cases tracked yet.")
