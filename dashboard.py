"""
dashboard.py — In-Store Requests Dashboard (Advanced Segments - Safe Cloud Version)
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
    .kpi-sub { font-size: 0.78rem; color: #3fb950; margin-top: .2rem; }
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

# ── جلب البيانات من جوجل شيت (نسخة فائقة الأمان تدعم Streamlit Secrets) ──
@st.cache_data(ttl=600, show_spinner="Fetching live data from Google Sheets...")
def load_data_from_sheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        # 1. محاولة القراءة من الـ Secrets الآمنة أولاً (للسيرفر الأونلاين)
        if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
            import json
            creds_dict = json.loads(st.secrets["gspread"]["credentials"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            # 2. الحل البديل في حال تشغيل الكود محلياً على جهازك (لو الملف متوفر في الفولدر)
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

        # تأمين الأعمدة الأساسية للتأكد من وجودها لتجنب السيستم كراش
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
        
        # تصنيف حالات التأمين
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
        st.info("تأكد من إعداد الـ Secrets بشكل سليم على Streamlit Cloud أو مراجعة صلاحيات الشيت.")
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

# ── القائمة الجانبية والفلاتر (Sidebar) ──────────────────────────────────────────
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

# تصفية البيانات بناءً على الفلاتر المحددة
df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_agents: df = df[df["Assigned By"].isin(sel_agents)]
if sel_types:  df = df[df["Request Type"].isin(sel_types)]

# ── العنوان الرئيسي ───────────────────────────────────────────────────────────
st.markdown("## 💊 In-Store Requests Dashboard")
st.caption(f"Showing **{len(df):,}** requests out of {len(df_raw):,} — {d_from} to {d_to}")

# ── تقسيم لوحة التحكم إلى تابات (Tabs) ──────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Team Overview", "👥 Agents Performance", "🗃 Raw Data"])

# ==============================================================================
# TAB 1: TEAM OVERVIEW (نظرة عامة على الفريق)
# ==============================================================================
with tab1:
    def kpi(label, value, sub=""):
        return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>'

    t_cases = len(df)
    t_email = df["Is Email"].sum()
    t_ins_sent = df["Has Insurance"].sum()
    t_ins_not = t_cases - t_ins_sent

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi("Total Received", f"{t_cases:,}"), unsafe_allow_html=True)
    c2.markdown(kpi("Email Cases", f"{t_email:,}", f"{(t_email/t_cases)*100:.1f}% of total" if t_cases else "0%"), unsafe_allow_html=True)
    c3.markdown(kpi("Sent To Insurance", f"{t_ins_sent:,}"), unsafe_allow_html=True)
    c4.markdown(kpi("Not Sent To Insurance", f"{t_ins_not:,}"), unsafe_allow_html=True)

    st.write("")
    
    # الخريطة الحرارية وتوزيع التأمين
    col_hm, col_pie = st.columns([2, 1], gap="large")
    with col_hm:
        st.markdown("### 🔥 Daily Volume Heatmap (Hour vs Day)")
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        hm_data = df.groupby(["Day Name", "Hour"]).size().reset_index(name="Cases")
        if not hm_data.empty:
            hm_pivot = hm_data.pivot(index="Day Name", columns="Hour", values="Cases").reindex(days_order).fillna(0)
            fig_hm = px.imshow(hm_pivot, text_auto=True, aspect="auto", color_continuous_scale="Blues",
                               labels=dict(x="Hour of Day", y="Day of Week", color="Cases"))
            fig_hm.update_layout(**THEME, coloraxis_showscale=False)
            st.plotly_chart(fig_hm, use_container_width=True)
        else:
            st.info("No data available for Heatmap.")

    with col_pie:
        st.markdown("### 🏢 Insurance Routing")
        ins_df = pd.DataFrame({"Category": ["Sent to Insurance", "Internal / Not Sent"], "Count": [t_ins_sent, t_ins_not]})
        fig_ins = px.pie(ins_df, names="Category", values="Count", hole=0.5, color_discrete_sequence=["#3fb950", "#1f4068"])
        fig_ins.update_layout(**THEME)
        st.plotly_chart(fig_ins, use_container_width=True)

    # حجم العمل بالساعة مقارنة بوقت الخدمة (Dual-Axis Chart)
    st.markdown("### ⏱️ Hourly Volume vs. Average Service Time")
    hourly = df.groupby("Hour").agg(Cases=("Request ID", "count"), Avg_Time=("Request Take (min)", "mean")).reset_index()
    
    if not hourly.empty:
        fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
        fig_dual.add_trace(go.Bar(x=hourly["Hour"], y=hourly["Cases"], name="Total Cases", marker_color="#58a6ff"), secondary_y=False)
        fig_dual.add_trace(go.Scatter(x=hourly["Hour"], y=hourly["Avg_Time"], name="Avg Service Time (min)", line=dict(color="#f0883e", width=3), mode="lines+markers"), secondary_y=True)
        # تم إصلاح القوس المفقود هنا بالكامل لضمان استقرار التشغيل
        fig_dual.update_layout(**THEME, hovermode="x unified", xaxis=dict(tickmode="linear", dtick=1))
        fig_dual.update_yaxes(title_text="Number of Cases", secondary_y=False)
        fig_dual.update_yaxes(title_text="Avg Service Time (min)", secondary_y=True, showgrid=False)
        st.plotly_chart(fig_dual, use_container_width=True)

    # منحنى التوزيع الإحصائي لوقت الخدمة
    st.markdown("### 📈 Service Time Distribution Curve")
    if "Request Take (min)" in df.columns and not df["Request Take (min)"].dropna().empty:
        fig_dist = px.histogram(df, x="Request Take (min)", nbins=50, marginal="box", 
                                color_discrete_sequence=["#bc8cff"], title="Distribution of Request Service Time (Minutes)")
        fig_dist.update_layout(**THEME, xaxis_title="Minutes", yaxis_title="Frequency")
        st.plotly_chart(fig_dist, use_container_width=True)
    else:
        st.info("Service time data not sufficient for curve.")


# ==============================================================================
# TAB 2: AGENTS PERFORMANCE (أداء الزملاء التفصيلي)
# ==============================================================================
with tab2:
    st.markdown("### 🧑‍💻 Agent Detailed Performance")

    agent_stats = calc_attendance(df, min_cases)
    
    # فصل نوع الإغلاق (Completed بنجاح أو بمشكلة)
    closed_df = df[df["Status"].astype(str).str.contains("Closed", na=False, case=False)].copy()
    
    if not closed_df.empty:
        closed_df["Closed Type"] = closed_df["Status"].apply(
            lambda x: "Completed With Issue" if "issue" in str(x).lower() else "Completed Successfully"
        )
        closed_breakdown = closed_df.groupby(["Assigned By", "Closed Type"]).size().unstack(fill_value=0).reset_index()
        if not closed_breakdown.empty:
            agent_stats = agent_stats.merge(closed_breakdown, on="Assigned By", how="left").fillna(0)

    # ترتيب الجدول النهائي
    if not agent_stats.empty:
        if "Completed Successfully" not in agent_stats.columns: agent_stats["Completed Successfully"] = 0
        if "Completed With Issue" not in agent_stats.columns: agent_stats["Completed With Issue"] = 0
        
        agent_stats = agent_stats.sort_values("Total Handled Cases", ascending=False)
        
        # إعادة تسمية الأعمدة للمظهر الإنجليزي الاحترافي
        columns_rename = {
            "Assigned By": "Agent Name",
            "Total Handled Cases": "Total Cases",
            "Attendance Days": "Working Days",
            "Completed Successfully": "Closed Successfully",
            "Completed With Issue": "Closed With Issue"
        }
        
        col_tbl, col_bar = st.columns([2, 3], gap="medium")
        
        with col_tbl:
            st.dataframe(agent_stats.rename(columns=columns_rename), hide_index=True, use_container_width=True, height=450)

        with col_bar:
            plot_closed = closed_df.groupby(["Assigned By", "Closed Type"]).size().reset_index(name="Count")
            fig_stack = px.bar(plot_closed, x="Assigned By", y="Count", color="Closed Type", 
                               color_discrete_map={"Completed Successfully": "#3fb950", "Completed With Issue": "#d29922"},
                               title="Closed Status Breakdown per Agent")
            fig_stack.update_layout(**THEME, xaxis={'categoryorder':'total descending'}, 
                                   legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_stack, use_container_width=True)
    else:
        st.info("No agent data found for the selected filters.")


# ==============================================================================
# TAB 3: RAW DATA (البيانات الخام)
# ==============================================================================
with tab3:
    st.markdown("### 🗃 Raw Data Explorer")
    search = st.text_input("🔍 Search in any column")
    show_df = df.copy()
    if search:
        mask = show_df.astype(str).apply(lambda c: c.str.contains(search, case=False, na=False)).any(axis=1)
        show_df = show_df[mask]

    display_cols = ["Request ID", "Request Date", "Request Type", "Status", "Assigned By", 
                    "Store Code", "Insurance Company", "Request Take", "Response Take"]
    st.dataframe(show_df[[c for c in display_cols if c in show_df.columns]], use_container_width=True, height=400)

    csv = show_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download Current View as CSV", data=csv, file_name="filtered_requests.csv", mime="text/csv")

st.divider()
st.caption("al-Dawaa • Advanced In-Store Requests Dashboard • Powered by Streamlit")
