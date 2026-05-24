# dashboard.py — Approvals Team Dashboard (Multi-Page English Version)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

# ── PAGE CONFIGURATION ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Approvals Team Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Dark Theme CSS
st.markdown("""
<style>
    .stApp { background: #0d1117; color: #e6edf3; }
    .kpi-card {
        background: linear-gradient(135deg, #161b22 0%, #21262d 100%);
        border: 1px solid #30363d; border-radius: 14px;
        padding: 1.3rem 1.2rem; text-align: center; margin-bottom: 1rem;
    }
    .kpi-label { font-size: 0.8rem; letter-spacing: .05em;
        text-transform: uppercase; color: #8b949e; margin-bottom: .4rem; }
    .kpi-value { font-size: 1.8rem; font-weight: 800;
        background: linear-gradient(90deg, #58a6ff, #bc8cff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .kpi-sub { font-size: 0.8rem; color: #3fb950; margin-top: .2rem; }
    [data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
    h2 { color: #e6edf3; border-left: 3px solid #58a6ff; padding-left: .6rem; }
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
        return np.nan

# ── DATA LOADING ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner="Fetching live data from Google Sheets...")
def load_data_from_sheets():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open("AlDawaa Tickets Data")

        all_dfs = []
        for worksheet in spreadsheet.worksheets():
            data = worksheet.get_all_values()
            if len(data) > 1:
                headers = data[0]
                rows = data[1:]
                df_tab = pd.DataFrame(rows, columns=headers)
                all_dfs.append(df_tab)

        if not all_dfs:
            return pd.DataFrame()

        df = pd.concat(all_dfs, ignore_index=True)
        df.replace("", pd.NA, inplace=True)

        # Convert dates and times
        df["Request Date"] = pd.to_datetime(df["Request Date"], errors="coerce")
        df["Date Only"] = df["Request Date"].dt.date
        df["Request Take (min)"]  = df["Request Take"].apply(time_to_minutes)
        df["Response Take (min)"] = df["Response Take"].apply(time_to_minutes)
        
        if "Is Special Request(By Email)" in df.columns:
            df["Is Email"] = df["Is Special Request(By Email)"].astype(str).str.strip().str.upper() == "YES"
        else:
            df["Is Email"] = False

        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

def kpi(label, value, sub=""):
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>{sub_html}</div>'

# ── SIDEBAR & NAVIGATION ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ Approvals Team")
    st.success("📡 Live sync is Active")
    
    if st.button("🔄 Refresh Data Now", use_container_width=True):
        load_data_from_sheets.clear()
        
    # Page Navigation Links
    page = st.radio("📌 Navigation:", ["📊 Platform Overview", "👥 Team Performance", "🎯 KPIs & Manual Settings"])
    st.divider()

    df_raw = load_data_from_sheets()
    if df_raw.empty:
        st.warning("No data found. Check connections.")
        st.stop()

    st.subheader("🔍 Global Filters")
    min_d, max_d = df_raw["Date Only"].dropna().min(), df_raw["Date Only"].dropna().max()
    
    if pd.isna(min_d) or pd.isna(max_d):
        st.error("Date column format issue detected.")
        st.stop()
        
    date_range = st.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        d_from, d_to = date_range
    else:
        d_from, d_to = min_d, max_d

    agents = sorted(df_raw["Assigned By"].dropna().unique())
    sel_agents = st.multiselect("Select Agent(s)", agents, default=agents)

# ── APPLY FILTERS ────────────────────────────────────────────────────────────
df = df_raw.copy()
df = df[df["Date Only"].between(d_from, d_to)]
if sel_agents: df = df[df["Assigned By"].isin(sel_agents)]

# ──────────────────────────────────────────────────────────────────────────────
# ── PAGE 1: PLATFORM OVERVIEW ──
# ──────────────────────────────────────────────────────────────────────────────
if page == "📊 Platform Overview":
    st.markdown("## 📊 Platform Statistics Overview")
    st.caption(f"Showing requests from {d_from} to {d_to}")
    
    # Calculations (Adjust keywords if your sheet data uses Arabic statuses)
    total_req = len(df)
    closed_completed = df["Status"].str.contains("Completed|مكتمل|Closed", na=False, case=False).sum()
    closed_issue = df["Status"].str.contains("Issue|مشكلة", na=False, case=False).sum()
    sent_insurance = df["Status"].str.contains("Insurance|تأمين", na=False, case=False).sum()
    reopen_cases = df["Status"].str.contains("Reopen|معاد", na=False, case=False).sum()
    
    avg_resp = df["Response Take (min)"].mean()
    aht = df["Request Take (min)"].mean()  # Average Handling Time / Service Time
    reopen_rate = (reopen_cases / total_req * 100) if total_req > 0 else 0

    # Row 1: Main Status Cards
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi("Total Requests", f"{total_req:,}"), unsafe_allow_html=True)
    c2.markdown(kpi("Completed / Closed", f"{closed_completed:,}"), unsafe_allow_html=True)
    c3.markdown(kpi("Closed with Issue", f"{closed_issue:,}"), unsafe_allow_html=True)
    c4.markdown(kpi("Sent to Insurance", f"{sent_insurance:,}"), unsafe_allow_html=True)

    # Row 2: Service Metrics Cards
    c5, c6, c7, c8 = st.columns(4)
    c5.markdown(kpi("Avg Response Time", f"{avg_resp:.1f} min" if pd.notna(avg_resp) else "0 min"), unsafe_allow_html=True)
    c6.markdown(kpi("Avg Handling Time (AHT)", f"{aht:.1f} min" if pd.notna(aht) else "0 min"), unsafe_allow_html=True)
    c7.markdown(kpi("Reopen Rate", f"{reopen_rate:.1f}%"), unsafe_allow_html=True)
    c8.markdown(kpi("Email Requests", f"{df['Is Email'].sum()}"), unsafe_allow_html=True)

    st.divider()

    # Charts: Request Types Pie and Distribution Curve
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🥧 Request Types Distribution")
        if not df.empty and "Request Type" in df.columns:
            type_counts = df["Request Type"].value_counts().reset_index()
            type_counts.columns = ["Request Type", "Count"]
            fig_pie = px.pie(type_counts, values="Count", names="Request Type", hole=0.4,
                             color_discrete_sequence=px.colors.sequential.Tealgrn)
            fig_pie.update_layout(**THEME)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No request type data available.")

    with col2:
        st.markdown("### 📈 Handling Time Distribution Curve")
        if not df.empty and pd.notna(aht):
            fig_dist = px.histogram(df, x="Request Take (min)", marginal="box", 
                                    color_discrete_sequence=["#58a6ff"])
            fig_dist.update_layout(**THEME, xaxis_title="Minutes", yaxis_title="Count")
            st.plotly_chart(fig_dist, use_container_width=True)
        else:
            st.info("Not enough data to calculate distribution.")

# ──────────────────────────────────────────────────────────────────────────────
# ── PAGE 2: TEAM PERFORMANCE ──
# ──────────────────────────────────────────────────────────────────────────────
elif page == "👥 Team Performance":
    st.markdown("## 👥 Team Performance Metrics")
    
    min_cases = st.sidebar.number_input("Minimum cases to count as Attendance Day", min_value=1, value=20)
    
    if not df.empty:
        # 1. Calculate Attendance Days per Agent
        daily_per_agent = df.groupby(["Assigned By", "Date Only"]).size().reset_index(name="Daily Cases")
        attendance = daily_per_agent[daily_per_agent["Daily Cases"] >= min_cases].groupby("Assigned By").size().reset_index(name="Attendance Days")
        
        # 2. Aggregate Agent Metrics
        agent_stats = df.groupby("Assigned By").agg(
            Total_Cases=("Request Date", "count"),
            Avg_Response_Time=("Response Take (min)", "mean"),
            Avg_Handling_Time=("Request Take (min)", "mean"),
            Email_Cases=("Is Email", "sum")
        ).reset_index()
        
        # Merge Data
        team_data = pd.merge(agent_stats, attendance, on="Assigned By", how="left").fillna(0)
        team_data["Attendance Days"] = team_data["Attendance Days"].astype(int)
        
        # Format and display team metrics table
        st.dataframe(
            team_data.style.format({
                "Avg_Response_Time": "{:.1f} min",
                "Avg_Handling_Time": "{:.1f} min"
            }),
            use_container_width=True, height=400, hide_index=True
        )
        
        st.markdown("### 📊 Agent Workload Volume")
        fig_wl = px.bar(team_data.sort_values("Total_Cases"), x="Total_Cases", y="Assigned By", 
                        orientation="h", color="Total_Cases", color_continuous_scale="Blues",
                        labels={"Total_Cases": "Total Handled Cases", "Assigned By": "Agent Name"})
        fig_wl.update_layout(**THEME, coloraxis_showscale=False)
        st.plotly_chart(fig_wl, use_container_width=True)
    else:
        st.warning("No data available for the selected filters.")

# ──────────────────────────────────────────────────────────────────────────────
# ── PAGE 3: KPIS & MANUAL ENTRY ──
# ──────────────────────────────────────────────────────────────────────────────
elif page == "🎯 KPIs & Manual Settings":
    st.markdown("## 🎯 KPI Management & External Inputs")
    st.info("💡 Use this page to track your operational targets and manually update external metrics.")
    
    # Editable Data Grid for KPI Targets
    st.markdown("### ✍️ Manual Target Settings")
    
    default_targets = pd.DataFrame({
        "Metric / KPI Indicator": ["Average Handling Time (AHT)", "Response Time (SLA)", "Quality Score %", "Reopen Rate Target"],
        "Target Goal": ["15 Min", "5 Min", "95%", "< 5%"],
        "Current Actual": ["-", "-", "-", "-"],
        "Comments / Notes": ["", "", "", ""]
    })
    
    edited_df = st.data_editor(default_targets, num_rows="dynamic", use_container_width=True)
    
    st.divider()
    
    # File Uploader section for external sheets (e.g., QA sheets, Audits)
    st.markdown("### 📎 Upload External Team Sheets (Excel / CSV)")
    uploaded_file = st.file_uploader("Upload external QA or performance files", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                ext_df = pd.read_csv(uploaded_file)
            else:
                ext_df = pd.read_excel(uploaded_file)
            st.success("File uploaded successfully! Data Preview:")
            st.dataframe(ext_df, use_container_width=True, height=250)
        except Exception as e:
            st.error(f"An error occurred while parsing the file: {e}")
