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
    .card-total      { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }
    .card-completed  { background: #12221b; border: 1px solid #3fb950; color: #3fb950; }
    .card-issue      { background: #261f12; border: 1px solid #d29922; color: #d29922; }
    .card-frt        { background: #2b1c11; border: 1px solid #f0883e; color: #f0883e; }
    .card-aht        { background: #221230; border: 1px solid #bc8cff; color: #bc8cff; }
    .card-tat        { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }

    [data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
</style>
""", unsafe_allow_html=True)

THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9",
    margin=dict(l=10, r=10, t=50, b=10)
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

# Alias used in Tab 2 scorecard
fmt_m = format_minutes_to_hhmmss

def assign_time_tier(m):
    if m <= 15: return "Under 15 Mins"
    if m <= 30: return "15-30 Mins"
    if m <= 45: return "30-45 Mins"
    if m <= 60: return "45-60 Mins"
    return "Over 1 Hour"

# قاموس ترجمة أسماء الأيام للعربية
DAYS_ARABIC = {
    "Saturday":  "السبت",
    "Sunday":    "الأحد",
    "Monday":    "الإثنين",
    "Tuesday":   "الثلاثاء",
    "Wednesday": "الأربعاء",
    "Thursday":  "الخميس",
    "Friday":    "الجمعة"
}

# ── 3. سحب ومعالجة البيانات من Google Sheets بداخل تكتل آمن ومستقر ─────────────
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
                    if "id" in c_low and "req" in c_low:                       target = "Request ID"
                    elif "date" in c_low:                                       target = "Request Date"
                    elif "type" in c_low:                                       target = "Request Type"
                    elif "status" in c_low:                                     target = "Status"
                    elif "assigned" in c_low or "agent" in c_low:              target = "Assigned By"
                    elif "response" in c_low and "take" in c_low:              target = "Response Take"
                    elif "action" in c_low and "take" in c_low:                target = "First Action Take"
                    elif "request" in c_low and "take" in c_low:               target = "Request Take"
                    elif "email" in c_low or "special" in c_low:               target = "Is Special Request(By Email)"

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

        df["Status"]       = df["Status"].fillna("Unknown")
        df["Assigned By"]  = df["Assigned By"].fillna("Unassigned")
        df["Request Type"] = df["Request Type"].fillna("Unknown Type")

        date_parsed = pd.to_datetime(df["Request Date"], errors="coerce")
        df["Request Date"]          = date_parsed
        df["Date Only"]             = date_parsed.dt.date
        df["Hour"]                  = date_parsed.dt.hour.fillna(0).astype(int)
        df["Day Name"]              = date_parsed.dt.day_name().fillna("Unknown")
        df["Request Take (min)"]    = df["Request Take"].apply(time_to_minutes).fillna(0)
        df["Response Take (min)"]   = df["Response Take"].apply(time_to_minutes).fillna(0)
        df["First Action Take (min)"] = df["First Action Take"].apply(time_to_minutes).fillna(0)
        df["AHT (min)"]             = df["First Action Take (min)"]

        mail_col  = df["Is Special Request(By Email)"].astype(str).str.strip().str.lower()
        df["Is Email"] = (mail_col == "yes")
        return df
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return pd.DataFrame()


# ── 4. شريط الفلاتر الجانبي (Sidebar Filters) ──────────────────────────────────
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

    # أ. فلتر نطاق التاريخ
    min_d = df_raw["Date Only"].dropna().min()
    max_d = df_raw["Date Only"].dropna().max()
    date_val   = (min_d, max_d)
    date_range = st.date_input("Date Range", value=date_val, min_value=min_d, max_value=max_d)

    d_from, d_to = (
        date_range if isinstance(date_range, (list, tuple)) and len(date_range) == 2
        else (min_d, max_d)
    )

    if d_from == d_to:
        day_en = pd.to_datetime(d_from).day_name()
        day_ar = DAYS_ARABIC.get(day_en, day_en)
        st.caption(f"📅 اليوم المحدد: **{day_ar}**")

    st.divider()

    # ب. فلتر الموظفين
    raw_agents   = df_raw["Assigned By"].dropna().unique()
    sorted_agents = sorted(raw_agents)
    sel_agents   = st.multiselect("Agent Filter", sorted_agents)

    # ج. فلتر أنواع الطلبات
    raw_types   = df_raw["Request Type"].dropna().unique()
    sorted_types = sorted(raw_types)
    sel_types   = st.multiselect("Request Type Filter", sorted_types)


# ── تطبيق فلاتر الشريط الجانبي ───────────────────────────────────────────────────
df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_agents:
    df = df[df["Assigned By"].isin(sel_agents)]
if sel_types:
    df = df[df["Request Type"].isin(sel_types)]


# ── 5. العناوين الرئيسية ──────────────────────────────────────────────────────────
if d_from == d_to:
    day_en = pd.to_datetime(d_from).day_name()
    day_ar = DAYS_ARABIC.get(day_en, day_en)
    caption_text = f"🔍 Search Period: {d_from} ({day_ar})"
else:
    caption_text = f"🔍 Search Period: {d_from} to {d_to}"

st.markdown("## 💊 In-Store Requests")
st.caption(caption_text)


# ══════════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["📈 Tab 1: Operational Insights", "👥 Tab 2: Team Performance and KPIs"])


# ══════════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Operational Insights (unchanged)
# ══════════════════════════════════════════════════════════════════════════════════
with tab1:

    col_check1, col_check2 = st.columns(2)
    with col_check1:
        escalated_only_filter = st.checkbox(
            "🔥 Show Escalated Cases Only (Interactive Data Mapping)", value=False, key="t1_esc"
        )
    with col_check2:
        non_escalated_only_filter = st.checkbox(
            "🟢 Show Non-Escalated Cases Only", value=False, key="t1_nonesc"
        )

    df_metrics = df.copy()
    if escalated_only_filter and not non_escalated_only_filter:
        df_metrics = df_metrics[df_metrics["Is Email"] == True]
    elif non_escalated_only_filter and not escalated_only_filter:
        df_metrics = df_metrics[df_metrics["Is Email"] == False]

    total_tickets   = len(df_metrics)
    status_series   = df_metrics["Status"].astype(str).str.strip()
    comp_success    = df_metrics[
        status_series.str.contains("Closed", na=False, case=False) &
        ~status_series.str.contains("issue", na=False, case=False)
    ].shape[0]
    comp_with_issue = df_metrics[
        status_series.str.contains("Closed", na=False, case=False) &
        status_series.str.contains("issue", na=False, case=False)
    ].shape[0]

    avg_response_global = df_metrics["Response Take (min)"].mean() if not df_metrics.empty else 0
    avg_aht_global      = df_metrics["AHT (min)"].mean()           if not df_metrics.empty else 0
    avg_service_global  = df_metrics["Request Take (min)"].mean()  if not df_metrics.empty else 0

    h_frt = format_minutes_to_hhmmss(avg_response_global)
    h_aht = format_minutes_to_hhmmss(avg_aht_global)
    h_tat = format_minutes_to_hhmmss(avg_service_global)

    # ── [A] KPI Cards ────────────────────────────────────────────────────────────
    r1_c1, r1_c2, r1_c3, r1_c4, r1_c5, r1_c6 = st.columns(6)
    r1_c1.markdown(kpi_colored("Total Tickets",         f"{total_tickets:,}",   "card-total"),     unsafe_allow_html=True)
    r1_c2.markdown(kpi_colored("Closed Completed",      f"{comp_success:,}",    "card-completed"), unsafe_allow_html=True)
    r1_c3.markdown(kpi_colored("Closed with Issue",     f"{comp_with_issue:,}", "card-issue"),     unsafe_allow_html=True)
    r1_c4.markdown(kpi_colored("Avg Response (FRT)",    h_frt,                  "card-frt"),       unsafe_allow_html=True)
    r1_c5.markdown(kpi_colored("Avg Handling (AHT)",    h_aht,                  "card-aht"),       unsafe_allow_html=True)
    r1_c6.markdown(kpi_colored("Avg Service (TAT)",     h_tat,                  "card-tat"),       unsafe_allow_html=True)

    st.write("")

    # ── [B] Sunburst ─────────────────────────────────────────────────────────────
    if not df_metrics.empty:
        df_metrics["Response Tier"] = df_metrics["Response Take (min)"].apply(assign_time_tier)
        df_metrics["Service Tier"]  = df_metrics["Request Take (min)"].apply(assign_time_tier)

        r_data = df_metrics.groupby("Response Tier").size().reset_index(name="Tickets")
        r_data["SLA Category"] = "Response Time"
        r_data.rename(columns={"Response Tier": "SLA Tier"}, inplace=True)

        s_data = df_metrics.groupby("Service Tier").size().reset_index(name="Tickets")
        s_data["SLA Category"] = "Service Resolution"
        s_data.rename(columns={"Service Tier": "SLA Tier"}, inplace=True)

        sunburst_df = pd.concat([r_data, s_data], ignore_index=True)

        time_order     = ["Under 15 Mins", "15-30 Mins", "30-45 Mins", "45-60 Mins", "Over 1 Hour"]
        category_order = ["Response Time", "Service Resolution"]

        sunburst_df["SLA Category"] = pd.Categorical(sunburst_df["SLA Category"], categories=category_order, ordered=True)
        sunburst_df["SLA Tier"]     = pd.Categorical(sunburst_df["SLA Tier"],     categories=time_order,     ordered=True)
        sunburst_df = sunburst_df.sort_values(["SLA Category", "SLA Tier"]).reset_index(drop=True)
        sunburst_df["SLA Category"] = sunburst_df["SLA Category"].astype(str)
        sunburst_df["SLA Tier"]     = sunburst_df["SLA Tier"].astype(str)

        fig_sunburst = px.sunburst(
            sunburst_df,
            path=["SLA Category", "SLA Tier"],
            values="Tickets",
            color="SLA Tier",
            color_discrete_map={
                "Under 15 Mins": "#2ea44f",
                "15-30 Mins":    "#2188ff",
                "30-45 Mins":    "#bc8cff",
                "45-60 Mins":    "#f9c513",
                "Over 1 Hour":   "#ea4a5a"
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
            title_text="SLA Compliance & Time Tiers Breakdown",
            title_font_size=18,
            title_font_family="Inter, sans-serif",
            title_font_color="#e6edf3",
            hoverlabel_font_size=14,
            hoverlabel_font_family="Inter, sans-serif"
        )
        st.plotly_chart(fig_sunburst, use_container_width=True)

    st.divider()

    # ── [C] 24-Hour Rush Curve ───────────────────────────────────────────────────
    if not df_metrics.empty:
        full_hours   = list(range(24))
        hourly_stats = df_metrics.groupby("Hour").agg(
            Volume=("Request ID", "count"),
            Avg_Response=("Response Take (min)", "mean")
        ).reset_index()
        hourly_stats = hourly_stats.set_index("Hour").reindex(full_hours).fillna(0).reset_index()

        h_labels = [
            "12 AM" if h == 0 else ("12 PM" if h == 12 else (f"{h} AM" if h < 12 else f"{h-12} PM"))
            for h in hourly_stats["Hour"]
        ]
        hourly_stats["Hour Label"] = h_labels

        fig_rush_mobi = make_subplots(specs=[[{"secondary_y": True}]])
        fig_rush_mobi.add_trace(
            go.Scatter(
                x=hourly_stats["Hour Label"], y=hourly_stats["Volume"],
                name="Volume (Total Tickets)", fill="tozeroy",
                line=dict(color="#58a6ff", width=2)
            ),
            secondary_y=False
        )
        fig_rush_mobi.add_trace(
            go.Scatter(
                x=hourly_stats["Hour Label"], y=hourly_stats["Avg_Response"],
                name="FRT (Avg Response Take Min)", mode="lines+markers",
                line=dict(color="#f0883e", width=3, shape="spline")
            ),
            secondary_y=True
        )
        fig_rush_mobi.update_xaxes(type="category", categoryorder="array", categoryarray=h_labels)
        fig_rush_mobi.update_layout(
            **THEME,
            height=450,
            hovermode="x unified",
            legend_orientation="h",
            legend_y=1.1,
            title_text="Hourly Performance: Ticket Volume vs Average Response Time (FRT)",
            title_font_size=18,
            title_font_family="Inter, sans-serif",
            title_font_color="#e6edf3",
            hoverlabel_font_size=14,
            hoverlabel_font_family="Inter, sans-serif"
        )
        st.plotly_chart(fig_rush_mobi, use_container_width=True)

    # ── [D] Breakdown Table ──────────────────────────────────────────────────────
    st.info(f"⏱️ **Average Service Resolution Time (TAT) Across Selected Filter:** {h_tat} (HH:MM:SS) Per Ticket")
    st.write("")
    st.markdown("### 📋 Detailed Request Type Breakdown & Handling SLA")
    if not df_metrics.empty:
        breakdown = df_metrics.groupby("Request Type").agg(
            Count=("Request ID", "count"),
            Avg_Service=("Request Take (min)", "mean"),
            Avg_AHT=("AHT (min)", "mean")
        ).reset_index()
        breakdown["Percentage of Total"] = (
            breakdown["Count"] / total_tickets * 100
        ).round(1).astype(str) + "%"
        breakdown["Average Handling Time (AHT)"] = breakdown["Avg_AHT"].apply(format_minutes_to_hhmmss)
        breakdown["Avg Service Time"]            = breakdown["Avg_Service"].apply(format_minutes_to_hhmmss)

        display_breakdown = breakdown[
            ["Request Type", "Count", "Percentage of Total", "Average Handling Time (AHT)", "Avg Service Time"]
        ].sort_values("Count", ascending=False)
        st.dataframe(display_breakdown, hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Team Performance and KPIs
# ══════════════════════════════════════════════════════════════════════════════════
with tab2:

    st.markdown("### 👥 Team Performance and KPIs")
    st.write("")

    # ── Checkbox filters (same pattern as Tab 1) ──────────────────────────────
    t2_col1, t2_col2 = st.columns(2)
    with t2_col1:
        t2_escalated = st.checkbox(
            "🔥 Show Escalated Cases Only (Interactive Data Mapping)", value=False, key="t2_esc"
        )
    with t2_col2:
        t2_non_escalated = st.checkbox(
            "🟢 Show Non-Escalated Cases Only", value=False, key="t2_nonesc"
        )

    # Apply checkbox filters to a dedicated copy for Tab 2
    df_t2 = df.copy()
    if t2_escalated and not t2_non_escalated:
        df_t2 = df_t2[df_t2["Is Email"] == True]
    elif t2_non_escalated and not t2_escalated:
        df_t2 = df_t2[df_t2["Is Email"] == False]

    # ── Tab 2 KPI Cards ───────────────────────────────────────────────────────
    t2_total     = len(df_t2)
    t2_status    = df_t2["Status"].astype(str).str.strip()
    t2_closed_ok = df_t2[
        t2_status.str.contains("Closed", na=False, case=False) &
        ~t2_status.str.contains("issue", na=False, case=False)
    ].shape[0]
    t2_issue     = df_t2[
        t2_status.str.contains("Closed", na=False, case=False) &
        t2_status.str.contains("issue", na=False, case=False)
    ].shape[0]

    t2_avg_frt = df_t2["Response Take (min)"].mean() if not df_t2.empty else 0
    t2_avg_aht = df_t2["AHT (min)"].mean()           if not df_t2.empty else 0
    t2_avg_tat = df_t2["Request Take (min)"].mean()   if not df_t2.empty else 0

    t2_h_frt = format_minutes_to_hhmmss(t2_avg_frt)
    t2_h_aht = format_minutes_to_hhmmss(t2_avg_aht)
    t2_h_tat = format_minutes_to_hhmmss(t2_avg_tat)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.markdown(kpi_colored("Total Tickets",       f"{t2_total:,}",     "card-total"),     unsafe_allow_html=True)
    k2.markdown(kpi_colored("Closed Completed",    f"{t2_closed_ok:,}", "card-completed"), unsafe_allow_html=True)
    k3.markdown(kpi_colored("Closed with Issue",   f"{t2_issue:,}",     "card-issue"),     unsafe_allow_html=True)
    k4.markdown(kpi_colored("Avg Response (FRT)",  t2_h_frt,            "card-frt"),       unsafe_allow_html=True)
    k5.markdown(kpi_colored("Avg Handling (AHT)",  t2_h_aht,            "card-aht"),       unsafe_allow_html=True)
    k6.markdown(kpi_colored("Avg Service (TAT)",   t2_h_tat,            "card-tat"),       unsafe_allow_html=True)

    st.write("")
    st.divider()

    # ════════════════════════════════════════════════════════════════════════════
    #  Expert Performance Scorecard
    # ════════════════════════════════════════════════════════════════════════════
    st.markdown("### 📊 Expert Performance Scorecard")

    if df_t2.empty:
        st.warning("No data available for the selected filters.")
    else:
        # ── Exclude team leader from scorecard ───────────────────────────────
        EXCLUDED_AGENTS = ["mohammed shehta"]   # lowercase for case-insensitive match
        df_t2 = df_t2[
            ~df_t2["Assigned By"].astype(str).str.strip().str.lower().isin(EXCLUDED_AGENTS)
        ].copy()

        # ── Helper columns ───────────────────────────────────────────────────
        rt_lower = df_t2["Request Type"].astype(str).str.lower()

        df_t2["_is_jhah"]       = rt_lower.str.contains("jhah",            na=False)
        df_t2["_is_rep_or_fb"]  = rt_lower.str.contains("report|feedback", na=False)
        df_t2["_is_closed_ok"]  = (
            df_t2["Status"].astype(str).str.contains("Closed", case=False, na=False) &
            ~df_t2["Status"].astype(str).str.contains("issue",  case=False, na=False)
        )
        df_t2["_is_closed_all"] = df_t2["Status"].astype(str).str.contains("Closed", case=False, na=False)

        # ── Working Days: only days where agent handled > 15 tickets ─────────
        daily_counts = (
            df_t2.groupby(["Assigned By", "Date Only"])["Request ID"]
            .count()
            .reset_index(name="_daily_count")
        )
        active_days = (
            daily_counts[daily_counts["_daily_count"] > 15]
            .groupby("Assigned By")["Date Only"]
            .nunique()
            .rename("Working Days")
        )

        # ── Per-expert aggregation ───────────────────────────────────────────
        grp = df_t2.groupby("Assigned By")

        scorecard = pd.DataFrame(index=grp.groups.keys())
        scorecard.index.name = "Assigned By"

        scorecard["Working Days"]         = active_days                          # days with >15 tickets
        scorecard["Working Days"]         = scorecard["Working Days"].fillna(0).astype(int)
        scorecard["Tickets Count"]        = grp["Request ID"].count()
        scorecard["JHAH Requests"]        = grp["_is_jhah"].sum().astype(int)
        scorecard["Reporting & Feedback"] = grp["_is_rep_or_fb"].sum().astype(int)
        scorecard["Email Counts"]         = grp["Is Email"].sum().astype(int)

        # ── % Achievement from Target (vs team average baseline) ─────────────
        team_avg_volume = scorecard["Tickets Count"].mean()
        if team_avg_volume > 0:
            scorecard["% Achievement from Target"] = (
                scorecard["Tickets Count"] / team_avg_volume * 100
            ).round(1).astype(str) + "%"
        else:
            scorecard["% Achievement from Target"] = "0.0%"

        # ── Service Time (avg Request Take per expert → HH:MM:SS) ────────────
        avg_service_min = grp["Request Take (min)"].mean()
        scorecard["Service Time"] = avg_service_min.apply(fmt_m)

        # ── Service Quality (% closed tickets with no issue) ─────────────────
        closed_all_cnt  = grp["_is_closed_all"].sum()
        closed_ok_cnt   = grp["_is_closed_ok"].sum()
        service_quality = (closed_ok_cnt / closed_all_cnt.replace(0, np.nan) * 100).round(1)
        scorecard["Service Quality"] = service_quality.fillna(0).astype(str) + "%"

        scorecard = scorecard.reset_index().rename(columns={"Assigned By": "Expert"})

        # ── Team AVG baseline row (injected as first row) ─────────────────────
        def _avg_pct_str(series):
            nums = series.str.rstrip("%").astype(float)
            return f"{nums.mean():.1f}%"

        team_row = {
            "Expert":                    "🏆 Team AVG",
            "Working Days":              round(scorecard["Working Days"].mean(), 1),
            "Tickets Count":             round(scorecard["Tickets Count"].mean(), 1),
            "JHAH Requests":             round(scorecard["JHAH Requests"].mean(), 1),
            "Reporting & Feedback":      round(scorecard["Reporting & Feedback"].mean(), 1),
            "Email Counts":              round(scorecard["Email Counts"].mean(), 1),
            "% Achievement from Target": "100.0%",
            "Service Time":              fmt_m(avg_service_min.mean()),
            "Service Quality":           _avg_pct_str(scorecard["Service Quality"]),
        }

        scorecard_final = pd.concat(
            [pd.DataFrame([team_row]), scorecard],
            ignore_index=True
        )

        # ── Render table ─────────────────────────────────────────────────────
        st.dataframe(
            scorecard_final,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Expert":                    st.column_config.TextColumn("Expert"),
                "Working Days":              st.column_config.NumberColumn("Working Days",          format="%g"),
                "Tickets Count":             st.column_config.NumberColumn("Tickets Count",         format="%g"),
                "JHAH Requests":             st.column_config.NumberColumn("JHAH Requests",         format="%g"),
                "Reporting & Feedback":      st.column_config.NumberColumn("Reporting & Feedback",  format="%g"),
                "Email Counts":              st.column_config.NumberColumn("Email Counts",           format="%g"),
                "% Achievement from Target": st.column_config.TextColumn("% Achievement from Target"),
                "Service Time":              st.column_config.TextColumn("Service Time (HH:MM:SS)"),
                "Service Quality":           st.column_config.TextColumn("Service Quality"),
            }
        )

        # ── Manual Data Entry — Mohammed Shehta (Team Leader) ────────────────
        st.divider()
        st.markdown("### ✏️ Team Leader Manual Entry — Mohammed Shehta")
        st.caption("This section is not linked to the data source. Enter the team leader's figures manually.")

        ml_c1, ml_c2, ml_c3, ml_c4 = st.columns(4)
        with ml_c1:
            ml_working_days  = st.number_input("Working Days",         min_value=0, value=0, step=1,   key="ml_wd")
            ml_tickets       = st.number_input("Tickets Count",        min_value=0, value=0, step=1,   key="ml_tc")
        with ml_c2:
            ml_jhah          = st.number_input("JHAH Requests",        min_value=0, value=0, step=1,   key="ml_jhah")
            ml_rep_fb        = st.number_input("Reporting & Feedback", min_value=0, value=0, step=1,   key="ml_rfb")
        with ml_c3:
            ml_email         = st.number_input("Email Counts",         min_value=0, value=0, step=1,   key="ml_email")
            ml_achievement   = st.text_input("% Achievement from Target", value="0.0%",                key="ml_ach")
        with ml_c4:
            ml_service_time  = st.text_input("Service Time (HH:MM:SS)", value="00:00:00",              key="ml_st")
            ml_quality       = st.text_input("Service Quality (%)",      value="0.0%",                 key="ml_sq")

        if st.button("💾 Save & Preview Team Leader Row", use_container_width=True):
            leader_row = {
                "Expert":                    "👑 Mohammed Shehta (TL)",
                "Working Days":              ml_working_days,
                "Tickets Count":             ml_tickets,
                "JHAH Requests":             ml_jhah,
                "Reporting & Feedback":      ml_rep_fb,
                "Email Counts":              ml_email,
                "% Achievement from Target": ml_achievement,
                "Service Time":              ml_service_time,
                "Service Quality":           ml_quality,
            }
            st.success("✅ Team Leader row saved for this session.")
            st.dataframe(pd.DataFrame([leader_row]), hide_index=True, use_container_width=True)
