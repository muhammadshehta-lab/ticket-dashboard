# dashboard.py — In-Store Requests Dashboard (Multi-Page)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

# ── إعدادات الصفحة ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Approvals Team Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

# ── جلب البيانات ─────────────────────────────────────────────────────────────
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

        # تحويل التواريخ والأوقات
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

# ── القائمة الجانبية (Sidebar & Navigation) ──────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ Approvals Team")
    
    # نظام التنقل بين الصفحات
    page = st.radio("📌 انتقل إلى:", ["📊 ملخص المنصة", "👥 أداء الفريق", "🎯 مؤشرات الأداء (KPIs)"])
    st.divider()

    df_raw = load_data_from_sheets()
    if df_raw.empty:
        st.warning("No data found. Check connections.")
        st.stop()

    st.subheader("🔍 الفلاتر العامة")
    min_d, max_d = df_raw["Date Only"].dropna().min(), df_raw["Date Only"].dropna().max()
    date_range = st.date_input("نطاق التاريخ", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        d_from, d_to = date_range
    else:
        d_from, d_to = min_d, max_d

    agents = sorted(df_raw["Assigned By"].dropna().unique())
    sel_agents = st.multiselect("اختر الموظف (Agent)", agents, default=agents)

# ── تطبيق الفلاتر ─────────────────────────────────────────────────────────────
df = df_raw.copy()
df = df[df["Date Only"].between(d_from, d_to)]
if sel_agents: df = df[df["Assigned By"].isin(sel_agents)]

# ──────────────────────────────────────────────────────────────────────────────
# ── الصفحة الأولى: ملخص المنصة (Platform Overview) ──
# ──────────────────────────────────────────────────────────────────────────────
if page == "📊 ملخص المنصة":
    st.markdown("## 📊 تقرير المنصة (Platform Statistics)")
    
    # حساب الإحصائيات (ملاحظة: عدل نصوص الـ Status حسب ما هو مكتوب عندك في الشيت)
    total_req = len(df)
    closed_completed = df["Status"].str.contains("Completed|مكتمل", na=False, case=False).sum()
    closed_issue = df["Status"].str.contains("Issue|مشكلة", na=False, case=False).sum()
    sent_insurance = df["Status"].str.contains("Insurance|تأمين", na=False, case=False).sum()
    reopen_cases = df["Status"].str.contains("Reopen|معاد", na=False, case=False).sum()
    
    avg_resp = df["Response Take (min)"].mean()
    aht = df["Request Take (min)"].mean() # Average Handling Time / Service Time
    reopen_rate = (reopen_cases / total_req * 100) if total_req > 0 else 0

    # عرض كروت الـ KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi("إجمالي الطلبات", f"{total_req:,}"), unsafe_allow_html=True)
    c2.markdown(kpi("مكتمل بدون مشاكل", f"{closed_completed:,}"), unsafe_allow_html=True)
    c3.markdown(kpi("مغلق بمشكلة", f"{closed_issue:,}"), unsafe_allow_html=True)
    c4.markdown(kpi("مرسل للتأمين", f"{sent_insurance:,}"), unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    c5.markdown(kpi("متوسط سرعة الرد", f"{avg_resp:.1f} min"), unsafe_allow_html=True)
    c6.markdown(kpi("متوسط وقت الخدمة (AHT)", f"{aht:.1f} min"), unsafe_allow_html=True)
    c7.markdown(kpi("نسبة إعادة الفتح (Reopen)", f"{reopen_rate:.1f}%"), unsafe_allow_html=True)
    c8.markdown(kpi("طلبات الإيميل", f"{df['Is Email'].sum()}"), unsafe_allow_html=True)

    st.divider()

    # الرسوم البيانية: أنواع الطلبات ومنحنى التوزيع
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🥧 توزيع أنواع الطلبات")
        type_counts = df["Request Type"].value_counts().reset_index()
        type_counts.columns = ["Request Type", "Count"]
        fig_pie = px.pie(type_counts, values="Count", names="Request Type", hole=0.4,
                         color_discrete_sequence=px.colors.sequential.Tealgrn)
        fig_pie.update_layout(**THEME)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.markdown("### 📈 منحنى التوزيع: وقت الخدمة والاستجابة")
        # Distribution curve using Marginal Box plot
        fig_dist = px.histogram(df, x="Request Take (min)", marginal="box", 
                                title="Distribution of Handling Time (AHT)",
                                color_discrete_sequence=["#58a6ff"])
        fig_dist.update_layout(**THEME, xaxis_title="Minutes", yaxis_title="Count")
        st.plotly_chart(fig_dist, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# ── الصفحة الثانية: أداء الفريق (Team Performance) ──
# ──────────────────────────────────────────────────────────────────────────────
elif page == "👥 أداء الفريق":
    st.markdown("## 👥 تفاصيل أداء الفريق (Team Metrics)")
    
    min_cases = st.sidebar.number_input("الحد الأدنى لاحتساب يوم دوام", min_value=1, value=20)
    
    # تجميع بيانات كل موظف
    # 1. أيام الدوام
    daily_per_agent = df.groupby(["Assigned By", "Date Only"]).size().reset_index(name="Daily Cases")
    attendance = daily_per_agent[daily_per_agent["Daily Cases"] >= min_cases].groupby("Assigned By").size().reset_index(name="أيام الدوام")
    
    # 2. إحصائيات الموظف (إجمالي، متوسط الأوقات، الحالات، الإيميلات)
    agent_stats = df.groupby("Assigned By").agg(
        إجمالي_الحالات=("Request Date", "count"),
        متوسط_وقت_الاستجابة=("Response Take (min)", "mean"),
        متوسط_وقت_الخدمة=("Request Take (min)", "mean"),
        حالات_الايميل=("Is Email", "sum")
    ).reset_index()
    
    # دمج البيانات
    team_data = pd.merge(agent_stats, attendance, on="Assigned By", how="left").fillna(0)
    team_data["أيام الدوام"] = team_data["أيام الدوام"].astype(int)
    
    st.dataframe(
        team_data.style.format({
            "متوسط_وقت_الاستجابة": "{:.1f} دقيقة",
            "متوسط_وقت_الخدمة": "{:.1f} دقيقة"
        }),
        use_container_width=True, height=400, hide_index=True
    )
    
    st.markdown("### 📊 حجم العمل لكل موظف")
    fig_wl = px.bar(team_data.sort_values("إجمالي_الحالات"), x="إجمالي_الحالات", y="Assigned By", 
                    orientation="h", color="إجمالي_الحالات", color_continuous_scale="Blues")
    fig_wl.update_layout(**THEME, coloraxis_showscale=False)
    st.plotly_chart(fig_wl, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# ── الصفحة الثالثة: مؤشرات الأداء والإدخال اليدوي (KPIs & Manual Entry) ──
# ──────────────────────────────────────────────────────────────────────────────
elif page == "🎯 مؤشرات الأداء (KPIs)":
    st.markdown("## 🎯 إعدادات ومتابعة الـ KPIs")
    st.info("💡 في هذه الصفحة يمكنك إدخال التارجت الشهري يدوياً أو مراجعة شيتات خارجية.")
    
    # جزء للإدخال اليدوي باستخدام st.data_editor
    st.markdown("### ✍️ إدخال التارجت يدوياً (Manual Target Entry)")
    
    # بيانات مبدئية قابلة للتعديل
    default_targets = pd.DataFrame({
        "الهدف (KPI)": ["متوسط وقت الخدمة (AHT)", "سرعة الاستجابة (SLA)", "نسبة الجودة", "نسبة إعادة الفتح"],
        "التارجت المطلوب": ["15 Min", "5 Min", "95%", "< 5%"],
        "النتيجة الفعلية": ["-", "-", "-", "-"],
        "ملاحظات": ["", "", "", ""]
    })
    
    # الأداة دي بتسمحلك تعدل البيانات كأنها ملف إكسيل جوه الداش بورد
    edited_df = st.data_editor(default_targets, num_rows="dynamic", use_container_width=True)
    
    st.divider()
    
    # جزء لرفع شيتات خارجية (مثلاً شيت تقييم الجودة من الـ QA)
    st.markdown("### 📎 رفع شيتات خارجية (External Data Upload)")
    uploaded_file = st.file_uploader("ارفع ملف Excel أو CSV لتقييمات الفريق", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                ext_df = pd.read_csv(uploaded_file)
            else:
                ext_df = pd.read_excel(uploaded_file)
            st.success("تم رفع الملف بنجاح! معاينة البيانات:")
            st.dataframe(ext_df, use_container_width=True, height=250)
        except Exception as e:
            st.error(f"حدث خطأ أثناء قراءة الملف: {e}")
