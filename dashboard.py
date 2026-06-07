import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json, hashlib, time, pathlib, urllib.parse, re
from datetime import timedelta

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
#  CSS  — PUFF BACKGROUND THEME & BOLD/LARGE TYPOGRAPHY BLOCK
# ══════════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ══ GLOBAL APP CANVAS ADJUSTMENT (PUFF THEME) ══════════════════════ */
.stApp {
    background: radial-gradient(ellipse at 20% 10%, #f7f1e1 0%, #f4ebd0 40%, #ebdcb9 100%) !important;
    color: #0f172a !important;
}

/* Global Font Weights & Sizes Scaling */
.stApp, p, span, label, input, select {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
}

/* ══ HEADER ELEMENT TYPOGRAPHY (LARGE & BOLD 900) ═══════════════════ */
h1 { font-size: 2.5rem !important; font-weight: 900 !important; color: #0f172a !important; }
h2 { font-size: 2.15rem !important; font-weight: 900 !important; color: #0f172a !important; margin-top: 1rem !important; }
h3 { font-size: 1.65rem !important; font-weight: 900 !important; color: #0f172a !important; }
h4 { font-size: 1.35rem !important; font-weight: 900 !important; color: #0f172a !important; }

.stMarkdown p { 
    color: #1e293b !important; 
    font-size: 1.1rem !important; 
    font-weight: 600 !important; 
}

/* ══ SIDEBAR RESKIN ══════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f1e6c7 0%, #ebdcb9 100%) !important;
    border-right: 2px solid #cbd5e1 !important;
}
[data-testid="stSidebar"] * { 
    color: #0f172a !important; 
    font-weight: 700 !important;
}
[data-testid="stSidebar"] label p {
    font-size: 1.15rem !important;
    font-weight: 800 !important;
}
[data-testid="stSidebar"] .stButton button {
    background: linear-gradient(135deg, #ffffff, #f4ebd0) !important;
    border: 2px solid #bba370 !important;
    color: #0f172a !important;
    border-radius: 10px !important;
    font-weight: 800 !important;
    font-size: 1.05rem !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.06);
}
[data-testid="stSidebar"] .stButton button:hover {
    background: linear-gradient(135deg, #ebdcb9, #dcb98a) !important;
    border-color: #0f172a !important;
}

/* ══ TABS NAVIGATION TYPOGRAPHY Scaling ═════════════════════════════ */
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent; 
    color: #475569 !important; 
    font-weight: 800 !important;
    font-size: 1.2rem !important;
    padding-bottom: 8px !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #1d4ed8 !important; 
    border-bottom: 3px solid #1d4ed8 !important;
}

/* Form Input Layout Contrast Optimization */
.stTextInput input, .stNumberInput input, .stSelectbox select, .stDateInput input {
    background: #ffffff !important; 
    border: 2px solid #bba370 !important;
    color: #0f172a !important; 
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 1.05rem !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #1d4ed8 !important;
    box-shadow: 0 0 0 3px rgba(29,78,216,0.2) !important;
}

.stButton > button {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    border: 2px solid #1e40af !important; 
    color: #ffffff !important;
    border-radius: 10px !important; 
    font-weight: 800 !important;
    font-size: 1.1rem !important;
    padding: 0.5rem 1.5rem !important;
    box-shadow: 0 4px 6px rgba(29,78,216,0.2);
}
.stButton > button:hover {
    background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
    border-color: #0f172a !important; 
    transform: translateY(-1px);
    box-shadow: 0 6px 15px rgba(29,78,216,0.35);
}

.stAlert { 
    border-radius: 12px !important; 
    background-color: #ffffff !important; 
    color: #1e40af !important; 
    border: 2px solid #93c5fd !important;
    font-weight: 700 !important;
}

/* ══ HIGH-CONTRAST BOLD KPI CARDS ═══════════════════════════════════ */
.kpi-container {
    border-radius: 18px; 
    padding: 1.4rem 1.1rem; 
    text-align: center;
    min-height: 124px; 
    display: flex; 
    flex-direction: column;
    justify-content: center; 
    margin-bottom: 1rem;
    box-shadow: 0 4px 8px rgba(0,0,0,0.06);
    border-width: 2px !important;
}
.kpi-container:hover { 
    transform: translateY(-3px); 
    box-shadow: 0 12px 20px rgba(0,0,0,0.1); 
}
.kpi-label {
    font-size: .85rem !important; 
    letter-spacing: .08em; 
    text-transform: uppercase;
    margin-bottom: .5rem; 
    font-weight: 800 !important; 
    color: #334155 !important;
}
.kpi-value { 
    font-size: 1.95rem !important; 
    font-weight: 900 !important; 
    letter-spacing: -.02em; 
}

.card-total     { background: #e0f2fe; border: 2px solid #7dd3fc; color: #0369a1; }
.card-completed { background: #dcfce7; border: 2px solid #86efac; color: #166534; }
.card-issue     { background: #fee2e2; border: 2px solid #fca5a5; color: #991b1b; }
.card-frt       { background: #fce7f3; border: 2px solid #f9a8d4; color: #9d174d; }
.card-aht       { background: #f3e8ff; border: 2px solid #d8b4fe; color: #6b21a8; }
.card-tat       { background: #ecfeff; border: 2px solid #67e8f9; color: #155e75; }
.card-store     { background: #fffbeb; border: 2px solid #fde047; color: #b45309; }
.card-actions   { background: #eff6ff; border: 2px solid #93c5fd; color: #1e3a8a; }

/* ══ AUTHENTICATION MODULE SCREEN RESKIN ═════════════════════════════ */
.login-wrap {
    max-width:460px; margin:5rem auto 0; padding:2.8rem 2.5rem 1.5rem;
    background: #ffffff;
    border:2px solid #bba370; border-radius:22px;
    box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);
}
.login-title {
    font-size: 2rem !important; font-weight: 900 !important; text-align: center; margin-bottom: .4rem;
    background: linear-gradient(90deg, #1d4ed8, #2563eb, #047857);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.login-sub { font-size: 1rem !important; text-align: center; color: #475569; margin-bottom: 2rem; font-weight: 700 !important; }

/* ══ SYSTEM BADGES & NOTIFICATIONS ════════════════════════════════════ */
.badge { display:inline-block; font-size:.72rem !important; border-radius:7px; padding:3px 11px; margin-left:6px; font-weight:900; letter-spacing:.08em; }
.badge-admin  { background:#dbeafe; border:2px solid #3b82f6; color:#1d4ed8; }
.badge-expert { background:#dcfce7; border:2px solid #22c55e; color:#166534; }

.req-pending  { background:#fef3c7; border:2px solid #f59e0b; border-radius:12px; padding:.85rem 1.4rem; margin-bottom:.8rem; color:#78350f; font-size:.95rem; font-weight:700; }
.req-approved { background:#dcfce7; border:2px solid #22c55e; border-radius:12px; padding:.85rem 1.4rem; margin-bottom:.8rem; color:#166534; font-size:.95rem; font-weight:700; }
.req-rejected { background:#fee2e2; border:2px solid #ef4444; border-radius:12px; padding:.85rem 1.4rem; margin-bottom:.8rem; color:#991b1b; font-size:.95rem; font-weight:700; }

.section-card { background:#ffffff; border:2px solid #cbd5e1; border-radius:16px; padding:1.6rem 2rem; margin-bottom:1.4rem; box-shadow: 0 2px 4px rgba(0,0,0,0.04); }

/* ══ FULL-WIDTH CUSTOM HTML TABLE STYLING FOR SCORECARD ═════════════ */
.scorecard-container {
    width: 100%;
    overflow-x: auto;
    margin-top: 1rem;
    margin-bottom: 2rem;
    border-radius: 12px;
    box-shadow: 0 6px 12px rgba(0,0,0,0.08);
}
.scorecard-container table {
    width: 100%;
    border-collapse: collapse;
    background-color: #ffffff;
    font-family: inherit;
    table-layout: auto;
}
.scorecard-container th {
    background-color: #1e40af !important; /* Deep Professional Blue */
    color: #ffffff !important;            /* White Text */
    font-weight: 900 !important;          /* Extra Bold */
    font-size: 0.95rem !important;        /* Slightly reduced for better fit */
    text-align: center !important;        /* Centered Header */
    padding: 8px 5px !important;          /* Reduced padding */
    white-space: normal !important;       /* Allow wrapping to save horizontal space */
    border: 1px solid #cbd5e1;
    line-height: 1.2;
    vertical-align: middle;
}
.scorecard-container td {
    text-align: center !important;        /* Centered Data */
    padding: 8px 5px !important;          /* Reduced padding */
    font-size: 0.95rem !important;        /* Slightly reduced for better fit */
    border: 1px solid #e2e8f0;
    white-space: nowrap;                  /* Keep numbers on a single line */
    vertical-align: middle;
}
/* Ensure the Expert column remains visibly strong */
.scorecard-container td:first-child {
    font-weight: 900 !important;
    color: #0f172a !important;
    text-align: left !important;
    padding-left: 10px !important;
    white-space: nowrap;                  /* Keep names on a single line */
}
</style>
""", unsafe_allow_html=True)

# 👥 Plotly components template engine synced configuration variables
THEME = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(247,241,225,0.6)",
    font_color="#0f172a",
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

# ── Helpers لإدارة العمليات التشغيلية ───────────────────────────────────────────────
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
#  METRIC HELPERS WITH TREND INDICATOR
# ══════════════════════════════════════════════════════════════════════════════════
def calc_change(curr, prev):
    if pd.isna(curr): curr = 0
    if pd.isna(prev): prev = 0
    if prev == 0:
        return 100.0 if curr > 0 else 0.0
    return ((curr - prev) / prev) * 100.0

def kpi_colored(label, value, cls, change=None, inverse=False, neutral=False):
    change_html = ""
    if change is not None:
        if neutral:
            color = "#64748b" 
            arrow = "▲" if change > 0 else ("▼" if change < 0 else "−")
        else:
            if change > 0:
                arrow = "▲"
                color = "#ef4444" if inverse else "#10b981" 
            elif change < 0:
                arrow = "▼"
                color = "#10b981" if inverse else "#ef4444" 
            else:
                arrow = "−"
                color = "#94a3b8" 
        
        bg_color = color + "20" 
        change_html = f'<span style="font-size: 0.85rem; margin-left: 8px; padding: 2px 6px; border-radius: 8px; font-weight: 800; color: {color}; background-color: {bg_color}; display: inline-flex; align-items: center; justify-content: center; vertical-align: middle; white-space: nowrap;">{arrow} {abs(change):.1f}%</span>'
        
    return (f'<div class="kpi-container {cls}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value" style="display:flex; align-items:center; justify-content:center; flex-wrap:wrap; gap:4px;">{value}{change_html}</div></div>')

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
#  OFFICIAL EXPERTS WHITELIST, ALIASES & ID MAPPING
# ══════════════════════════════════════════════════════════════════════════════════
OFFICIAL_EXPERTS = [
    "Ahmed El-Kholy", 
    "Ahmed Kadry", 
    "Amr El-Sayed", 
    "Eslam Ramadan", 
    "Mohamed Abdelmageed", 
    "Mohamed Khalifa", 
    "Yahia Ali Shafei"
]

EXPERT_ID_MAP = {
    "Ahmed El-Kholy": "50107",
    "Ahmed Kadry": "50399",
    "Amr El-Sayed": "50187",
    "Eslam Ramadan": "50461",
    "Mohamed Abdelmageed": "50274",
    "Mohamed Khalifa": "50476",
    "Yahia Ali Shafei": "50114"
}

# 🧠 Name Normalizer
AGENT_ALIASES = {
    "mohamed abdelmajid": "Mohamed Abdelmageed",
    "mohamed el-sayed": "Mohamed Abdelmageed",
    "محمد عبد المجيد": "Mohamed Abdelmageed",
    "محمد السيد عبد المجيد": "Mohamed Abdelmageed",
    "محمد السيد": "Mohamed Abdelmageed",
    "50274": "Mohamed Abdelmageed",
    
    "احمد الخولى": "Ahmed El-Kholy",
    "أحمد الخولي": "Ahmed El-Kholy",
    "احمد الخولي": "Ahmed El-Kholy",
    "50107": "Ahmed El-Kholy",
    
    "يحي علي شافعي": "Yahia Ali Shafei",
    "يحيي علي شافعي": "Yahia Ali Shafei",
    "50114": "Yahia Ali Shafei",
    
    "عمرو محمد السيد": "Amr El-Sayed",
    "50187": "Amr El-Sayed",
    
    "أحمد محمد قدري": "Ahmed Kadry",
    "احمد محمد قدري": "Ahmed Kadry",
    "احمد قدري": "Ahmed Kadry",
    "50399": "Ahmed Kadry",
    
    "إسلام رمضان خليل": "Eslam Ramadan",
    "أصلان رمضان خليل": "Eslam Ramadan",
    "اسلام رمضان": "Eslam Ramadan",
    "50461": "Eslam Ramadan",
    
    "محمد خليفة جاب الله": "Mohamed Khalifa",
    "محمد خليفه جاب الله": "Mohamed Khalifa",
    "محمد خليفة": "Mohamed Khalifa",
    "محمد خليفه": "Mohamed Khalifa",
    "50476": "Mohamed Khalifa",
    
    "محمد شحته عبدالنبي مصطفي": "Muhammad Shehta",
    "50228": "Muhammad Shehta",
}

EXCLUSION_LIST = [
    'off', 'اوف', 'أوف', 'راحة', 
    'annual', 'casual', 'عارضة', 'عارضه', 'v', 'a', 'vacation', 
    'resign', 'استقالة', 'مستقيل', 'sick', 'مرضي',
    'nan', 'none', ''
]

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
            inp_u = st.text_input("Username / ID", placeholder="Enter ID", key="li_u")
            inp_p = st.text_input("Password", type="password", placeholder="Enter password", key="li_p")
            
            if st.button("🔐 Login", use_container_width=True):
                uname = inp_u.strip().lower()
                udata = users().get(uname)
                if udata and udata["password_hash"] == _hash(inp_p):
                    if inp_u.strip() == inp_p.strip() and udata["role"] == "expert":
                        st.session_state.username = uname
                        st.session_state.force_onboard = True
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.session_state.authenticated = True
                        st.session_state.username = uname
                        st.session_state.role = udata["role"]
                        st.session_state.page = "dashboard"
                        st.rerun()
                else:
                    st.error("❌ Incorrect username or password.")
            
            st.write("")
            if st.button("🚫 Not on the list? Request Access", use_container_width=True):
                st.session_state.view_request_form = True
                st.rerun()
        else:
            st.markdown("### 📝 Request Admin Authorization")
            visitor_name = st.text_input("Enter Your Full Name", placeholder="e.g. Ahmed Ali")
            
            if st.button("📤 Submit Access Request", use_container_width=True):
                if visitor_name.strip():
                    push_request(visitor_name.strip(), "visitor_access", "123456789")
                    st.success("✅ Request sent! Username will be your name, default password will be 123456789 upon approval.")
                    time.sleep(2)
                    st.session_state.view_request_form = False
                    st.rerun()
                else:
                    st.error("Name field cannot be left empty.")
            
            if st.button("← Back to Login", use_container_width=True):
                st.session_state.view_request_form = False
                st.rerun()
    st.stop()

if st.session_state.force_onboard:
    st.markdown("## ⚙️ Mandatory Password Update Required")
    st.info("🚨 This is your first login. You must update your password before accessing dashboard metrics.")
    _, ob_col, _ = st.columns([1, 1.5, 1])
    with ob_col:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        with st.form("onboard_pass_form"):
            new_ob1 = st.text_input("Set New Password", type="password")
            new_ob2 = st.text_input("Confirm New Password", type="password")
            submit_ob = st.form_submit_button("💾 Save & Open Dashboard", use_container_width=True)
        if submit_ob:
            if new_ob1 != new_ob2:
                st.error("❌ Passwords do not match.")
            elif len(new_ob1) < 6:
                st.error("❌ Password must be at least 6 characters.")
            else:
                uname = st.session_state.username
                users()[uname]["password_hash"] = _hash(new_ob1)
                _save_store()
                st.session_state.role = users()[uname]["role"]
                st.session_state.force_onboard = False
                st.session_state.page = "dashboard"
                st.success("✅ Password configured successfully!")
                time.sleep(1.5)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════════
#  SIDEBAR MODULE
# ══════════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## Approvals Team Dashboard")

    badge_cls = "badge-admin" if is_admin() else "badge-expert"
    badge_txt = "ADMIN" if is_admin() else "EXPERT"
    st.markdown(
        f"👤 **{cur_user().get('display_name', '–')}** "
        f"<span class='badge {badge_cls}'>{badge_txt}</span>",
        unsafe_allow_html=True
    )

    sb1, sb2 = st.columns(2)
    with sb1:
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.page = "settings"; st.rerun()
    with sb2:
        if st.button("🚪 Logout", use_container_width=True):
            for k in ("authenticated", "username", "role", "page", "force_onboard"):
                st.session_state.pop(k, None)
            st.rerun()

    if is_admin() and pending_count() > 0:
        pc = pending_count()
        st.warning(f"🔔 {pc} pending system change request{'s' if pc > 1 else ''}")

    st.success("📡 Live Sync Active")
    if is_admin() and st.button("🔄 Refresh Data Now", use_container_width=True):
        st.cache_data.clear()

    @st.cache_data(ttl=600, show_spinner="Syncing database tables…")
    def load_data():
        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
                creds = Credentials.from_service_account_info(
                    json.loads(st.secrets["gspread"]["credentials"]), scopes=scopes)
            else:
                st.error("❌ Secrets file layout unconfigured.")
                return pd.DataFrame(), pd.DataFrame()
            
            client = gspread.authorize(creds)
            sheet = client.open("AlDawaa Tickets Data")
            
            all_dfs = []
            roster_df = pd.DataFrame() 
            
            for ws in sheet.worksheets():
                data = ws.get_all_values()
                if len(data) < 2: continue
                
                if ws.title.strip() == "Working Days":
                    roster_df = pd.DataFrame(data[1:], columns=[str(c).strip() for c in data[0]])
                    continue
                
                dft = pd.DataFrame(data[1:], columns=[str(c).strip() for c in data[0]])
                mp = {}; seen = set()
                for col in dft.columns:
                    cl = col.lower(); t = None
                    if   "id"       in cl and "req"    in cl: t = "Request ID"
                    elif "date"     in cl:                     t = "Request Date"
                    elif "type"     in cl:                     t = "Request Type"
                    elif "status"   in cl and "count"  in cl: t = "Status Count"
                    elif "status"   in cl:                     t = "Status"
                    elif "assigned" in cl or "agent"   in cl: t = "Assigned By"
                    elif "response" in cl and "take"   in cl: t = "Response Take"
                    elif "action"   in cl and "take"   in cl: t = "First Action Take"
                    elif "request"  in cl and "take"   in cl: t = "Request Take"
                    elif "email"    in cl or "special" in cl: t = "Is Special Request(By Email)"
                    elif "hic"      in cl or "insurance" in cl: t = "HIC"
                    elif "store" in cl or "branch" in cl or "pharmacy" in cl: t = "Store ID"
                    if t and t not in seen: mp[col] = t; seen.add(t)
                dft.rename(columns=mp, inplace=True)
                all_dfs.append(dft)
            
            if not all_dfs: 
                return pd.DataFrame(), roster_df
                
            df = pd.concat(all_dfs, ignore_index=True, sort=False)
            df.replace("", np.nan, inplace=True)
            for c in ["Request ID", "Request Date", "Request Type", "Status", "Status Count",
                      "Request Take", "Response Take", "First Action Take",
                      "Assigned By", "Is Special Request(By Email)", "HIC"]:
                if c not in df.columns: df[c] = np.nan
            
            if "Store ID" not in df.columns: df["Store ID"] = "Unknown"
            
            df["Status"]       = df["Status"].fillna("Unknown")
            df["Status Count"] = pd.to_numeric(df["Status Count"], errors="coerce").fillna(0).astype(int)
            df["Request Type"] = df["Request Type"].fillna("Unknown Type")
            df["HIC"]          = df["HIC"].fillna("Unknown")
            df["Assigned By"]  = df["Assigned By"].fillna("Unassigned").astype(str).str.strip()
            df["Store ID"]     = df["Store ID"].fillna("Unknown").astype(str).str.strip()
            
            id_to_name = {v: k for k, v in EXPERT_ID_MAP.items()}
            def normalize_name(name):
                n_lower = name.lower()
                if n_lower in AGENT_ALIASES:
                    return AGENT_ALIASES[n_lower]
                if name in id_to_name:
                    return id_to_name[name]
                return name
                
            df["Assigned By"] = df["Assigned By"].apply(normalize_name)
            
            dp = pd.to_datetime(df["Request Date"], errors="coerce")
            df["Request Date"]             = dp
            df["Date Only"]                = dp.dt.date
            df["Hour"]                     = dp.dt.hour.fillna(0).astype(int)
            df["Day Name"]                 = dp.dt.day_name().fillna("Unknown")
            df["Request Take (min)"]       = df["Request Take"].apply(time_to_minutes).fillna(0)
            df["Response Take (min)"]      = df["Response Take"].apply(time_to_minutes).fillna(0)
            df["First Action Take (min)"]  = df["First Action Take"].apply(time_to_minutes).fillna(0)
            df["AHT (min)"]                = df["First Action Take (min)"]
            df["Is Email"] = (
                df["Is Special Request(By Email)"].astype(str).str.strip().str.lower() == "yes")
                
            return df, roster_df
            
        except Exception as e:
            st.error(f"❌ Connection Error: {e}")
            return pd.DataFrame(), pd.DataFrame()

    df_raw, df_roster = load_data()
    
    if df_raw.empty:
        st.warning("Empty source records."); st.stop()

    # ── DYNAMIC DEFAULT DATE CALCULATOR (LAST ENDED MONTH) ──
    st.markdown("### 🔍 Global Filters")
    
    raw_dates = pd.to_datetime(df_raw["Request Date"]).dropna()
    if not raw_dates.empty:
        max_uploaded_date = raw_dates.max()
        first_of_current_upload_month = max_uploaded_date.replace(day=1)
        last_day_of_ended_month = first_of_current_upload_month - pd.Timedelta(days=1)
        first_day_of_ended_month = last_day_of_ended_month.replace(day=1)
        
        default_from = first_day_of_ended_month.date()
        default_to = last_day_of_ended_month.date()
    else:
        default_from = df_raw["Date Only"].dropna().min()
        default_to = df_raw["Date Only"].dropna().max()

    min_d = df_raw["Date Only"].dropna().min()
    max_d = df_raw["Date Only"].dropna().max()
    
    date_range = st.date_input("Date Range", value=(default_from, default_to), min_value=min_d, max_value=max_d)
    d_from, d_to = (
        date_range if isinstance(date_range, (list, tuple)) and len(date_range) == 2 else (min_d, max_d)
    )
    if d_from == d_to:
        st.caption(f"📅 {DAYS_AR.get(pd.to_datetime(d_from).day_name(), '')}")
        
    # Calculate Previous Period Range for KPI Trends
    delta_days = (d_to - d_from).days + 1
    prev_d_to = d_from - timedelta(days=1)
    prev_d_from = prev_d_to - timedelta(days=delta_days - 1)
    
    PERIOD_KEY = f"{d_from}_{d_to}"
    
    sel_hic = st.multiselect("HIC", sorted(df_raw["HIC"].dropna().unique()))

# ══════════════════════════════════════════════════════════════════════════════════
#  APPLYING SIDEBAR FILTERS TO MAIN DATAFRAMES
# ══════════════════════════════════════════════════════════════════════════════════
df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
df_prev_all = df_raw[(df_raw["Date Only"] >= prev_d_from) & (df_raw["Date Only"] <= prev_d_to)].copy()

if sel_hic:    
    df = df[df["HIC"].isin(sel_hic)]
    df_prev_all = df_prev_all[df_prev_all["HIC"].isin(sel_hic)]

# ══════════════════════════════════════════════════════════════════════════════════
#  SETTINGS PANEL
# ══════════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "settings":
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"; st.rerun()

    if is_admin():
        st.markdown("## ⚙️ Admin Control Panel")
        atab1, atab2, atab3 = st.tabs(["👤 My Profile", "🔔 Change & Access Requests", "👥 Manage Dashboard Users"])

        with atab1:
            st.markdown("### Update Profile Fields")
            urow = users()[me()]
            st.markdown("<div class='section-card'>", unsafe_allow_html=True)
            st.markdown("**✏️ Display Name**")
            with st.form("admin_name_form"):
                new_dn = st.text_input("New Display Name", value=urow["display_name"])
                if st.form_submit_button("💾 Save Name", use_container_width=True):
                    if new_dn.strip() and new_dn.strip() != urow["display_name"]:
                        users()[me()]["display_name"] = new_dn.strip()
                        _save_store(); st.success("✅ Profile display name updated."); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div class='section-card'>", unsafe_allow_html=True)
            st.markdown("**🔑 Change Password**")
            with st.form("admin_pw_form"):
                old_pw  = st.text_input("Current Account Password", type="password")
                new_pw1 = st.text_input("New Secure Password",     type="password")
                new_pw2 = st.text_input("Confirm Secure Password", type="password")
                if st.form_submit_button("💾 Update Password", use_container_width=True):
                    if _hash(old_pw) != urow["password_hash"]: st.error("❌ Password input incorrect.")
                    elif new_pw1 != new_pw2: st.error("❌ Confirmation inputs mismatch.")
                    elif len(new_pw1) < 6:   st.error("❌ Minimum limit 6 characters.")
                    else:
                        users()[me()]["password_hash"] = _hash(new_pw1)
                        _save_store(); st.success("✅ Administrative password saved.")
            st.markdown("</div>", unsafe_allow_html=True)

        with atab2:
            st.markdown("### 🔔 Change & Visitor Access Requests")
            pending = [r for r in requests() if r["status"] == "pending"]
            if not pending:
                st.info("✅ No requests pending approval.")
            else:
                for req in pending:
                    if req["type"] == "visitor_access":
                        st.markdown(f"""
                        <div class='req-pending'>
                            🕐 <b>{req['ts']}</b> &nbsp;|&nbsp; 🔑 <b>VISITOR REQUEST</b> &nbsp;|&nbsp;
                            Full Name: <b>{req['requester']}</b> wants an active account.
                        </div>""", unsafe_allow_html=True)
                        rc1, rc2, rc3 = st.columns([3, 1, 1])
                        with rc2:
                            if st.button("✅ Approve Access", key=f"apr_vis_{req['id']}", use_container_width=True):
                                approve_request(req["id"])
                                st.success(f"Approved account for visitor: {req['requester']}."); st.rerun()
                        with rc3:
                            if st.button("❌ Deny Access", key=f"rej_vis_{req['id']}", use_container_width=True):
                                reject_request(req["id"]); st.warning("Access request rejected."); st.rerun()
                    else:
                        udata_r   = users().get(req["requester"], {})
                        udisp     = udata_r.get("display_name", req["requester"])
                        req_label = "Display Name" if req["type"] == "display_name" else "Password"
                        st.markdown(f"""
                        <div class='req-pending'>
                            🕐 <b>{req['ts']}</b> &nbsp;|&nbsp; 👤 <b>{udisp}</b> &nbsp;|&nbsp; Wants to adjust <b>{req_label}</b>
                        </div>""", unsafe_allow_html=True)
                        rc1, rc2, rc3 = st.columns([3, 1, 1])
                        with rc2:
                            if st.button("✅ Approve", key=f"apr_{req['id']}", use_container_width=True):
                                approve_request(req["id"]); st.success("Approved successfully."); st.rerun()
                        with rc3:
                            if st.button("❌ Reject", key=f"rej_{req['id']}", use_container_width=True):
                                reject_request(req["id"]); st.warning("Rejected successfully."); st.rerun()

        with atab3:
            st.markdown("### 👥 Manage Dashboard Users")
            
            with st.expander("➕ Add New User"):
                with st.form("add_new_user_form"):
                    c1, c2 = st.columns(2)
                    with c1:
                        add_uname = st.text_input("Username / ID *", key="add_uname")
                        add_dname = st.text_input("Display Name *", key="add_dname")
                        add_role = st.selectbox("Role", ["expert", "admin"], key="add_role")
                    with c2:
                        add_aname = st.text_input("Agent Key Mapping (Sheets)", key="add_aname")
                        add_pass1 = st.text_input("Password *", type="password", key="add_pass1")
                        add_pass2 = st.text_input("Confirm Password *", type="password", key="add_pass2")
                    
                    submit_add = st.form_submit_button("➕ Create Account", use_container_width=True)
                    
                    if submit_add:
                        add_uname = add_uname.strip().lower()
                        if not add_uname or not add_dname.strip() or not add_pass1:
                            st.error("❌ Please fill in all required fields (*).")
                        elif add_uname in users():
                            st.error("❌ Username/ID already exists.")
                        elif add_pass1 != add_pass2:
                            st.error("❌ Passwords do not match.")
                        elif len(add_pass1) < 6:
                            st.error("❌ Password must be at least 6 characters.")
                        else:
                            users()[add_uname] = {
                                "display_name": add_dname.strip(),
                                "password_hash": _hash(add_pass1),
                                "role": add_role,
                                "agent_name": add_aname.strip() if add_aname.strip() else None
                            }
                            _save_store()
                            st.success(f"✅ Account for {add_dname.strip()} created successfully!")
                            time.sleep(1)
                            st.rerun()
            
            st.divider()

            for uname, urow in list(users().items()):
                role_icon = "🔑" if urow["role"] == "admin" else "👤"
                with st.expander(f"{role_icon} {urow['display_name']} (@{uname})"):
                    with st.form(f"admin_edit_{uname}"):
                        eu_dn   = st.text_input("Display Username", value=urow["display_name"], key=f"dn_{uname}")
                        eu_an   = st.text_input("Agent Key Mapping (Sheets)", value=urow.get("agent_name") or "", key=f"an_{uname}")
                        eu_p1   = st.text_input("Override Password", type="password", key=f"p1_{uname}")
                        eu_p2   = st.text_input("Confirm Password", type="password", key=f"p2_{uname}")
                        eu_role = st.selectbox("Role", ["expert","admin"], index=0 if urow["role"] != "admin" else 1, key=f"rl_{uname}")
                        
                        col1, col2 = st.columns([3, 1])
                        with col1: saved = st.form_submit_button("💾 Update User Settings", use_container_width=True)
                        with col2: deleted = st.form_submit_button("🗑️ Delete User", use_container_width=True)
                        
                    if saved:
                        if eu_dn.strip(): users()[uname]["display_name"] = eu_dn.strip()
                        users()[uname]["agent_name"] = eu_an.strip() if eu_an.strip() else None
                        users()[uname]["role"] = eu_role
                        if eu_p1 and eu_p1 == eu_p2: users()[uname]["password_hash"] = _hash(eu_p1)
                        _save_store(); st.success("✅ User settings updated."); st.rerun()
                        
                    if deleted:
                        if uname == "admin":
                            st.error("❌ Cannot delete the primary admin account!")
                        elif uname == me():
                            st.error("❌ You cannot delete your own account while logged in!")
                        else:
                            users().pop(uname)
                            _save_store()
                            st.success(f"🗑️ Account for {uname} has been successfully revoked and deleted.")
                            time.sleep(1)
                            st.rerun()
    else:
        st.markdown("## ⚙️ My Profile Settings")
        urow = users()[me()]
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("### ✏️ Propose Profile Display Name Change")
        with st.form("expert_name_form"):
            req_name = st.text_input("Proposed Display Name", placeholder=urow["display_name"])
            if st.form_submit_button("📤 Submit Request", use_container_width=True):
                if req_name.strip(): push_request(me(), "display_name", req_name.strip()); st.success("✅ Request delivered."); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("### 🔑 Direct Password Adjuster Form")
        with st.form("expert_pw_direct"):
            get_cur_pw = st.text_input("Verify Current Password", type="password")
            new_p1     = st.text_input("Set New Secret Password", type="password")
            new_p2     = st.text_input("Confirm New Secret Password", type="password")
            if st.form_submit_button("💾 Save Changes", use_container_width=True):
                if _hash(get_cur_pw) == urow["password_hash"] and new_p1 == new_p2 and len(new_p1) >= 6:
                    users()[me()]["password_hash"] = _hash(new_p1); _save_store(); st.success("✅ Password updated."); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════════
#  DASHBOARD MAIN MODULE
# ══════════════════════════════════════════════════════════════════════════════════
caption_text = (
    f"🔍 Search Period: {d_from} ({DAYS_AR.get(pd.to_datetime(d_from).day_name(), '')})"
    if d_from == d_to else f"🔍 Search Period: {d_from} to {d_to}"
)
st.markdown("## 💊 In-Store Requests Matrix")
st.caption(caption_text)

# ══════════════════════════════════════════════════════════════════════════════════
#  TABS NAVIGATION ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["📈 Operational Insights", "👥 Team Performance & KPIs"])

# ── TAB 1 — Operational Insights ──────────────────────────────────────────────────
with tab1:
    c1, c2 = st.columns(2)
    with c1: esc  = st.checkbox("🔥 Escalated Cases Only",    value=False, key="t1_esc")
    with c2: nesc = st.checkbox("🟢 Non-Escalated Cases Only", value=False, key="t1_nesc")

    dfm = df.copy()
    if esc  and not nesc: dfm = dfm[dfm["Is Email"] == True]
    elif nesc and not esc: dfm = dfm[dfm["Is Email"] == False]
    
    dfm_prev = df_prev_all.copy()
    if esc  and not nesc: dfm_prev = dfm_prev[dfm_prev["Is Email"] == True]
    elif nesc and not esc: dfm_prev = dfm_prev[dfm_prev["Is Email"] == False]

    # Current Metrics
    total = len(dfm)
    ss    = dfm["Status"].astype(str).str.strip()
    ok    = dfm[ss.str.contains("Closed", na=False, case=False) & ~ss.str.contains("issue", na=False, case=False)].shape[0]
    issue = dfm[ss.str.contains("Closed", na=False, case=False) & ss.str.contains("issue", na=False, case=False)].shape[0]
    curr_frt_val = dfm["Response Take (min)"].mean() if not dfm.empty else 0
    curr_aht_val = dfm["AHT (min)"].mean() if not dfm.empty else 0
    curr_tat_val = dfm["Request Take (min)"].mean() if not dfm.empty else 0
    
    curr_merged_aht_val = curr_frt_val + curr_aht_val
    h_merged_aht = fmt_m(curr_merged_aht_val)
    h_tat = fmt_m(curr_tat_val)
    
    ok_pct = (ok / total * 100) if total > 0 else 0
    issue_pct = (issue / total * 100) if total > 0 else 0
    stores_count = dfm[dfm["Store ID"] != "Unknown"]["Store ID"].nunique() if not dfm.empty else 0
    status_actions_sum = int(dfm["Status Count"].sum()) if not dfm.empty else 0
    
    # Previous Metrics
    prev_total = len(dfm_prev)
    ss_prev    = dfm_prev["Status"].astype(str).str.strip()
    prev_ok    = dfm_prev[ss_prev.str.contains("Closed", na=False, case=False) & ~ss_prev.str.contains("issue", na=False, case=False)].shape[0]
    prev_issue = dfm_prev[ss_prev.str.contains("Closed", na=False, case=False) & ss_prev.str.contains("issue", na=False, case=False)].shape[0]
    prev_frt_val = dfm_prev["Response Take (min)"].mean() if not dfm_prev.empty else 0
    prev_aht_val = dfm_prev["AHT (min)"].mean() if not dfm_prev.empty else 0
    prev_tat_val = dfm_prev["Request Take (min)"].mean() if not dfm_prev.empty else 0
    
    prev_merged_aht_val = prev_frt_val + prev_aht_val
    
    prev_ok_pct = (prev_ok / prev_total * 100) if prev_total > 0 else 0
    prev_issue_pct = (prev_issue / prev_total * 100) if prev_total > 0 else 0
    prev_stores_count = dfm_prev[dfm_prev["Store ID"] != "Unknown"]["Store ID"].nunique() if not dfm_prev.empty else 0
    prev_status_actions_sum = int(dfm_prev["Status Count"].sum()) if not dfm_prev.empty else 0

    # Calculate Trend Changes 
    chg_total = calc_change(total, prev_total)
    chg_stores = calc_change(stores_count, prev_stores_count)
    chg_actions = calc_change(status_actions_sum, prev_status_actions_sum)
    chg_ok = calc_change(ok_pct, prev_ok_pct)
    chg_issue = calc_change(issue_pct, prev_issue_pct)
    chg_merged_aht = calc_change(curr_merged_aht_val, prev_merged_aht_val)
    chg_tat = calc_change(curr_tat_val, prev_tat_val)

    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
    r2c1, r2c2 = st.columns(2)
    
    r1c1.markdown(kpi_colored("Total Tickets",      f"{total:,}", "card-total", chg_total, neutral=True),     unsafe_allow_html=True)
    r1c2.markdown(kpi_colored("Stores Served",      f"{stores_count:,}", "card-store", chg_stores, neutral=True),  unsafe_allow_html=True)
    r1c3.markdown(kpi_colored("Total Actions",      f"{status_actions_sum:,}", "card-actions", chg_actions, neutral=True),  unsafe_allow_html=True)
    r1c4.markdown(kpi_colored("Closed Completed",   f"{ok:,} <span style='font-size:1rem; opacity:0.8'>({ok_pct:.1f}%)</span>",    "card-completed", chg_ok), unsafe_allow_html=True)
    r1c5.markdown(kpi_colored("Closed with Issue", f"{issue:,} <span style='font-size:1rem; opacity:0.8'>({issue_pct:.1f}%)</span>", "card-issue", chg_issue, inverse=True),     unsafe_allow_html=True)
    
    r2c1.markdown(kpi_colored("AHT (Average Handling Time)", h_merged_aht, "card-aht", chg_merged_aht, inverse=True),       unsafe_allow_html=True)
    r2c2.markdown(kpi_colored("Avg Service (TAT)", h_tat,        "card-tat", chg_tat, inverse=True),       unsafe_allow_html=True)
    st.write("")

    if not dfm.empty:
        # Layout Division: 70% Chart | 30% Interactive Slicer
        sb_col1, sb_col2 = st.columns([7, 3])
        
        with sb_col2:
            st.markdown("<br><b>🎛️ Filter by Request Type</b>", unsafe_allow_html=True)
            req_counts = dfm['Request Type'].value_counts()
            req_pct = (req_counts / len(dfm) * 100).round(1)
            slicer_options = ["All Types"] + [f"{rt} ({pct}%)" for rt, pct in zip(req_pct.index, req_pct.values)]
            selected_slicer = st.radio("Select Request Type:", slicer_options, label_visibility="collapsed")
            
        if selected_slicer == "All Types":
            dfm_sb = dfm.copy()
        else:
            selected_rt = selected_slicer.rsplit(" (", 1)[0]
            dfm_sb = dfm[dfm["Request Type"] == selected_rt].copy()

        with sb_col1:
            st.markdown("### ⏱️ Service Time Breakdown (FRT & TAT)")
            if not dfm_sb.empty:
                dfm_sb["Response Tier"] = dfm_sb["Response Take (min)"].apply(assign_time_tier)
                dfm_sb["Service Tier"]  = dfm_sb["Request Take (min)"].apply(assign_time_tier)
                rd = dfm_sb.groupby("Response Tier").size().reset_index(name="Tickets")
                rd["SLA Category"] = "Response Time"
                rd.rename(columns={"Response Tier": "SLA Tier"}, inplace=True)
                sd = dfm_sb.groupby("Service Tier").size().reset_index(name="Tickets")
                sd["SLA Category"] = "Service Resolution"
                sd.rename(columns={"Service Tier": "SLA Tier"}, inplace=True)
                sb_df = pd.concat([rd, sd], ignore_index=True)
                
                fig_sb = px.sunburst(sb_df, path=["SLA Category", "SLA Tier"], values="Tickets", branchvalues="total")
                
                custom_colors = {
                    "Response Time": "#3b82f6",       # Blue
                    "Service Resolution": "#10b981",  # Green
                    "Under 15 Mins": "#2ea44f", 
                    "15-30 Mins": "#2188ff", 
                    "30-45 Mins": "#bc8cff", 
                    "45-60 Mins": "#f9c513", 
                    "Over 1 Hour": "#ea4a5a"
                }
                
                trace = fig_sb.data[0]
                new_colors = [custom_colors.get(label, "#cccccc") for label in trace.labels]
                
                new_text = []
                new_hover = []
                for p, label in zip(trace.parents, trace.labels):
                    if p == "" or p is None:
                        new_text.append(f"<b>{label}</b>")
                        new_hover.append("<b>%{label}</b><br>Total Tickets: %{value:,}<extra></extra>")
                    else:
                        new_text.append("%{label}<br>%{value:,}<br>%{percentParent:.1%}")
                        new_hover.append("<b>%{label}</b><br>Tickets Count: %{value:,}<br>Percentage: %{percentParent:.1%}<extra></extra>")
                        
                fig_sb.update_traces(
                    texttemplate=new_text,
                    textinfo="none",
                    hovertemplate=new_hover,
                    marker=dict(colors=new_colors)
                )
                
                fig_sb.update_layout(**THEME, height=520, margin=dict(t=20, b=20, l=10, r=10))
                st.plotly_chart(fig_sb, use_container_width=True)
            else:
                st.info("No data available for this request type.")

    st.divider()

    # ⏳ Ticket flow rate over daily hours — STRICT DATE FILTER APPLIED
    if not df_raw.empty:
        st.markdown("### ⏳ Ticket flow rate over daily hours")
        
        df_flow_strict = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
        
        if esc and not nesc: 
            df_flow_strict = df_flow_strict[df_flow_strict["Is Email"] == True]
        elif nesc and not esc: 
            df_flow_strict = df_flow_strict[df_flow_strict["Is Email"] == False]
            
        hrs = df_flow_strict.groupby("Hour").agg(Volume=("Request ID", "count"), AR=("Response Take (min)" , "mean")).reset_index()
        hrs = hrs.set_index("Hour").reindex(range(24)).fillna(0).reset_index()
        hl = ["12 AM" if h == 0 else ("12 PM" if h == 12 else (f"{h} AM" if h < 12 else f"{h - 12} PM")) for h in hrs["Hour"]]
        hrs["Hour Label"] = hl
        
        fig_r = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"], y=hrs["Volume"], name="Volume", fill="tozeroy", line=dict(color="#58a6ff", width=2)), secondary_y=False)
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"], y=hrs["AR"], name="FRT (Avg Response)", mode="lines+markers", line=dict(color="#f0883e", width=3, shape="spline")), secondary_y=True)
        fig_r.update_layout(
            **THEME, 
            height=550, 
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig_r.update_yaxes(title_text="Volume (Tickets)", secondary_y=False)
        fig_r.update_yaxes(title_text="Avg Response Time (min)", secondary_y=True)
        st.plotly_chart(fig_r, use_container_width=True)

        st.divider()
        st.markdown("### 📅 Daily Volume & Schedule Workload Analysis")
        
        st.markdown("""
        <div style="text-align: left; font-size: 1.1rem; margin-bottom: 1rem;">
            <strong>Agent Workload Indicator (Tickets per Agent):</strong><br>
            <span style="display: inline-block; margin-right: 15px;"><span style="display:inline-block; width:14px; height:14px; background-color:#3b82f6; border-radius:3px; vertical-align:middle; margin-right:6px; margin-bottom:2px;"></span>Optimal (≤55)</span>
            <span style="display: inline-block; margin-right: 15px;"><span style="display:inline-block; width:14px; height:14px; background-color:#fbbf24; border-radius:3px; vertical-align:middle; margin-right:6px; margin-bottom:2px;"></span>Moderate (56-60)</span>
            <span style="display: inline-block; margin-right: 15px;"><span style="display:inline-block; width:14px; height:14px; background-color:#f97316; border-radius:3px; vertical-align:middle; margin-right:6px; margin-bottom:2px;"></span>High (61-63)</span>
            <span style="display: inline-block; margin-right: 15px;"><span style="display:inline-block; width:14px; height:14px; background-color:#ef4444; border-radius:3px; vertical-align:middle; margin-right:6px; margin-bottom:2px;"></span>Severe (64-70)</span>
            <span style="display: inline-block;"><span style="display:inline-block; width:14px; height:14px; background-color:#991b1b; border-radius:3px; vertical-align:middle; margin-right:6px; margin-bottom:2px;"></span>Excessive (>70)</span>
        </div>
        """, unsafe_allow_html=True)
        
        df_workload = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
        if esc and not nesc: df_workload = df_workload[df_workload["Is Email"] == True]
        elif nesc and not esc: df_workload = df_workload[df_workload["Is Email"] == False]
        
        dfm_shift = df_workload.copy()
        dfm_shift["Shift Date"] = dfm_shift["Date Only"]
        
        daily_vol = dfm_shift.groupby("Shift Date").agg(
            Total_Tickets=("Request ID", "count")
        ).reset_index()
        
        roster_date_map = {}
        if not df_roster.empty:
            for col in df_roster.columns:
                col_str = str(col).strip()
                clean_col = re.sub(r'(?i)\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', '', col_str).strip()
                match = re.search(r'(\d{1,2}[-/\s]+(?:[A-Za-z]+|\d{1,2})[-/\s]+\d{4}|\d{4}[-/\s]+\d{1,2}[-/\s]+\d{1,2})', clean_col)
                if match:
                    try:
                        col_date = pd.to_datetime(match.group(1), dayfirst=True).date()
                        roster_date_map[col_date] = col
                    except: pass
        
        tracked_ids = [str(v).strip().lower() for v in EXPERT_ID_MAP.values()]
        
        def get_scheduled_agents(target_date):
            if target_date not in roster_date_map or df_roster.empty:
                return -1 
            
            col_name = roster_date_map[target_date]
            working_count = 0
            
            for index, row in df_roster.iterrows():
                row_vals_str = " ".join([str(x).strip().lower() for x in row.values])
                if any(tid in row_vals_str for tid in tracked_ids):
                    cell_val = str(row.get(col_name, "")).strip().lower()
                    if cell_val and cell_val not in EXCLUSION_LIST:
                        working_count += 1
            return working_count
        
        daily_vol["Scheduled_Agents"] = daily_vol["Shift Date"].apply(get_scheduled_agents)
        
        agents_df = dfm_shift[dfm_shift["Assigned By"].isin(OFFICIAL_EXPERTS)]
        active_df = agents_df.groupby("Shift Date").agg(Actual_Agents=("Assigned By", "nunique")).reset_index()
        
        daily_vol = pd.merge(daily_vol, active_df, on="Shift Date", how="left")
        daily_vol["Actual_Agents"] = daily_vol["Actual_Agents"].fillna(0)
        
        daily_vol["Active_Agents"] = np.where(
            daily_vol["Scheduled_Agents"] != -1, 
            daily_vol["Scheduled_Agents"], 
            daily_vol["Actual_Agents"]
        )
        
        daily_vol["Active_Agents"] = daily_vol["Active_Agents"].replace(0, 1)
        daily_vol["Tickets per Agent"] = (daily_vol["Total_Tickets"] / daily_vol["Active_Agents"]).round(1)

        daily_vol["Date DT"] = pd.to_datetime(daily_vol["Shift Date"])
        daily_vol["Day Name"] = daily_vol["Date DT"].dt.day_name()
        
        DAY_COLORS = {
            "Saturday": "#dc2626", # Red
            "Sunday": "#2563eb",   # Blue
            "Monday": "#16a34a",   # Green
            "Tuesday": "#d97706",  # Orange
            "Wednesday": "#9333ea",# Purple
            "Thursday": "#0891b2", # Teal
            "Friday": "#475569"    # Slate
        }
        
        daily_vol["Date Label"] = daily_vol.apply(
            lambda r: f"{r['Date DT'].strftime('%b %d')}<br><span style='color:{DAY_COLORS.get(r['Day Name'], '#0f172a')}'><b>({r['Day Name']})</b></span>", 
            axis=1
        )
        
        conditions = [
            daily_vol["Tickets per Agent"] > 70,
            daily_vol["Tickets per Agent"] > 63,
            daily_vol["Tickets per Agent"] > 60,
            daily_vol["Tickets per Agent"] > 55
        ]
        choices = ["#991b1b", "#ef4444", "#f97316", "#fbbf24"]
        daily_vol["Color"] = np.select(conditions, choices, default="#3b82f6") 
        
        fig_d = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig_d.add_trace(go.Bar(
            x=daily_vol["Date Label"], 
            y=daily_vol["Total_Tickets"], 
            text=daily_vol["Total_Tickets"],
            textposition='auto',
            marker_color=daily_vol["Color"],
            name="Total Tickets",
            showlegend=False,
            hovertemplate="<b>%{x}</b><br>Tickets: %{y}<extra></extra>"
        ), secondary_y=False)
        
        fig_d.add_trace(go.Scatter(
            x=daily_vol["Date Label"],
            y=daily_vol["Tickets per Agent"],
            name="Tickets per Agent (Workload)",
            mode="lines+markers+text",
            text=daily_vol["Tickets per Agent"],
            textposition="top center",
            line=dict(color="#ef4444", width=3, shape="spline"),
            marker=dict(size=8, color="#ef4444"),
            hovertemplate="<b>%{x}</b><br>Tickets/Agent: %{y}<br>Scheduled Agents: %{customdata}<extra></extra>",
            customdata=daily_vol["Active_Agents"]
        ), secondary_y=True)

        fig_d.update_layout(
            **THEME, 
            height=480, 
            xaxis_title="", 
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig_d.update_yaxes(title_text="Total Tickets Count", secondary_y=False)
        fig_d.update_yaxes(title_text="Workload Ratio (Tickets/Agent)", secondary_y=True)
        
        st.plotly_chart(fig_d, use_container_width=True)

        # ══════════════════════════════════════════════════════════════════════════════════
        #  NEW CURVE: HIC Vs TICKET COUNTS (STRICT DATE FILTER ONLY)
        # ══════════════════════════════════════════════════════════════════════════════════
        st.divider()
        st.markdown("### 🏥 Health Insurance Companies (HIC) Distribution Analysis")
        
        df_hic_strict = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
        if esc and not nesc: 
            df_hic_strict = df_hic_strict[df_hic_strict["Is Email"] == True]
        elif nesc and not esc: 
            df_hic_strict = df_hic_strict[df_hic_strict["Is Email"] == False]
            
        if not df_hic_strict.empty:
            hic_counts = df_hic_strict.groupby("HIC").agg(Volume=("Request ID", "count")).reset_index()
            hic_counts = hic_counts.sort_values(by="Volume", ascending=False) 
            
            fig_hic = px.bar(
                hic_counts,
                x="HIC",
                y="Volume",
                text="Volume",
                color="HIC", 
                labels={"Volume": "Tickets Count", "HIC": "Insurance Provider"}
            )
            fig_hic.update_traces(
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Tickets Resolved: %{y:,}<extra></extra>"
            )
            fig_hic.update_layout(
                **THEME,
                height=500,
                xaxis_title="",
                yaxis_title="Total Handled Volume (Tickets)",
                xaxis_tickangle=-45,
                legend_title_text="Insurance Provider"
            )
            st.plotly_chart(fig_hic, use_container_width=True)
        else:
            st.info("No insurance (HIC) records available for this period.")

# ── TAB 2 — Team Performance and KPIs ──────────────────────────────────────────────
with tab2:
    st.markdown("### 👥 Team Performance and KPIs")
    
    sel_agents_t2 = st.multiselect("Filter by Expert Name", sorted(df_raw["Assigned By"].dropna().unique()), key="t2_agents")

    df_t2 = df.copy()
    df_t2_prev = df_prev_all.copy()

    if sel_agents_t2:
        df_t2 = df_t2[df_t2["Assigned By"].isin(sel_agents_t2)]
        df_t2_prev = df_t2_prev[df_t2_prev["Assigned By"].isin(sel_agents_t2)]

    aname = my_agent_name()
    if not is_admin() and aname:
        df_kpi = df_t2[df_t2["Assigned By"] == aname].copy()
        df_kpi_prev = df_t2_prev[df_t2_prev["Assigned By"] == aname].copy()
    else:
        df_kpi = df_t2.copy()
        df_kpi_prev = df_t2_prev.copy()

    # Current KPI Metrics
    total_kpi = len(df_kpi)
    kpi_ss  = df_kpi["Status"].astype(str).str.strip()
    kpi_ok  = df_kpi[kpi_ss.str.contains("Closed", na=False, case=False) & ~kpi_ss.str.contains("issue", na=False, case=False)].shape[0]
    kpi_iss = df_kpi[kpi_ss.str.contains("Closed", na=False, case=False) & kpi_ss.str.contains("issue", na=False, case=False)].shape[0]
    kpi_curr_frt_val = df_kpi["Response Take (min)"].mean() if not df_kpi.empty else 0
    kpi_curr_aht_val = df_kpi["AHT (min)"].mean() if not df_kpi.empty else 0
    kpi_curr_tat_val = df_kpi["Request Take (min)"].mean() if not df_kpi.empty else 0
    
    kpi_curr_merged_aht_val = kpi_curr_frt_val + kpi_curr_aht_val
    h_kpi_merged_aht = fmt_m(kpi_curr_merged_aht_val)
    
    kpi_ok_pct = (kpi_ok / total_kpi * 100) if total_kpi > 0 else 0
    kpi_iss_pct = (kpi_iss / total_kpi * 100) if total_kpi > 0 else 0

    # Previous KPI Metrics
    prev_kpi_total = len(df_kpi_prev)
    kpi_ss_prev = df_kpi_prev["Status"].astype(str).str.strip()
    prev_kpi_ok = df_kpi_prev[kpi_ss_prev.str.contains("Closed", na=False, case=False) & ~kpi_ss_prev.str.contains("issue", na=False, case=False)].shape[0]
    prev_kpi_iss = df_kpi_prev[kpi_ss_prev.str.contains("Closed", na=False, case=False) & kpi_ss_prev.str.contains("issue", na=False, case=False)].shape[0]
    prev_kpi_frt_val = df_kpi_prev["Response Take (min)"].mean() if not df_kpi_prev.empty else 0
    prev_kpi_aht_val = df_kpi_prev["AHT (min)"].mean() if not df_kpi_prev.empty else 0
    prev_kpi_tat_val = df_kpi_prev["Request Take (min)"].mean() if not df_kpi_prev.empty else 0
    
    prev_kpi_merged_aht_val = prev_kpi_frt_val + prev_kpi_aht_val
    
    prev_kpi_ok_pct = (prev_kpi_ok / prev_kpi_total * 100) if prev_kpi_total > 0 else 0
    prev_kpi_iss_pct = (prev_kpi_iss / prev_kpi_total * 100) if prev_kpi_total > 0 else 0

    # KPI Changes
    chg_kpi_total = calc_change(total_kpi, prev_kpi_total)
    chg_kpi_ok = calc_change(kpi_ok_pct, prev_kpi_ok_pct)
    chg_kpi_iss = calc_change(kpi_iss_pct, prev_kpi_iss_pct)
    chg_kpi_merged_aht = calc_change(kpi_curr_merged_aht_val, prev_kpi_merged_aht_val)
    chg_kpi_tat = calc_change(kpi_curr_tat_val, prev_kpi_tat_val)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.markdown(kpi_colored("Total Tickets",      f"{total_kpi:,}", "card-total", chg_kpi_total, neutral=True),     unsafe_allow_html=True)
    k2.markdown(kpi_colored("Closed Completed",   f"{kpi_ok:,} <span style='font-size:1rem; opacity:0.8'>({kpi_ok_pct:.1f}%)</span>",      "card-completed", chg_kpi_ok), unsafe_allow_html=True)
    k3.markdown(kpi_colored("Closed with Issue",  f"{kpi_iss:,} <span style='font-size:1rem; opacity:0.8'>({kpi_iss_pct:.1f}%)</span>",     "card-issue", chg_kpi_iss, inverse=True),     unsafe_allow_html=True)
    k4.markdown(kpi_colored("AHT (Average Handling Time)", h_kpi_merged_aht, "card-aht", chg_kpi_merged_aht, inverse=True), unsafe_allow_html=True)
    k5.markdown(kpi_colored("Avg Service (TAT)",  fmt_m(kpi_curr_tat_val), "card-tat", chg_kpi_tat, inverse=True), unsafe_allow_html=True)

    st.write(""); st.divider()
    
    period_ovs = overrides().get(PERIOD_KEY, {})
    global_target = float(period_ovs.get("GLOBAL_TARGET", 0))

    if is_admin():
        col_t1, col_t2 = st.columns([1, 3])
        with col_t1:
            st.markdown(f"#### 🎯 Set Daily Target")
            with st.form("global_target_form"):
                new_target = st.number_input("Daily Target (Cases/Day)", value=int(global_target), step=1, min_value=0)
                if st.form_submit_button("💾 Save Global Target", use_container_width=True):
                    if PERIOD_KEY not in overrides(): overrides()[PERIOD_KEY] = {}
                    overrides()[PERIOD_KEY]["GLOBAL_TARGET"] = new_target
                    _save_store()
                    st.success("✅ Target saved successfully!")
                    st.rerun()

    OFFICIAL_EXPERTS_LOWER = [x.lower() for x in OFFICIAL_EXPERTS]
    df_sc = df_t2[df_t2["Assigned By"].astype(str).str.strip().str.lower().isin(OFFICIAL_EXPERTS_LOWER)].copy()

    sc = pd.DataFrame({"Expert": OFFICIAL_EXPERTS})
    
    if not df_sc.empty:
        expert_map = {x.lower(): x for x in OFFICIAL_EXPERTS}
        df_sc["Assigned By"] = df_sc["Assigned By"].astype(str).str.strip().str.lower().map(expert_map)
        
        rtl = df_sc["Request Type"].astype(str).str.lower()
        df_sc["_jhah"]  = rtl.str.contains("jhah", na=False)
        df_sc["_rfb"]   = rtl.str.contains("report|feedback", na=False)
        df_sc["_c_ok"]  = (df_sc["Status"].astype(str).str.contains("Closed", case=False, na=False) & ~df_sc["Status"].astype(str).str.contains("issue", case=False, na=False))
        df_sc["_c_all"] = df_sc["Status"].astype(str).str.contains("Closed", case=False, na=False)

        grp = df_sc.groupby("Assigned By")
        stats = pd.DataFrame(index=grp.groups.keys())
        stats["Tickets Count"]        = grp["Request ID"].count()
        stats["JHAH Requests"]        = grp["_jhah"].sum().astype(int)
        stats["Reporting & Feedback"] = grp["_rfb"].sum().astype(int)
        stats["Email Counts"]         = grp["Is Email"].sum().astype(int)
        stats["_Service_Time_val"]    = grp["Request Take (min)"].mean()
        stats["_FRT_val"]             = grp["Response Take (min)"].mean()
        stats["_AHT_val"]             = grp["AHT (min)"].mean()
        stats["_c_ok_sum"]            = grp["_c_ok"].sum()
        stats["_c_all_sum"]           = grp["_c_all"].sum()
        
        sc = sc.merge(stats, left_on="Expert", right_index=True, how="left")
    else:
        sc["Tickets Count"] = 0
        sc["JHAH Requests"] = 0
        sc["Reporting & Feedback"] = 0
        sc["Email Counts"] = 0
        sc["_Service_Time_val"] = 0
        sc["_FRT_val"] = 0
        sc["_AHT_val"] = 0
        sc["_c_ok_sum"] = 0
        sc["_c_all_sum"] = 0

    sc["Tickets Count"] = sc["Tickets Count"].fillna(0).astype(int)
    sc["JHAH Requests"] = sc["JHAH Requests"].fillna(0).astype(int)
    sc["Reporting & Feedback"] = sc["Reporting & Feedback"].fillna(0).astype(int)
    sc["Email Counts"] = sc["Email Counts"].fillna(0).astype(int)
    sc["Out Requests"] = 0  
    
    roster_counts = {}
    if not df_roster.empty:
        valid_roster_cols = []
        for col in df_roster.columns:
            col_str = str(col).strip()
            clean_col = re.sub(r'(?i)\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', '', col_str).strip()
            match = re.search(r'(\d{1,2}[-/\s]+(?:[A-Za-z]+|\d{1,2})[-/\s]+\d{4}|\d{4}[-/\s]+\d{1,2}[-/\s]+\d{1,2})', clean_col)
            if match:
                try:
                    col_date = pd.to_datetime(match.group(1), dayfirst=True).date()
                    if d_from <= col_date <= d_to:
                        valid_roster_cols.append(col)
                except: pass
        
        df_r_str = df_roster.astype(str)
        
        for exp in OFFICIAL_EXPERTS:
            exp_id = EXPERT_ID_MAP.get(exp, "")
            off_c, ann_c, cas_c, sick_c, wd_c = 0, 0, 0, 0, 0
            
            if exp_id:
                mask = df_r_str.apply(lambda row: str(exp_id).strip().lower() in [str(x).strip().lower() for x in row.values], axis=1)
                exp_rows = df_r_str[mask]
                
                if not exp_rows.empty and valid_roster_cols:
                    safe_cols = [c for c in valid_roster_cols if c in exp_rows.columns]
                    if safe_cols:
                        vals = exp_rows[safe_cols].values.flatten()
                        vals_lower = [str(v).strip().lower() for v in vals]
                        
                        off_c = sum(1 for v in vals_lower if v in ['off', 'اوف', 'أوف', 'راحة'])
                        ann_c = sum(1 for v in vals_lower if v in ['annual', 'v', 'a', 'vacation'])
                        max_cas = sum(1 for v in vals_lower if v in ['casual', 'عارضة', 'عارضه'])
                        sick_c = sum(1 for v in vals_lower if v in ['sick', 'مرضي', 'مرضى'])
                        wd_c  = sum(1 for v in vals_lower if v and v not in EXCLUSION_LIST)
                
            roster_counts[exp] = {
                "Working Days": wd_c,
                "Off Days": off_c,
                "Annual Leaves": ann_c,
                "Casual Leaves": max_cas,
                "Sick Leaves": sick_c
            }

    sc["Working Days"] = sc["Expert"].apply(lambda x: roster_counts.get(x, {}).get("Working Days", 0))
    sc["Off Days"] = sc["Expert"].apply(lambda x: roster_counts.get(x, {}).get("Off Days", 0))
    sc["Annual Leaves"] = sc["Expert"].apply(lambda x: roster_counts.get(x, {}).get("Annual Leaves", 0))
    sc["Casual Leaves"] = sc["Expert"].apply(lambda x: roster_counts.get(x, {}).get("Casual Leaves", 0))
    sc["Sick Leaves"] = sc["Expert"].apply(lambda x: roster_counts.get(x, {}).get("Sick Leaves", 0))

    for i, row in sc.iterrows():
        ov = period_ovs.get(row["Expert"], {})
        for col, val in ov.items(): 
            if col != "GLOBAL_TARGET":
                sc.at[i, col] = val

    # ── ROSTER KPI CARDS FOR THE CURRENT VIEW ──
    st.markdown("### 📅 Schedule & Leaves Summary")
    if not is_admin() and aname in sc["Expert"].values:
        kpi_r_df = sc[sc["Expert"] == aname]
    else:
        kpi_r_df = sc
        if sel_agents_t2:
            kpi_r_df = sc[sc["Expert"].isin([x for x in OFFICIAL_EXPERTS if x in sel_agents_t2])]

    sum_wd   = int(kpi_r_df["Working Days"].astype(float).sum())
    sum_off  = int(kpi_r_df["Off Days"].astype(float).sum())
    sum_ann  = int(kpi_r_df["Annual Leaves"].astype(float).sum())
    sum_cas  = int(kpi_r_df["Casual Leaves"].astype(float).sum())
    sum_sick = int(kpi_r_df["Sick Leaves"].astype(float).sum())

    rk1, rk2, rk3, rk4, rk5 = st.columns(5)
    rk1.markdown(kpi_colored("Working Days (Shifts)", f"{sum_wd}", "card-store"), unsafe_allow_html=True)
    rk2.markdown(kpi_colored("Off Days", f"{sum_off}", "card-actions"), unsafe_allow_html=True)
    rk3.markdown(kpi_colored("Annual Leaves", f"{sum_ann}", "card-completed"), unsafe_allow_html=True)
    rk4.markdown(kpi_colored("Casual Leaves", f"{sum_cas}", "card-issue"), unsafe_allow_html=True)
    rk5.markdown(kpi_colored("Sick Leaves", f"{sum_sick}", "card-frt"), unsafe_allow_html=True)
    st.write("")
    
    st.markdown("### 📊 Expert Performance Scorecard Dashboard")

    total_cases = sc["Tickets Count"].astype(float) + sc["JHAH Requests"].astype(float) + sc["Out Requests"].astype(float)
    wdays = sc["Working Days"].astype(float).replace(0, 1)
    sc["Cases/Day"] = (total_cases / wdays).round(1)

    if not sc.empty:
        sc.insert(1, "Rank", sc["Cases/Day"].rank(method="min", ascending=False).astype(int).astype(str))
    else:
        sc["Rank"] = []

    if global_target > 0:
        sc["% Achievement from Target"] = ((sc["Cases/Day"] / global_target) * 100).round(1).astype(str) + "%"
    else:
        tavg_cpd = sc["Cases/Day"].mean()
        sc["% Achievement from Target"] = ((sc["Cases/Day"] / tavg_cpd * 100).round(1).astype(str) + "%" if tavg_cpd > 0 else "0.0%")

    sc["FRT"] = sc["_FRT_val"].fillna(0).apply(fmt_m)
    sc["Service Time"] = sc["_Service_Time_val"].fillna(0).apply(fmt_m)
    
    c_all = sc["_c_all_sum"].fillna(0).replace(0, 1)
    c_ok = sc["_c_ok_sum"].fillna(0)
    sc["Service Quality"] = (c_ok / c_all * 100).round(1).astype(str) + "%"

    team_wd = round(sc["Working Days"].mean(), 1) if not sc.empty else 0
    team_tc = round(sc["Tickets Count"].mean(), 1) if not sc.empty else 0
    team_jhah = round(sc["JHAH Requests"].mean(), 1) if not sc.empty else 0
    team_out = round(sc["Out Requests"].mean(), 1) if not sc.empty else 0
    team_cpd = round((team_tc + team_jhah + team_out) / (team_wd if team_wd > 0 else 1), 1)

    team_st = fmt_m(df_sc["Request Take (min)"].mean() if not df_sc.empty else 0)
    team_merged_aht = fmt_m(df_sc["Response Take (min)"].mean() + df_sc["AHT (min)"].mean() if not df_sc.empty else 0)

    if global_target > 0:
        team_achiev = f"{round((team_cpd / global_target) * 100, 1)}%"
    else:
        team_achiev = "100.0%"

    team_row = {
        "Expert": "🏆 Team AVG", 
        "Rank": "-",
        "Working Days": team_wd, 
        "Tickets Count": team_tc,
        "JHAH Requests": team_jhah, 
        "Out Requests": team_out,
        "Cases/Day": team_cpd,
        "Reporting & Feedback": round(sc["Reporting & Feedback"].mean(), 1) if not sc.empty else 0,
        "Email Counts": round(sc["Email Counts"].mean(), 1) if not sc.empty else 0,
        "Off Days": round(sc["Off Days"].mean(), 1) if not sc.empty else 0,
        "Annual Leaves": round(sc["Annual Leaves"].mean(), 1) if not sc.empty else 0,
        "Casual Leaves": round(sc["Casual Leaves"].mean(), 1) if not sc.empty else 0,
        "Sick Leaves": round(sc["Sick Leaves"].mean(), 1) if not sc.empty else 0,
        "% Achievement from Target": team_achiev, 
        "AHT": team_merged_aht,
        "Service Time": team_st, 
        "Service Quality": "100.0%"
    }
    
    team_ov = period_ovs.get("🏆 Team AVG", {})
    for col, val in team_ov.items():
        if col != "GLOBAL_TARGET":
            team_row[col] = val

    sc.drop(columns=["_Service_Time_val", "_FRT_val", "_AHT_val", "_c_ok_sum", "_c_all_sum"], inplace=True, errors='ignore')

    sc_final = pd.concat([pd.DataFrame([team_row]), sc], ignore_index=True) if is_admin() else pd.concat([pd.DataFrame([team_row]), sc[sc["Expert"] == aname]], ignore_index=True)

    def format_clean_num(x):
        if x == "-": return "-"
        try:
            f = float(x)
            if f.is_integer():
                return str(int(f))
            return str(round(f, 1))
        except:
            return str(x)

    cols_clean = ["Working Days", "Tickets Count", "JHAH Requests", "Out Requests", "Cases/Day", "Reporting & Feedback", "Email Counts", "Off Days", "Annual Leaves", "Casual Leaves", "Sick Leaves"]
    for c in cols_clean:
        if c in sc_final.columns:
            sc_final[c] = sc_final[c].apply(format_clean_num)

    rank_df = sc.copy()
    rank_df["_sort_val"] = pd.to_numeric(rank_df["Cases/Day"], errors="coerce").fillna(0)
    top_experts = rank_df.nlargest(3, "_sort_val")["Expert"].tolist()
    
    gold_exp   = top_experts[0] if len(top_experts) > 0 else None
    silver_exp = top_experts[1] if len(top_experts) > 1 else None
    bronze_exp = top_experts[2] if len(top_experts) > 2 else None

    display_df = sc_final.copy()
    
    gold_disp   = f"🥇 {gold_exp}" if gold_exp else None
    silver_disp = f"🥈 {silver_exp}" if silver_exp else None
    bronze_disp = f"🥉 {bronze_exp}" if bronze_exp else None

    def add_medals_row(val):
        if val == gold_exp: return gold_disp
        if val == silver_exp: return silver_disp
        if val == bronze_exp: return bronze_disp
        return val
        
    display_df["Expert"] = display_df["Expert"].apply(add_medals_row)

    def style_performers(row):
        exp = row["Expert"]
        if exp == "🏆 Team AVG":
            return ['background-color: #cbd5e1; font-weight: 800; color: #0f172a'] * len(row)
        elif exp == gold_disp:
            return ['background-color: #fef08a; color: #854d0e; font-weight: 800'] * len(row)
        elif exp == silver_disp:
            return ['background-color: #e2e8f0; color: #334155; font-weight: 800'] * len(row)
        elif exp == bronze_disp:
            return ['background-color: #ffedd5; color: #9a3412; font-weight: 800'] * len(row)
        elif exp == aname and not is_admin():
            return ['background-color: #dbeafe; color: #1e40af; font-weight: 800'] * len(row)
        return [''] * len(row)

    column_order = ["Expert", "Rank", "Tickets Count", "JHAH Requests", "Out Requests", "Cases/Day", "Reporting & Feedback", "Email Counts", "% Achievement from Target", "AHT", "Service Time", "Service Quality"]
    display_df = display_df[column_order]

    styled_df = display_df.style.apply(style_performers, axis=1)
    styled_df = styled_df.set_properties(**{'text-align': 'center'})
    styled_df = styled_df.set_properties(subset=['Expert'], **{'font-weight': '900', 'color': '#0f172a'})

    html_table = styled_df.hide(axis="index").to_html()
    st.markdown(f'<div class="scorecard-container">{html_table}</div>', unsafe_allow_html=True)

    if is_admin():
        st.divider()
        st.markdown(f"#### ✏️ Manual KPI Override Editor (Period: {d_from} to {d_to})")
        st.info("💡 **ملاحظة هامة:** اترك الحقل فارغاً (Empty) ليتم حسابه تلقائياً بمرونة. اكتب رقماً فقط في الحقل الذي تريد تثبيته لهذه الفترة الزمنية المحددة.")
        
        agent_opts = list(sc["Expert"]) + ["🏆 Team AVG"]
        sel_agent  = st.selectbox("Choose agent to edit", agent_opts, key="agent_ov_sel")
        
        cur = period_ovs.get(sel_agent, {})
        def gv(k):
            return str(cur.get(k, ""))

        with st.form(f"ov_form_{sel_agent}"):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                nout = st.text_input("Out Requests", value=gv("Out Requests"))
                njh  = st.text_input("JHAH Requests", value=gv("JHAH Requests"))
            with fc2:
                nrfb = st.text_input("Reporting & Feedback", value=gv("Reporting & Feedback"))
                nem  = st.text_input("Email Counts", value=gv("Email Counts"))
            with fc3:
                naht = st.text_input("AHT (HH:MM:SS)", value=gv("AHT"))
                nsq  = st.text_input("Service Quality (%)", value=gv("Service Quality"))
            
            sc_col, rc_col = st.columns(2)
            with sc_col: do_save  = st.form_submit_button("💾 Save Override", use_container_width=True)
            with rc_col: do_clear = st.form_submit_button("🔄 Clear Override", use_container_width=True)

        if do_save:
            new_ov = {}
            def parse_int(v):
                try: return int(float(v))
                except: return None
            def parse_str(v):
                return str(v).strip() if str(v).strip() else None

            if parse_int(nout) is not None: new_ov["Out Requests"] = parse_int(nout)
            if parse_int(njh) is not None: new_ov["JHAH Requests"] = parse_int(njh)
            if parse_int(nrfb) is not None: new_ov["Reporting & Feedback"] = parse_int(nrfb)
            if parse_int(nem) is not None: new_ov["Email Counts"] = parse_int(nem)
            if parse_str(naht): new_ov["AHT"] = parse_str(naht)
            if parse_str(nsq): new_ov["Service Quality"] = parse_str(nsq)

            if PERIOD_KEY not in overrides(): overrides()[PERIOD_KEY] = {}
            
            if new_ov:
                overrides()[PERIOD_KEY][sel_agent] = new_ov
            else:
                if sel_agent in overrides().get(PERIOD_KEY, {}):
                    overrides()[PERIOD_KEY].pop(sel_agent)
                    
            _save_store()
            st.success(f"✅ Override parameters saved specifically for period **{d_from} to {d_to}**.")
            st.rerun()

        if do_clear:
            if PERIOD_KEY in overrides() and sel_agent in overrides()[PERIOD_KEY]:
                overrides()[PERIOD_KEY].pop(sel_agent)
                _save_store()
                st.success(f"🔄 Cleared overrides for period **{d_from} to {d_to}**.")
                st.rerun()
            else:
                st.warning("No active overrides found to clear for this period.")

        active_ovs = overrides().get(PERIOD_KEY, {})
        disp_ovs = {k: v for k, v in active_ovs.items() if k != "GLOBAL_TARGET"}
        if disp_ovs:
            st.write("")
            with st.expander("🗂️ Active Metric Overrides (This Period)"):
                st.json(disp_ovs)
        
        st.divider()
        st.markdown("#### ✉️ Performance Review Emails")
        
        email_agents_list = [x for x in sc_final["Expert"] if "🏆 Team AVG" not in x]
        selected_email_agent = st.selectbox("Select Agent for Email Draft", email_agents_list)
        
        if selected_email_agent:
            agent_row = sc_final[sc_final["Expert"] == selected_email_agent].iloc[0]
            team_row_disp = sc_final[sc_final["Expert"] == "🏆 Team AVG"].iloc[0]
            
            def safe_float(v):
                try: return float(str(v).replace('%','').replace(',',''))
                except: return 0.0
            
            achiev_val = safe_float(agent_row["% Achievement from Target"])
            qual_val = safe_float(agent_row["Service Quality"])
            
            agent_total_cases = safe_float(agent_row['Tickets Count']) + safe_float(agent_row['JHAH Requests']) + safe_float(agent_row['Out Requests'])
            team_total_cases = safe_float(team_row_disp['Tickets Count']) + safe_float(team_row_disp['JHAH Requests']) + safe_float(team_row_disp['Out Requests'])
            
            if achiev_val >= 100:
                perf_word = "outstanding"
                target_msg = f"You successfully exceeded the daily target with a brilliant **{agent_row['% Achievement from Target']}** achievement rate!"
            elif achiev_val >= 80:
                perf_word = "solid"
                target_msg = f"You reached a solid **{agent_row['% Achievement from Target']}** of the daily target. Great effort, let's push for 100%!"
            else:
                perf_word = "developing"
                target_msg = f"You achieved **{agent_row['% Achievement from Target']}** of the daily target. We believe in your potential and are here to support you in hitting higher milestones."
            
            if qual_val >= 95:
                qual_msg = f"Your service quality is top-tier at **{agent_row['Service Quality']}**. Keep up the flawless work!"
            elif qual_val >= 85:
                qual_msg = f"Your service quality is strong at **{agent_row['Service Quality']}**."
            else:
                qual_msg = f"Your service quality sits at **{agent_row['Service Quality']}**. Let's focus on accuracy and quality in the upcoming period."
            
            clean_name = selected_email_agent.replace("🥇 ", "").replace("🥈 ", "").replace("🥉 ", "")
            
            markdown_email = f"""
Dear **{clean_name}**,

I hope this email finds you well. 

As we review the performance for the period from **{d_from}** to **{d_to}**, I wanted to personally share your metrics and highlight your **{perf_word}** contributions to the team.

### 📊 Your Performance Scorecard:

| Metric | Total Cases | Cases/Day | Achievement | Quality | AHT | Service Time |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Your Score** | **{int(agent_total_cases)}** | **{agent_row['Cases/Day']}** | **{agent_row['% Achievement from Target']}** | **{agent_row['Service Quality']}** | **{agent_row['AHT']}** | **{agent_row['Service Time']}** |
| **Team Average** | {team_total_cases} | {team_row_disp['Cases/Day']} | {team_row_disp['% Achievement from Target']} | {team_row_disp['Service Quality']} | {team_row_disp['AHT']} | {team_row_disp['Service Time']} |

**🎯 Targets & Quality:** {target_msg}  
{qual_msg}

Thank you for your hard work and dedication to our success. Should you need any support or wish to discuss your metrics further, my door is always open.

Best regards,  
**Mohammed Shehta** Team Leader
"""
            
            st.markdown("##### 📝 Email Preview (Highlight & Copy directly from here!)")
            st.info("💡 **تلميح:** قم بتظليل الإيميل والجدول الموجود بالأسفل بالماوس وانسخه (Copy) ثم قم بلصقه (Paste) مباشرة في (Gmail) ليحتفظ بتنسيقه الرائع.")
            
            st.markdown(f"<div style='background:#ffffff; padding:2rem; border-radius:12px; border:2px solid #cbd5e1; font-size:1.1rem; color:#1e293b;'>\n\n{markdown_email}\n\n</div>", unsafe_allow_html=True)
            
            email_body_plain = f"""Dear {clean_name},

I hope this email finds you well. 

As we review the performance for the period from {d_from} to {d_to}, I wanted to personally share your metrics and highlight your {perf_word} contributions to the team.

📊 Your Performance Scorecard:
------------------------------------------------------------------------------------------
Metric         | Total Cases | Cases/Day | Achievement | Quality | AHT      | Service Time
------------------------------------------------------------------------------------------
Your Score     | {str(int(agent_total_cases)):<11} | {str(agent_row['Cases/Day']):<9} | {str(agent_row['% Achievement from Target']):<11} | {str(agent_row['Service Quality']):<7} | {str(agent_row['AHT']):<8} | {str(agent_row['Service Time'])}
Team Average   | {str(team_total_cases):<11} | {str(team_row_disp['Cases/Day']):<9} | {str(team_row_disp['% Achievement from Target']):<11} | {str(team_row_disp['Service Quality']):<7} | {str(team_row_disp['AHT']):<8} | {str(team_row_disp['Service Time'])}
------------------------------------------------------------------------------------------

🎯 Targets & Quality:
{target_msg.replace('**', '')}
{qual_msg.replace('**', '')}

Thank you for your hard work and dedication to our success. Should you need any support or wish to discuss your metrics further, my door is always open.

Best regards,
Mohammed Shehta
Team Leader"""

            with st.expander("Show Plain Text Version (For manual copy/paste)"):
                st.text_area("Plain Text Draft", value=email_body_plain, height=300)
            
            subject_encoded = urllib.parse.quote(f"Your Performance Review ({d_from} to {d_to}) - {clean_name}")
            body_encoded = urllib.parse.quote(email_body_plain)
            
            st.write("")
            gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&to=&su={subject_encoded}&body={body_encoded}"
            st.markdown(
                f'<a href="{gmail_link}" target="_blank" style="display:block; padding:0.8rem 1.2rem; background-color:#ea4335; color:white; text-decoration:none; border-radius:8px; font-weight:900; font-size:1.15rem; width:100%; text-align:center; margin-top: 10px; box-shadow: 0 4px 6px rgba(234, 67, 53, 0.3);">'
                f'🌐 Open Draft in Gmail</a>', 
                unsafe_allow_html=True
            )

st.info(f"⏱️ Operational Sync Status: Metrics loaded completely across {len(df)} synced records.")
# --- END OF SCRIPT ---
