import pandas as pd, numpy as np, plotly.express as px, plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st, gspread, json, urllib.parse
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="In-Store Performance Hub", page_icon="💊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.stApp { background: #0d1117; color: #e6edf3; }
.kpi-container { border-radius: 14px; padding: 1.2rem 0.8rem; text-align: center; min-height: 110px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 1rem; }
.kpi-label { font-size: 0.72rem; letter-spacing: .1em; text-transform: uppercase; color: #8b949e; margin-bottom: .4rem; font-weight: 600; }
.kpi-value { font-size: 1.5rem; font-weight: 800; }
.card-total { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }
.card-completed { background: #12221b; border: 1px solid #3fb950; color: #3fb950; }
.card-issue { background: #261f12; border: 1px solid #d29922; color: #d29922; }
.card-frt { background: #2b1c11; border: 1px solid #f0883e; color: #f0883e; }
.card-aht { background: #221230; border: 1px solid #bc8cff; color: #bc8cff; }
.card-tat { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }
.stTabs [data-baseweb="tab-list"] { gap: 10px; }
.stTabs [data-baseweb="tab"] { background-color: #161b22; border-radius: 10px 10px 0 0; padding: 10px 20px; color: #8b949e; }
.stTabs [aria-selected="true"] { background-color: #1e3a8a !important; color: white !important; }
</style>""", unsafe_allow_html=True)

THEME = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#c9d1d9", margin=dict(l=10, r=10, t=50, b=10))
DAYS_ARABIC = {"Saturday":"السبت", "Sunday":"الأحد", "Monday":"الإثنين", "Tuesday":"الثلاثاء", "Wednesday":"الأربعاء", "Thursday":"الخميس", "Friday":"الجمعة"}
CMAP = {"Under 15 Mins":"#2ea44f", "15-30 Mins":"#2188ff", "30-45 Mins":"#bc8cff", "45-60 Mins":"#f9c513", "Over 1 Hour":"#ea4a5a"}

def kpi(l, v, c): return f'<div class="kpi-container {c}"><div class="kpi-label">{l}</div><div class="kpi-value">{v}</div></div>'
def t2m(s):
    try: return int(str(s).strip().split(":")[0]) * 60 + int(str(s).strip().split(":")[1])
    except: return 0
def fmt_m(m):
    if pd.isna(m) or m<=0: return "00:00:00"
    ts = int(round(m*60))
    return f"{ts//3600:02d}:{(ts%3600)//60:02d}:{ts%60:02d}"
def get_tier(m): return "Under 15 Mins" if m<=15 else "15-30 Mins" if m<=30 else "30-45 Mins" if m<=45 else "45-60 Mins" if m<=60 else "Over 1 Hour"

@st.cache_data(ttl=600, show_spinner="Fetching data...")
def load_data():
    try:
        sc = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        cr = Credentials.from_service_account_info(json.loads(st.secrets["gspread"]["credentials"]), scopes=sc)
        cl = gspread.authorize(cr)
        dfs = []
        for ws in cl.open("AlDawaa Tickets Data").worksheets():
            d = ws.get_all_values()
            if len(d) > 1:
                tdf = pd.DataFrame(d[1:], columns=[str(c).strip() for c in d[0]])
                mp, tgts = {}, set()
                for c in tdf.columns:
                    cl = c.lower()
                    t = "Request ID" if "id" in cl and "req" in cl else "Request Date" if "date" in cl else "Request Type" if "type" in cl else "Status" if "status" in cl else "Assigned By" if "agent" in cl or "assigned" in cl else "Response Take" if "response" in cl and "take" in cl else "First Action Take" if "action" in cl and "take" in cl else "Request Take" if "request" in cl and "take" in cl else "Is Email" if "email" in cl or "special" in cl else None
                    if t and t not in tgts: mp[c] = t; tgts.add(t)
                dfs.append(tdf.rename(columns=mp))
        if not dfs: return pd.DataFrame()
        df = pd.concat(dfs, ignore_index=True).replace("", np.nan)
        reqs = ["Request ID", "Request Date", "Request Type", "Status", "Request Take", "Response Take", "First Action Take", "Assigned By", "Is Email"]
        for c in reqs:
            if c not in df.columns
