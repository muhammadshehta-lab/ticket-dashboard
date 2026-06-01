import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json

# ── 1. تهيئة إعدادات الصفحة التشغيلية ──────────────────────────────────────────
st.set_page_config(
    page_title="In-Store Requests Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 2. تصميم الواجهة والألوان المتطورة الملونة للكروت (KPI Custom Colors CSS) ─────
st.markdown("""
<style>
    .stApp { background: #0d1117; color: #e6edf3; }
    
    /* الستايل الأساسي الموحد للكروت */
    .kpi-container {
        border-radius: 14px;
        padding: 1.2rem 0.8rem;
        text-align: center;
        min-height: 110px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin-bottom: 1rem;
    }
    .kpi-label { font-size: 0.72rem; letter-spacing: .1em; text-transform: uppercase; color: #8b949e; margin-bottom: .4rem; font-weight: 600; }
    .kpi-value { font-size: 1.5rem; font-weight: 800; }
    
    /* الألوان المخصصة لكل كارت مع إضاءة خفيفة مضيئة للحواف */
    .card-total { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }
    .card-completed { background: #12221b; border: 1px solid #3fb950; color: #3fb950; }
    .card-issue { background: #261f12; border: 1px solid #d29922; color: #d29922; }
    .card-frt { background: #2b1c11; border: 1px solid #f0883e; color: #f0883e; }
    .card-aht { background: #221230; border: 1px solid #bc8cff; color: #bc8cff; }
    .card-tat { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }

    [data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
</style>
""", unsafe_allow_html=True)

THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9",
    margin=dict(l=10, r=10, t=20, b=10)
)

# ✅ دالة بناء الكروت الملونة النظيفة بدون نصوص سفلية
def kpi_colored(label, value, card_class):
    return f"""
    <div class="kpi-container {card_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """

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

# ── 3. سحب ومعالجة البيانات من Google Sheets بداخل تكتل آمن ──────────────────
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
        df["Request Type"] = df["Request Type"].fillna("Unknown Type")
        
        date_parsed = pd.to_datetime(df["Request Date"], errors="coerce")
        df["Request Date"] = date_parsed
        df["Date Only"] = date_parsed.dt.date
        df["Hour"] = date_parsed.dt.hour.fillna(0).astype(int)
        df["Day Name"] = date_parsed.dt.day_name().fillna("Unknown")
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

# ── 4. شريط الفلاتر الجانبي (Sidebar Filters) ──────────────────────────────────
with st.sidebar:
    st.markdown("## 💊 Navigation & Filters")
    st.success("📡 Live Sync Active")
    if st.button("🔄 Refresh Data Now", use_container_width=True): load_data_from_sheets.clear()
    df_raw = load_data_from_sheets()
    if df_raw.empty:
        st.warning("Waiting for data configuration...")
        st.stop()
    st.divider()
    
    # أ. فلتر نطاق التاريخ
    min_d = df_raw["Date Only"].dropna().min()
    max_d = df_raw["Date Only"].dropna().max()
    date_val = (min_d, max_d)
    date_range = st.date_input("Date Range", value=date_val, min_value=min_d, max_value=max_d)
    d_from, d_to = date_range if isinstance(date_range, (list, tuple)) and len(date_range) == 2 else (min_d, max_d)
    
    # ب. فلتر الموظفين
    raw_agents = df_raw["Assigned By"].dropna().unique()
    sorted_agents = sorted(raw_agents)
    sel_agents = st.multiselect("Agent Filter", sorted_agents)
    
    # ج. الفلتر الجديد المطلب: تصفية أنواع الطلبات (Request Type Filter)
    raw_types = df_raw["Request Type"].dropna().unique()
    sorted_types = sorted(raw_types)
    sel_types = st.multiselect("Request Type Filter", sorted_types)

# تطبيق شروط الفلترة الشاملة للقائمة الجانبية بناءً على الاختيارات
df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_agents: 
    df = df[df["Assigned By"].isin(sel_agents)]
if sel_types: 
    df = df[df["Request Type"].isin(sel_types)]

# ── 5. العناوين الرئيسية والفلاتر التفاعلية ───────────────────────────────────────
st.markdown("## 💊 In-Store Requests")
st.caption(f"🔍 Search Period: {d_from} to {d_to}")

col_check1, col_check2 = st.columns(2)
with col_check1:
    escalated_only_filter = st.checkbox("🔥 Show Escalated Cases Only (Interactive Data Mapping)", value=False)
with col_check2:
    non_escalated_only_filter = st.checkbox("🟢 Show Non-Escalated Cases Only", value=False)

df_metrics = df.copy()
if escalated_only_filter and not non_escalated_only_filter:
    df_metrics = df_metrics[df_metrics["Is Email"] == True]
elif non_escalated_only_filter and not escalated_only_filter:
    df_metrics = df_metrics[df_metrics["Is Email"] == False]

total_tickets = len(df_metrics)
status_series = df_metrics["Status"].astype(str).str.strip()
comp_success = df_metrics[status_series.str.contains("Closed", na=False, case=False) & ~status_series.str.contains("issue", na=False, case=False)].shape[0]
comp_with_issue = df_metrics[status_series.str.contains("Closed", na=False, case=False) & status_series.str.contains("issue", na=False, case=False)].shape[0]

avg_response_global = df_metrics["Response Take (min)"].mean() if not df_metrics.empty else 0
avg_aht_global = df_metrics["AHT (min)"].mean() if not df_metrics.empty else 0
avg_service_global = df_metrics["Request Take (min)"].mean() if not df_metrics.empty else 0

h_frt = format_minutes_to_hhmmss(avg_response_global)
h_aht = format_minutes_to_hhmmss(avg_aht_global)
h_tat = format_minutes_to_hhmmss(avg_service_global)

# ── [A] الصف العلوي: كروت ملونة ونظيفة تماماً وموزعة بالتساوي ──────────────────
r1_c1, r1_c2, r1_c3, r1_c4, r1_c5, r1_c6 = st.columns(6)

r1_c1.markdown(kpi_colored("Total Tickets", f"{total_tickets:,}", "card-total"), unsafe_allow_html=True)
r1_c2.markdown(kpi_colored("Closed Completed", f"{comp_success:,}", "card-completed"), unsafe_allow_html=True)
r1_c3.markdown(kpi_colored("Closed with Issue", f"{comp_with_issue:,}", "card-issue"), unsafe_allow_html=True)
r1_c4.markdown(kpi_colored("Avg Response (FRT)", h_frt, "card-frt"), unsafe_allow_html=True)
r1_c5.markdown(kpi_colored("Avg Handling (AHT)", h_aht, "card-aht"), unsafe_allow_html=True)
r1_c6.markdown(kpi_colored("Avg Service (TAT)", h_tat, "card-tat"), unsafe_allow_html=True)

st.write("")

# ── [B] مخطط الـ Sunburst المحدث المرتب فئوياً وزمنياً بشكل متجاور ──────────────
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
    category_order = ["Response Time", "Service Resolution"]
    
    sunburst_df["SLA Category"] = pd.Categorical(sunburst_df["SLA Category"], categories=category_order, ordered=True)
    sunburst_df["SLA Tier"] = pd.Categorical(sunburst_df["SLA Tier"], categories=time_order, ordered=True)
    sunburst_df = sunburst_df.sort_values(["SLA Category", "SLA Tier"]).reset_index(drop=True)
    
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
    
    fig_sunburst.update_traces(
        sort=False,  
        textinfo="label+percent parent", 
        hovertemplate="<b>%{label}</b><br>Tickets: %{value:,}<br>Percentage: %{percentParent:.1%}"
    )
    
    fig_sunburst.update_layout(
        **THEME, 
        height=520,
        category_orders={
            "SLA Category": category_order,
            "SLA Tier": time_order
        }
    )
    st.plotly_chart(fig_sunburst, use_container_width=True)

st.divider()

# ── [C] منحنى الـ 24 ساعة المطور بالتسلسل الزمني المتتالي المتقارب ──────────────
if not df_metrics.empty:
    full_hours = list(range(24))
    hourly_stats = df_metrics.groupby("Hour").agg(Volume=("Request ID", "count"), Avg_Response=("Response Take (min)", "mean")).reset_index()
    hourly_stats = hourly_stats.set_index("Hour").reindex(full_hours).fillna(0).reset_index()
    
    h_labels = [ "12 AM" if h==0 else ("12 PM" if h==12 else (f"{h} AM" if h<12 else f"{h-12} PM")) for h in hourly_stats["Hour"] ]
    hourly_stats["Hour Label"] = h_labels
    
    fig_rush_mobi = make_subplots(specs=[[{"secondary_y": True}]])
    fig_rush_mobi.add_trace(go.Scatter(x=hourly_stats["Hour Label"], y=hourly_stats["Volume"], name="Volume (Total Tickets)", fill='tozeroy', line=dict(color="#58a6ff", width=2)), secondary_y=False)
    fig_rush_mobi.add_trace(go.Scatter(x=hourly_stats["Hour Label"], y=hourly_stats["Avg_Response"], name="FRT (Avg Response Take Min)", mode="lines+markers", line=dict(color="#f0883e", width=3, shape="spline")), secondary_y=True)
    
    fig_rush_mobi.update_xaxes(type='category', categoryorder='array', categoryarray=h_labels)
    fig_rush_mobi.update_layout(**THEME, height=450, hovermode="x unified", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig_rush_mobi, use_container_width=True)

# ── [D] الجدول الإحصائي التحليلي السفلي ─────────────────────────────────────────
st.info(f"⏱️ **Average Service Resolution Time (TAT) Across Selected Filter:** {h_tat} (HH:MM:SS) Per Ticket")
st.write("")
st.markdown("### 📋 Detailed Request Type Breakdown & Handling SLA")
if not df_metrics.empty:
    breakdown = df_metrics.groupby("Request Type").agg(Count=("Request ID", "count"), Avg_Service=("Request Take (min)", "mean"), Avg_AHT=("AHT (min)", "mean")).reset_index()
    breakdown["Percentage of Total"] = (breakdown["Count"] / total_tickets * 100).round(1).astype(str) + "%"
    
    breakdown["Average Handling Time (AHT)"] = breakdown["Avg_AHT"].apply(format_minutes_to_hhmmss)
    breakdown["Avg Service Time"] = breakdown["Avg_Service"].apply(format_minutes_to_hhmmss)
    
    display_breakdown = breakdown[["Request Type", "Count", "Percentage of Total", "Average Handling Time (AHT)", "Avg Service Time"]].sort_values("Count", ascending=False)
    st.dataframe(display_breakdown, hide_index=True, use_container_width=True)
