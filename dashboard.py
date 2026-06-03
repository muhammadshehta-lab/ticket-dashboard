import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json, hashlib, time, pathlib

# ══════════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="In-Store Requests Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════════
#  PERSISTENCE & PRE-SEEDED USER DATABASE
# ══════════════════════════════════════════════════════════════════════════════════
_DATA_FILE = pathlib.Path(__file__).parent / ".dashboard_data.json"

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def _load_store() -> dict:
    default_store = {
        "users": {
            "admin": {
                "display_name": "Mohammed Shehta",
                "password_hash": _hash("admin123"),
                "role": "admin",
                "agent_name": None,
            },
            "50107": {
                "display_name": "Ahmed El-Kholy",
                "password_hash": _hash("50107"),
                "role": "expert",
                "agent_name": "Ahmed El-Kholy",
            },
            "50399": {
                "display_name": "Ahmed Kadry",
                "password_hash": _hash("50399"),
                "role": "expert",
                "agent_name": "Ahmed Kadry",
            },
            "50187": {
                "display_name": "Amr El-Sayed",
                "password_hash": _hash("50187"),
                "role": "expert",
                "agent_name": "Amr El-Sayed",
            },
            "50461": {
                "display_name": "Eslam Ramadan",
                "password_hash": _hash("50461"),
                "role": "expert",
                "agent_name": "Eslam Ramadan",
            },
            "50274": {
                "display_name": "Mohamed Abdelmageed",
                "password_hash": _hash("50274"),
                "role": "expert",
                "agent_name": "Mohamed Abdelmageed",
            },
            "50476": {
                "display_name": "Mohamed Khalifa",
                "password_hash": _hash("50476"),
                "role": "expert",
                "agent_name": "Mohamed Khalifa",
            },
            "50114": {
                "display_name": "Yahia Ali Shafei",
                "password_hash": _hash("50114"),
                "role": "expert",
                "agent_name": "Yahia Ali Shafei",
            }
        },
        "requests":  [],
        "overrides": {},
    }
    
    if _DATA_FILE.exists():
        try:
            loaded = json.loads(_DATA_FILE.read_text())
            if "users" in loaded:
                for k, v in loaded["users"].items():
                    default_store["users"][k] = v
            if "requests" in loaded:
                default_store["requests"] = loaded["requests"]
            if "overrides" in loaded:
                default_store["overrides"] = loaded["overrides"]
        except Exception:
            pass
            
    return default_store

def _save_store():
    _DATA_FILE.write_text(json.dumps(st.session_state.store, indent=2))

# ══════════════════════════════════════════════════════════════════════════════════
#  CSS  — PREMIUM, HIGH-CONTRAST LIGHT THEME STYLE BLOCK
# ══════════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ══ BASE LIGHT LAYOUT ═══════════════════════════════════════════════ */
.stApp {
    background: radial-gradient(ellipse at 20% 10%, #f4f6fa 0%, #edf0f5 40%, #e4e8f0 100%);
    color: #1e293b;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    border-right: 1px solid #cbd5e1;
}
[data-testid="stSidebar"] * { color: #334155 !important; }
[data-testid="stSidebar"] .stButton button {
    background: linear-gradient(135deg,#ffffff,#f1f5f9) !important;
    border: 1px solid #cbd5e1 !important;
    color: #0f172a !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
[data-testid="stSidebar"] .stButton button:hover {
    background: linear-gradient(135deg,#e2e8f0,#cbd5e1) !important;
    border-color: #94a3b8 !important;
    color: #0f172a !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent; color: #64748b; font-weight: 700;
    border-bottom: 2px solid transparent;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #2563eb !important; border-bottom: 2px solid #2563eb !important;
}
h2,h3 { color:#0f172a !important; font-weight: 800; }
.stMarkdown p { color:#334155; }
hr { border-color:#cbd5e1 !important; }

.stTextInput input, .stNumberInput input, .stSelectbox select, .stDateInput input {
    background: #ffffff !important; border: 1px solid #cbd5e1 !important;
    color: #0f172a !important; border-radius: 10px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.15) !important;
}
.stButton > button {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    border: 1px solid #1d4ed8 !important; color: #ffffff !important;
    border-radius: 10px !important; font-weight: 700 !important;
    transition: all .2s ease;
    box-shadow: 0 2px 4px rgba(37,99,235,0.2);
}
.stButton > button:hover {
    background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
    border-color: #1e40af !important; color: #ffffff !important;
    transform: translateY(-1px); box-shadow: 0 4px 12px rgba(29,78,216,0.3);
}
.stAlert { border-radius: 12px !important; background-color: #eff6ff !important; color: #1e40af !important; border: 1px solid #bfdbfe !important; }

/* ══ CRISP LIGHT KPI CARDS ═══════════════════════════════════════════ */
.kpi-container {
    border-radius: 18px; padding: 1.3rem 1rem; text-align: center;
    min-height: 118px; display: flex; flex-direction: column;
    justify-content: center; margin-bottom: 1rem;
    position: relative; overflow: hidden; transition: transform .25s, box-shadow .25s;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
}
.kpi-container:hover { transform: translateY(-3px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.08); }
.kpi-label {
    font-size: .66rem; letter-spacing: .14em; text-transform: uppercase;
    margin-bottom: .45rem; font-weight: 700; color: #475569; opacity: .8;
}
.kpi-value { font-size: 1.55rem; font-weight: 800; letter-spacing: -.01em; }

.card-total     { background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; }
.card-completed { background: #f0fdf4; border: 1px solid #bbf7d0; color: #15803d; }
.card-issue     { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; }
.card-frt       { background: #fdf2f8; border: 1px solid #fbcfe8; color: #be185d; }
.card-aht       { background: #faf5ff; border: 1px solid #e9d5ff; color: #6b21a8; }
.card-tat       { background: #ecfeff; border: 1px solid #c5f6fa; color: #0e7490; }

/* ══ LIGHT BUSINESS LOGIN ═════════════════════════════════════════════ */
.login-wrap {
    max-width:440px; margin:5rem auto 0; padding:2.5rem 2.4rem 1rem;
    background: #ffffff;
    border:1px solid #e2e8f0; border-radius:22px;
    box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);
}
.login-title {
    font-size:1.75rem; font-weight:800; text-align:center; margin-bottom:.3rem;
    background: linear-gradient(90deg, #1d4ed8, #2563eb, #059669);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.login-sub { font-size:.86rem; text-align:center; color:#64748b; margin-bottom:1.8rem; }

/* ══ SYSTEM BADGES ════════════════════════════════════════════════════ */
.badge { display:inline-block; font-size:.64rem; border-radius:7px; padding:2px 9px; margin-left:6px; font-weight:800; letter-spacing:.1em; }
.badge-admin  { background:#eff6ff; border:1px solid #bfdbfe; color:#1d4ed8; }
.badge-expert { background:#f0fdf4; border:1px solid #bbf7d0; color:#15803d; }

/* ══ SYSTEM NOTIFICATION BANNERS ═══════════════════════════════════════ */
.req-pending  { background:#fffbeb; border:1px solid #fde68a; border-radius:12px; padding:.75rem 1.2rem; margin-bottom:.8rem; color:#b45309; font-size:.88rem; }
.req-approved { background:#f0fdf4; border:1px solid #bbf7d0; border-radius:12px; padding:.75rem 1.2rem; margin-bottom:.8rem; color:#15803d; font-size:.88rem; }
.req-rejected { background:#fef2f2; border:1px solid #fecaca; border-radius:12px; padding:.75rem 1.2rem; margin-bottom:.8rem; color:#b91c1c; font-size:.88rem; }

/* ══ PANEL CONTAINERS ═════════════════════════════════════════════════ */
.section-card { background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:1.5rem 1.8rem; margin-bottom:1.2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

# 👥 Plotly components light template configuration variables
THEME = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(248,250,252,0.8)",
    font_color="#334155",
    margin=dict(l=10, r=10, t=55, b=10)
)

# ══════════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════════
if "store" not in st.session_state:
    st.session_state.store = _load_store()
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username      = None
    st.session_state.role          = None
if "page" not in st.session_state:
    st.session_state.page = "dashboard"
if "force_onboard" not in st.session_state:
    st.session_state.force_onboard = False
if "view_request_form" not in st.session_state:
    st.session_state.view_request_form = False

# ── Helpers لإدارة العمليات ──────────────────────────────────────────────────────────
def users()     -> dict: return st.session_state.store["users"]
def requests()  -> list: return st.session_state.store["requests"]
def overrides() -> dict: return st.session_state.store["overrides"]
def me()        -> str:  return st.session_state.username
def is_admin()  -> bool: return st.session_state.role == "admin"
def cur_user()  -> dict: return users().get(me(), {})

def agent_name_of(uname: str) -> str:
    return users().get(uname, {}).get("agent_name")

def my_agent_name() -> str:
    return agent_name_of(me())

def pending_count() -> int:
    return sum(1 for r in requests() if r["status"] == "pending")

def push_request(uname, rtype, new_value):
    requests().append({
        "id": int(time.time() * 1000), "requester": uname,
        "type": rtype, "new_value": new_value,
        "status": "pending", "ts": time.strftime("%Y-%m-%d %H:%M"),
    })
    _save_store()

def approve_request(req_id):
    for r in requests():
        if r["id"] == req_id and r["status"] == "pending":
            u = r["requester"]
            if r["type"] == "display_name": 
                users()[u]["display_name"] = r["new_value"]
            elif r["type"] == "password":   
                users()[u]["password_hash"] = _hash(r["new_value"])
            elif r["type"] == "visitor_access":
                ukey = u.strip().lower().replace(" ", "_")
                users()[ukey] = {
                    "display_name": u.strip(),
                    "password_hash": _hash("123456789"),
                    "role": "expert",
                    "agent_name": u.strip()
                }
            r["status"] = "approved"; _save_store(); return True
    return False

def reject_request(req_id):
    for r in requests():
        if r["id"] == req_id and r["status"] == "pending":
            r["status"] = "rejected"; _save_store(); return True
    return False

# ══════════════════════════════════════════════════════════════════════════════════
#  METRIC HELPERS
# ══════════════════════════════════════════════════════════════════════════════════
def kpi_colored(label, value, cls):
    return (f'<div class="kpi-container {cls}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div></div>')

def time_to_minutes(s):
    try:
        p = str(s).strip().split(":")
        return int(p[0]) * 60 + int(p[1])
    except: return 0

def fmt_m(v):
    if pd.isna(v) or v <= 0: return "00:00:00"
    t = int(round(v * 60))
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"

def assign_time_tier(m):
    if m <= 15: return "Under 15 Mins"
    if m <= 30: return "15-30 Mins"
    if m <= 45: return "30-45 Mins"
    if m <= 60: return "45-60 Mins"
    return "Over 1 Hour"

DAYS_AR = {
    "Saturday": "السبت", "Sunday": "الأحد", "Monday": "الإثنين",
    "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء",
    "Thursday": "الخميس", "Friday": "الجمعة"
}

# ══════════════════════════════════════════════════════════════════════════════════
#  LOGIN GATE & FIRST-TIME LOGIN ONBOARDING
# ══════════════════════════════════════════════════════════════════════════════════
if not st.session_state.authenticated:
    st.markdown("""
    <div class='login-wrap'>
        <div class='login-title'>💊 Dashboard Login</div>
        <div class='login-sub'>In-Store Requests · AlDawaa</div>
    </div>""", unsafe_allow_html=True)
    
    _, lc, _ = st.columns([1, 1.4, 1])
    with lc:
        if not st.session_state.view_request_form:
