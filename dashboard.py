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
    font-size: .8rem !important; 
    letter-spacing: .12em; 
    text-transform: uppercase;
    margin-bottom: .5rem; 
    font-weight: 800 !important; 
    color: #334155 !important;
}
.kpi-value { 
    font-size: 2.05rem !important; 
    font-weight: 900 !important; 
    letter-spacing: -.02em; 
}

.card-total     { background: #e0f2fe; border: 2px solid #7dd3fc; color: #0369a1; }
.card-completed { background: #dcfce7; border: 2px solid #86efac; color: #166534; }
.card-issue     { background: #fee2e2; border: 2px solid #fca5a5; color: #991b1b; }
.card-frt       { background: #fce7f3; border: 2px solid #f9a8d4; color: #9d174d; }
.card-aht       { background: #f3e8ff; border: 2px solid #d8b4fe; color: #6b21a8; }
.card-tat       { background: #ecfeff; border: 2px solid #67e8f9; color: #155e75; }

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

/* Dataframe Row Typography Overrides */
div[data-testid="stDataFrame"] table {
    font-size: 1.05rem !important;
}
div[data-testid="stDataFrame"] th {
    font-weight: 900 !important;
    background-color: #f1f5f9 !important;
    color: #0f172a !important;
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
    st.markdown("## 💊 Navigation & Filters")

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
                st.error("❌ Secrets file layout unconfigured."); return pd.DataFrame()
            client = gspread.authorize(creds)
            sheet = client.open("AlDawaa Tickets Data")
            all_dfs = []
            for ws in sheet.worksheets():
                data = ws.get_all_values()
                if len(data) < 2: continue
                dft = pd.DataFrame(data[1:], columns=[str(c).strip() for c in data[0]])
                mp = {}; seen = set()
                for col in dft.columns:
                    cl = col.lower(); t = None
                    if   "id"       in cl and "req"    in cl: t = "Request ID"
                    elif "date"     in cl:                     t = "Request Date"
                    elif "type"     in cl:                     t = "Request Type"
                    elif "status"   in cl:                     t = "Status"
                    elif "assigned" in cl or "agent"   in cl: t = "Assigned By"
                    elif "response" in cl and "take"   in cl: t = "Response Take"
                    elif "action"   in cl and "take"   in cl: t = "First Action Take"
                    elif "request"  in cl and "take"   in cl: t = "Request Take"
                    elif "email"    in cl or "special" in cl: t = "Is Special Request(By Email)"
                    if t and t not in seen: mp[col] = t; seen.add(t)
                dft.rename(columns=mp, inplace=True)
                all_dfs.append(dft)
            if not all_dfs: return pd.DataFrame()
            df = pd.concat(all_dfs, ignore_index=True, sort=False)
            df.replace("", np.nan, inplace=True)
            for c in ["Request ID", "Request Date", "Request Type", "Status",
                      "Request Take", "Response Take", "First Action Take",
                      "Assigned By", "Is Special Request(By Email)"]:
                if c not in df.columns: df[c] = np.nan
            df["Status"]       = df["Status"].fillna("Unknown")
            df["Assigned By"]  = df["Assigned By"].fillna("Unassigned")
            df["Request Type"] = df["Request Type"].fillna("Unknown Type")
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
            return df
        except Exception as e:
            st.error(f"❌ Connection Error: {e}"); return pd.DataFrame()

    df_raw = load_data()
    if df_raw.empty:
        st.warning("Empty source records."); st.stop()

    st.divider()
    min_d = df_raw["Date Only"].dropna().min()
    max_d = df_raw["Date Only"].dropna().max()
    date_range = st.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    d_from, d_to = (
        date_range if isinstance(date_range, (list, tuple)) and len(date_range) == 2 else (min_d, max_d)
    )
    if d_from == d_to:
        st.caption(f"📅 {DAYS_AR.get(pd.to_datetime(d_from).day_name(), '')}")
    st.divider()
    sel_agents = st.multiselect("Agent Filter", sorted(df_raw["Assigned By"].dropna().unique()))
    sel_types  = st.multiselect("Request Type Filter", sorted(df_raw["Request Type"].dropna().unique()))

df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_agents: df = df[df["Assigned By"].isin(sel_agents)]
if sel_types:  df = df[df["Request Type"].isin(sel_types)]

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
            for uname, urow in list(users().items()):
                role_icon = "🔑" if urow["role"] == "admin" else "👤"
                with st.expander(f"{role_icon} {urow['display_name']} (@{uname})"):
                    with st.form(f"admin_edit_{uname}"):
                        eu_dn   = st.text_input("Display Username", value=urow["display_name"], key=f"dn_{uname}")
                        eu_an   = st.text_input("Agent Key Mapping (Sheets)", value=urow.get("agent_name") or "", key=f"an_{uname}")
                        eu_p1   = st.text_input("Override Password", type="password", key=f"p1_{uname}")
                        eu_p2   = st.text_input("Confirm Password", type="password", key=f"p2_{uname}")
                        eu_role = st.selectbox("Role", ["expert","admin"], index=0 if urow["role"] != "admin" else 1, key=f"rl_{
