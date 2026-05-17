"""
dashboard.py — In-Store Requests Dashboard (English)
"""

import io
import glob
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="In-Store Requests Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background: #0d1117; color: #e6edf3; }
    .kpi-card {
        background: linear-gradient(135deg, #161b22 0%, #21262d 100%);
        border: 1px solid #30363d; border-radius: 14px;
        padding: 1.3rem 1.2rem; text-align: center;
    }
    .kpi-label { font-size: 0.72rem; letter-spacing: .13em;
        text-transform: uppercase; color: #8b949e; margin-bottom: .4rem; }
    .kpi-value { font-size: 2rem; font-weight: 800;
        background: linear-gradient(90deg, #58a6ff, #bc8cff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .kpi-sub { font-size: 0.78rem; color: #3fb950; margin-top: .2rem; }
    [data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
    h2 { color: #e6edf3; border-left: 3px solid #58a6ff; padding-left: .6rem; }
    .attendance-table { font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9",
    margin=dict(l=10, r=10, t=40, b=10),
)

def time_to_minutes(s):
    try:
        parts = str(s).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except:
        return None

@st.cache_data(show_spinner="Loading data...")
def load_data(source):
    if isinstance(source, bytes):
        df = pd.read_excel(io.BytesIO(source), engine="openpyxl")
    else:
        df = pd.read_excel(source, engine="openpyxl")
    df["Request Date"] = pd.to_datetime(df["Request Date"], errors="coerce")
    df["Date Only"] = df["Request Date"].dt.date
    df["Hour"] = df["Request Date"].dt.hour
    df["Request Take (min)"]      = df["Request Take"].apply(time_to_minutes)
    df["Response Take (min)"]     = df["Response Take"].apply(time_to_minutes)
    df["First Action Take (min)"] = df["First Action Take"].apply(time_to_minutes)
    df["Is Email"] = df["Is Special Request(By Email)"].str.strip().str.upper() == "YES"
    return df

def calc_attendance(df, min_cases=20):
    """
    Count attendance days per agent.
    A day counts as an attendance day if the agent handled more than min_cases that day.
    """
    daily_per_agent = (
        df.groupby(["Assigned By", "Date Only"])
        .size()
        .reset_index(name="Daily Cases")
    )
    attendance = (
        daily_per_agent[daily_per_agent["Daily Cases"] >= min_cases]
        .groupby("Assigned By")
        .size()
        .reset_index(name="Attendance Days")
        .sort_values("Attendance Days", ascending=False)
    )
    # Also add total cases per agent
    total_cases = df.groupby("Assigned By").size().reset_index(name="Total Cases")
    attendance = attendance.merge(total_cases, on="Assigned By")
    attendance["Avg Cases/Day"] = (attendance["Total Cases"] / attendance["Attendance Days"]).round(1)
    return attendance

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💊 Dashboard")
    st.markdown("**In-Store Requests**")
    st.divider()

    uploaded = st.file_uploader("Upload Excel File", type=["xlsx"])
    if uploaded:
        df_raw = load_data(uploaded.read())
        st.success(f"✅ {uploaded.name}")
    else:
        files = glob.glob(str(Path(__file__).parent / "downloads" / "*.xlsx"))
        if files:
            latest = max(files, key=Path.stat)
            df_raw = load_data(latest)
            st.info(f"📂 {Path(latest).name}")
        else:
            st.warning("Please upload an Excel file.")
            st.stop()

    st.divider()
    st.subheader("🔍 Filters")

    min_d = df_raw["Date Only"].dropna().min()
    max_d = df_raw["Date Only"].dropna().max()
    date_range = st.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        d_from, d_to = date_range
    else:
        d_from, d_to = min_d, max_d

    agents = sorted(df_raw["Assigned By"].dropna().unique())
    sel_agents = st.multiselect("Agent", agents, default=agents)

    req_types = sorted(df_raw["Request Type"].dropna().unique())
    sel_types = st.multiselect("Request Type", req_types, default=req_types)

    statuses = sorted(df_raw["Status"].dropna().unique())
    sel_status = st.multiselect("Status", statuses, default=statuses)

    st.divider()
    # Attendance threshold setting
    st.subheader("⚙️ Attendance Setting")
    min_cases = st.number_input(
        "Min cases to count as attendance day",
        min_value=1, max_value=100, value=20, step=1
    )

# ── Filter ────────────────────────────────────────────────────────────────────
df = df_raw.copy()
df = df[df["Date Only"].between(d_from, d_to)]
if sel_agents:  df = df[df["Assigned By"].isin(sel_agents)]
if sel_types:   df = df[df["Request Type"].isin(sel_types)]
if sel_status:  df = df[df["Status"].isin(sel_status)]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 💊 In-Store Requests Dashboard")
st.caption(f"Showing **{len(df):,}** requests out of {len(df_raw):,} — {d_from} to {d_to}")

# ── KPIs ──────────────────────────────────────────────────────────────────────
def kpi(label, value, sub=""):
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>{sub_html}</div>'

total      = len(df)
closed     = df["Status"].str.startswith("Closed").sum()
open_t     = total - closed
email_t    = int(df["Is Email"].sum())
avg_resp   = df["Response Take (min)"].mean()

c1,c2,c3,c4,c5 = st.columns(5)
c1.markdown(kpi("Total Requests",   f"{total:,}"),                           unsafe_allow_html=True)
c2.markdown(kpi("Closed",           f"{closed:,}", f"{closed/total*100:.1f}%"), unsafe_allow_html=True)
c3.markdown(kpi("Open / Pending",   f"{open_t:,}"),                          unsafe_allow_html=True)
c4.markdown(kpi("Email Requests",   f"{email_t:,}"),                         unsafe_allow_html=True)
c5.markdown(kpi("Avg Response Time",f"{avg_resp:.0f} min" if pd.notna(avg_resp) else "N/A"), unsafe_allow_html=True)

st.write("")

# ── Attendance Section ────────────────────────────────────────────────────────
st.markdown(f"## 📅 Agent Attendance Days *(days with more than {min_cases} cases)*")

attendance = calc_attendance(df, min_cases)

if not attendance.empty:
    col_t, col_c = st.columns([2, 3], gap="medium")

    with col_t:
        # Table
        st.dataframe(
            attendance.rename(columns={
                "Assigned By":    "Agent",
                "Attendance Days": "Attendance Days",
                "Total Cases":    "Total Cases",
                "Avg Cases/Day":  "Avg Cases/Day"
            }),
            use_container_width=True,
            height=320,
            hide_index=True,
        )

    with col_c:
        # Bar chart
        fig_att = px.bar(
            attendance,
            x="Assigned By", y="Attendance Days",
            color="Attendance Days",
            color_continuous_scale=["#1f4068", "#58a6ff"],
            text="Attendance Days",
            labels={"Assigned By": "Agent", "Attendance Days": "Days"},
            title=f"Attendance Days per Agent (>{min_cases} cases/day)",
        )
        fig_att.update_traces(textposition="outside")
        fig_att.update_layout(**THEME, coloraxis_showscale=False)
        st.plotly_chart(fig_att, use_container_width=True)
else:
    st.info("No attendance data available.")

st.divider()

# ── Row 1: Daily Volume + Workload ────────────────────────────────────────────
col1, col2 = st.columns([3, 2], gap="medium")

with col1:
    st.markdown("## 📈 Daily Request Volume")
    daily = df.groupby("Date Only").size().reset_index(name="Requests")
    fig = go.Figure()
    fig.add_bar(x=daily["Date Only"], y=daily["Requests"], marker_color="#58a6ff", name="Requests")
    fig.add_scatter(x=daily["Date Only"], y=daily["Requests"],
                    mode="lines", line=dict(color="#bc8cff", width=2), name="Trend")
    fig.update_layout(**THEME, xaxis_title="Date", yaxis_title="Number of Requests")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("## 👥 Agent Workload")
    wl = df.groupby("Assigned By").size().reset_index(name="Requests").sort_values("Requests", ascending=True)
    fig2 = px.bar(wl, x="Requests", y="Assigned By", orientation="h",
                  color="Requests", color_continuous_scale=["#1f4068","#58a6ff"])
    fig2.update_layout(**THEME, coloraxis_showscale=False)
    st.plotly_chart(fig2, use_container_width=True)

# ── Row 2: Request Types + Status ─────────────────────────────────────────────
col3, col4 = st.columns(2, gap="medium")

with col3:
    st.markdown("## 📋 Request Types")
    rt = df["Request Type"].value_counts().reset_index()
    rt.columns = ["Request Type", "Count"]
    fig3 = px.bar(rt, x="Count", y="Request Type", orientation="h",
                  color="Count", color_continuous_scale=["#1a3a2a","#3fb950"])
    fig3.update_layout(**THEME, coloraxis_showscale=False)
    st.plotly_chart(fig3, use_container_width=True)

with col4:
    st.markdown("## 🔄 Request Status")
    sc = df["Status"].value_counts().reset_index()
    sc.columns = ["Status", "Count"]
    fig4 = px.pie(sc, names="Status", values="Count", hole=0.45,
                  color_discrete_sequence=["#3fb950","#f85149","#d29922","#58a6ff","#bc8cff"])
    fig4.update_layout(**THEME)
    st.plotly_chart(fig4, use_container_width=True)

# ── Row 3: Response Time + First Action ───────────────────────────────────────
col5, col6 = st.columns(2, gap="medium")

with col5:
    st.markdown("## ⏱ Avg Response Time per Agent")
    ar = (df.groupby("Assigned By")["Response Take (min)"].mean()
            .reset_index().rename(columns={"Response Take (min)":"Avg Minutes"})
            .sort_values("Avg Minutes", ascending=False))
    fig5 = px.bar(ar, x="Assigned By", y="Avg Minutes",
                  color="Avg Minutes", color_continuous_scale=["#1a2a3a","#f0883e"])
    fig5.update_layout(**THEME, coloraxis_showscale=False,
                       xaxis_title="Agent", yaxis_title="Avg Minutes")
    st.plotly_chart(fig5, use_container_width=True)

with col6:
    st.markdown("## ⚡ Avg First Action Time per Agent")
    af = (df.groupby("Assigned By")["First Action Take (min)"].mean()
            .reset_index().rename(columns={"First Action Take (min)":"Avg Minutes"})
            .sort_values("Avg Minutes", ascending=False))
    fig6 = px.bar(af, x="Assigned By", y="Avg Minutes",
                  color="Avg Minutes", color_continuous_scale=["#1a1a2e","#bc8cff"])
    fig6.update_layout(**THEME, coloraxis_showscale=False,
                       xaxis_title="Agent", yaxis_title="Avg Minutes")
    st.plotly_chart(fig6, use_container_width=True)

# ── Row 4: Hourly + Email ─────────────────────────────────────────────────────
col7, col8 = st.columns([2,1], gap="medium")

with col7:
    st.markdown("## 🕐 Requests by Hour of Day")
    hourly = df.groupby("Hour").size().reset_index(name="Requests")
    fig7 = px.area(hourly, x="Hour", y="Requests", color_discrete_sequence=["#58a6ff"])
    fig7.update_layout(**THEME, xaxis_title="Hour", yaxis_title="Number of Requests",
                       xaxis=dict(tickmode="linear", dtick=2))
    fig7.update_traces(fill="tozeroy", line_color="#58a6ff")
    st.plotly_chart(fig7, use_container_width=True)

with col8:
    st.markdown("## 📧 Email vs Regular")
    email_df = pd.DataFrame({"Type":["Email","Regular"],
                              "Count":[df["Is Email"].sum(), (~df["Is Email"]).sum()]})
    fig8 = px.pie(email_df, names="Type", values="Count", hole=0.5,
                  color_discrete_sequence=["#f0883e","#58a6ff"])
    fig8.update_layout(**THEME)
    st.plotly_chart(fig8, use_container_width=True)


st.divider()

# ── IQR Analysis ──────────────────────────────────────────────────────────────
st.markdown("## 📊 Service Time & Response Time — IQR Analysis")
st.caption("IQR removes outliers and shows the true performance range (Q1 to Q3)")

def iqr_stats(series, label):
    s = series.dropna()
    q1  = s.quantile(0.25)
    q3  = s.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    filtered = s[(s >= lower) & (s <= upper)]
    return {
        "Metric":           label,
        "Min (min)":        round(s.min(), 1),
        "Q1 — 25% (min)":  round(q1, 1),
        "Median (min)":     round(s.median(), 1),
        "Q3 — 75% (min)":  round(q3, 1),
        "Max (min)":        round(s.max(), 1),
        "IQR (min)":        round(iqr, 1),
        "Outliers Removed": int(len(s) - len(filtered)),
        "Avg After IQR":    round(filtered.mean(), 1),
    }

iqr_data = []
if "Request Take (min)" in df.columns:
    iqr_data.append(iqr_stats(df["Request Take (min)"], "Service Time (Request Take)"))
if "Response Take (min)" in df.columns:
    iqr_data.append(iqr_stats(df["Response Take (min)"], "Response Time"))
if "First Action Take (min)" in df.columns:
    iqr_data.append(iqr_stats(df["First Action Take (min)"], "First Action Time"))

if iqr_data:
    iqr_df = pd.DataFrame(iqr_data).set_index("Metric")
    st.dataframe(iqr_df, use_container_width=True)

    col_iqr1, col_iqr2 = st.columns(2, gap="medium")

    with col_iqr1:
        st.markdown("### Service Time — Box Plot per Agent")
        if "Request Take (min)" in df.columns:
            fig_box1 = px.box(
                df.dropna(subset=["Request Take (min)"]),
                x="Assigned By", y="Request Take (min)",
                color="Assigned By", points=False,
                labels={"Request Take (min)": "Minutes", "Assigned By": "Agent"},
                title="Service Time IQR",
            )
            fig_box1.update_layout(**THEME, showlegend=False)
            st.plotly_chart(fig_box1, use_container_width=True)

    with col_iqr2:
        st.markdown("### Response Time — Box Plot per Agent")
        if "Response Take (min)" in df.columns:
            fig_box2 = px.box(
                df.dropna(subset=["Response Take (min)"]),
                x="Assigned By", y="Response Take (min)",
                color="Assigned By", points=False,
                labels={"Response Take (min)": "Minutes", "Assigned By": "Agent"},
                title="Response Time IQR",
            )
            fig_box2.update_layout(**THEME, showlegend=False)
            st.plotly_chart(fig_box2, use_container_width=True)

    st.markdown("### Avg Time After Removing Outliers — per Agent")
    iqr_agent_rows = []
    for agent in df["Assigned By"].dropna().unique():
        agent_df = df[df["Assigned By"] == agent]
        for col, label in [("Request Take (min)", "Service Time"), ("Response Take (min)", "Response Time")]:
            if col in agent_df.columns:
                s = agent_df[col].dropna()
                if len(s) > 4:
                    q1, q3 = s.quantile(0.25), s.quantile(0.75)
                    iqr_val = q3 - q1
                    filtered = s[(s >= q1 - 1.5*iqr_val) & (s <= q3 + 1.5*iqr_val)]
                    iqr_agent_rows.append({"Agent": agent, "Metric": label, "Avg (min)": round(filtered.mean(), 1)})

    if iqr_agent_rows:
        iqr_agent_df = pd.DataFrame(iqr_agent_rows)
        fig_iqr = px.bar(
            iqr_agent_df, x="Agent", y="Avg (min)", color="Metric", barmode="group",
            color_discrete_map={"Service Time": "#58a6ff", "Response Time": "#f0883e"},
            title="Service Time vs Response Time — IQR Filtered Average per Agent",
        )
        fig_iqr.update_layout(**THEME)
        st.plotly_chart(fig_iqr, use_container_width=True)


# ── Raw Data ──────────────────────────────────────────────────────────────────
st.divider()
st.markdown("## 🗃 Raw Data")

search = st.text_input("🔍 Search in any column")
show_df = df.copy()
if search:
    mask = show_df.astype(str).apply(lambda c: c.str.contains(search, case=False, na=False)).any(axis=1)
    show_df = show_df[mask]

display_cols = ["Request ID","Request Date","Request Type","Status",
                "Assigned By","Store Code","Insurance Company",
                "Request Take","Response Take","First Action Take",
                "Is Special Request(By Email)"]
st.dataframe(show_df[[c for c in display_cols if c in show_df.columns]],
             use_container_width=True, height=380)

csv = show_df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download Filtered Data as CSV", data=csv,
                   file_name="filtered_requests.csv", mime="text/csv",
                   use_container_width=True)

st.caption("al-Dawaa • In-Store Requests Dashboard • Powered by Streamlit & Plotly")
