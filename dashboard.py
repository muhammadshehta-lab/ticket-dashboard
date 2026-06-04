import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json, hashlib, time, pathlib, urllib.parse

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

/* Dataframe Row Typography Overrides - Making Headers Exta Bold */
div[data-testid="stDataFrame"] table {
    font-size: 1.05rem !important;
}
div[data-testid="stDataFrame"] th {
    font-weight: 900 !important;
    background-color: #f1f5f9 !important;
    color: #0f172a !important;
    font-size: 1.05rem !important;
    border-bottom: 2px solid #cbd5e1 !important;
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
                    elif "hic"      in cl or "insurance" in cl: t = "HIC"
                    if t and t not in seen: mp[col] = t; seen.add(t)
                dft.rename(columns=mp, inplace=True)
                all_dfs.append(dft)
            if not all_dfs: return pd.DataFrame()
            df = pd.concat(all_dfs, ignore_index=True, sort=False)
            df.replace("", np.nan, inplace=True)
            for c in ["Request ID", "Request Date", "Request Type", "Status",
                      "Request Take", "Response Take", "First Action Take",
                      "Assigned By", "Is Special Request(By Email)", "HIC"]:
                if c not in df.columns: df[c] = np.nan
            
            df["Status"]       = df["Status"].fillna("Unknown")
            df["Assigned By"]  = df["Assigned By"].fillna("Unassigned")
            df["Request Type"] = df["Request Type"].fillna("Unknown Type")
            df["HIC"]          = df["HIC"].fillna("Unknown")
            
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
    sel_hic    = st.multiselect("HIC (Insurance) Filter", sorted(df_raw["HIC"].dropna().unique()))

df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_agents: df = df[df["Assigned By"].isin(sel_agents)]
if sel_types:  df = df[df["Request Type"].isin(sel_types)]
if sel_hic:    df = df[df["HIC"].isin(sel_hic)]

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
            cur_pw  = st.text_input("Verify Current Password", type="password")
            new_p1  = st.text_input("Set New Secret Password", type="password")
            new_p2  = st.text_input("Confirm New Secret Password", type="password")
            if st.form_submit_button("💾 Save Changes", use_container_width=True):
                if _hash(cur_pw) == urow["password_hash"] and new_p1 == new_p2 and len(new_p1) >= 6:
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
tab1, tab2 = st.tabs(["📈 Tab 1: Operational Insights", "👥 Tab 2: Team Performance and KPIs"])

# ── TAB 1 — Operational Insights ──────────────────────────────────────────────────
with tab1:
    c1, c2 = st.columns(2)
    with c1: esc  = st.checkbox("🔥 Filter: Escalated Cases Only",    value=False, key="t1_esc")
    with c2: nesc = st.checkbox("🟢 Filter: Non-Escalated Cases Only", value=False, key="t1_nesc")

    dfm = df.copy()
    if esc  and not nesc: dfm = dfm[dfm["Is Email"] == True]
    elif nesc and not esc: dfm = dfm[dfm["Is Email"] == False]

    total = len(dfm)
    ss    = dfm["Status"].astype(str).str.strip()
    ok    = dfm[ss.str.contains("Closed", na=False, case=False) & ~ss.str.contains("issue", na=False, case=False)].shape[0]
    issue = dfm[ss.str.contains("Closed", na=False, case=False) & ss.str.contains("issue", na=False, case=False)].shape[0]
    h_frt = fmt_m(dfm["Response Take (min)"].mean() if not dfm.empty else 0)
    h_aht = fmt_m(dfm["AHT (min)"].mean()           if not dfm.empty else 0)
    h_tat = fmt_m(dfm["Request Take (min)"].mean()   if not dfm.empty else 0)

    ok_pct = (ok / total * 100) if total > 0 else 0
    issue_pct = (issue / total * 100) if total > 0 else 0

    a, b, c_, d, e, f_ = st.columns(6)
    a.markdown(kpi_colored("Total Tickets",      f"{total:,}", "card-total"),     unsafe_allow_html=True)
    b.markdown(kpi_colored("Closed Completed",   f"{ok:,} <span style='font-size:1rem; opacity:0.8'>({ok_pct:.1f}%)</span>",    "card-completed"), unsafe_allow_html=True)
    c_.markdown(kpi_colored("Closed with Issue", f"{issue:,} <span style='font-size:1rem; opacity:0.8'>({issue_pct:.1f}%)</span>", "card-issue"),     unsafe_allow_html=True)
    d.markdown(kpi_colored("Avg Response (FRT)", h_frt,        "card-frt"),       unsafe_allow_html=True)
    e.markdown(kpi_colored("Avg Handling (AHT)", h_aht,        "card-aht"),       unsafe_allow_html=True)
    f_.markdown(kpi_colored("Avg Service (TAT)", h_tat,        "card-tat"),       unsafe_allow_html=True)
    st.write("")

    if not dfm.empty:
        dfm["Response Tier"] = dfm["Response Take (min)"].apply(assign_time_tier)
        dfm["Service Tier"]  = dfm["Request Take (min)"].apply(assign_time_tier)
        rd = dfm.groupby("Response Tier").size().reset_index(name="Tickets")
        rd["SLA Category"] = "Response Time"
        rd.rename(columns={"Response Tier": "SLA Tier"}, inplace=True)
        sd = dfm.groupby("Service Tier").size().reset_index(name="Tickets")
        sd["SLA Category"] = "Service Resolution"
        sd.rename(columns={"Service Tier": "SLA Tier"}, inplace=True)
        sb_df = pd.concat([rd, sd], ignore_index=True)
        
        fig_sb = px.sunburst(sb_df, path=["SLA Category", "SLA Tier"], values="Tickets", color="SLA Tier",
            color_discrete_map={"Under 15 Mins": "#2ea44f", "15-30 Mins": "#2188ff", "30-45 Mins": "#bc8cff", "45-60 Mins": "#f9c513", "Over 1 Hour": "#ea4a5a"}, branchvalues="total")
        
        fig_sb.update_traces(
            textinfo="label+value+percent parent",
            hovertemplate="<b>%{label}</b><br>Tickets Count: %{value:,}<br>Percentage: %{percentParent:.1%}"
        )
        fig_sb.update_layout(**THEME, height=520)
        st.plotly_chart(fig_sb, use_container_width=True)

    st.divider()

    if not dfm.empty:
        st.markdown("### ⏳ Ticket flow rate over daily hours")
        hrs = dfm.groupby("Hour").agg(Volume=("Request ID", "count"), AR=("Response Take (min)" , "mean")).reset_index()
        hrs = hrs.set_index("Hour").reindex(range(24)).fillna(0).reset_index()
        hl = ["12 AM" if h == 0 else ("12 PM" if h == 12 else (f"{h} AM" if h < 12 else f"{h - 12} PM")) for h in hrs["Hour"]]
        hrs["Hour Label"] = hl
        fig_r = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"], y=hrs["Volume"], name="Volume", fill="tozeroy", line=dict(color="#58a6ff", width=2)), secondary_y=False)
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"], y=hrs["AR"], name="FRT (Avg Response)", mode="lines+markers", line=dict(color="#f0883e", width=3, shape="spline")), secondary_y=True)
        fig_r.update_layout(**THEME, height=450, hovermode="x unified")
        st.plotly_chart(fig_r, use_container_width=True)

        st.divider()
        st.markdown("### 📅 Daily Tickets Volume")
        
        daily_vol = dfm.groupby("Date Only").size().reset_index(name="Total Tickets")
        daily_vol["Date DT"] = pd.to_datetime(daily_vol["Date Only"])
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
        
        daily_vol["Color"] = np.where(daily_vol["Total Tickets"] >= 300, "#f59e0b", "#3b82f6")
        
        fig_d = go.Figure()
        fig_d.add_trace(go.Bar(
            x=daily_vol["Date Label"], 
            y=daily_vol["Total Tickets"], 
            text=daily_vol["Total Tickets"],
            textposition='auto',
            marker_color=daily_vol["Color"],
            name="Daily Volume",
            hovertemplate="<b>%{x}</b><br>Tickets: %{y}<extra></extra>"
        ))
        fig_d.update_layout(
            **THEME, 
            height=450, 
            xaxis_title="", 
            yaxis_title="Total Tickets", 
            hovermode="x unified"
        )
        st.plotly_chart(fig_d, use_container_width=True)

# ── TAB 2 — Team Performance and KPIs ──────────────────────────────────────────────
with tab2:
    st.markdown("### 👥 Team Performance and KPIs")
    t2c1, t2c2 = st.columns(2)
    with t2c1: t2e  = st.checkbox("🔥 Toggle: Escalated Cases Scope",   value=False, key="t2_esc")
    with t2c2: t2ne = st.checkbox("🟢 Toggle: Non-Escalated Cases Scope", value=False, key="t2_nesc")

    df_t2 = df.copy()
    if t2e  and not t2ne: df_t2 = df_t2[df_t2["Is Email"] == True]
    elif t2ne and not t2e: df_t2 = df_t2[df_t2["Is Email"] == False]

    aname = my_agent_name()
    df_kpi = df_t2[df_t2["Assigned By"] == aname].copy() if (not is_admin() and aname) else df_t2.copy()

    total_kpi = len(df_kpi)
    kpi_ss  = df_kpi["Status"].astype(str).str.strip()
    kpi_ok  = df_kpi[kpi_ss.str.contains("Closed", na=False, case=False) & ~kpi_ss.str.contains("issue", na=False, case=False)].shape[0]
    kpi_iss = df_kpi[kpi_ss.str.contains("Closed", na=False, case=False) & kpi_ss.str.contains("issue", na=False, case=False)].shape[0]

    kpi_ok_pct = (kpi_ok / total_kpi * 100) if total_kpi > 0 else 0
    kpi_iss_pct = (kpi_iss / total_kpi * 100) if total_kpi > 0 else 0

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.markdown(kpi_colored("Total Tickets",      f"{total_kpi:,}", "card-total"),     unsafe_allow_html=True)
    k2.markdown(kpi_colored("Closed Completed",   f"{kpi_ok:,} <span style='font-size:1rem; opacity:0.8'>({kpi_ok_pct:.1f}%)</span>",      "card-completed"), unsafe_allow_html=True)
    k3.markdown(kpi_colored("Closed with Issue",  f"{kpi_iss:,} <span style='font-size:1rem; opacity:0.8'>({kpi_iss_pct:.1f}%)</span>",     "card-issue"),     unsafe_allow_html=True)
    k4.markdown(kpi_colored("Avg Response (FRT)", fmt_m(df_kpi["Response Take (min)"].mean() if not df_kpi.empty else 0), "card-frt"), unsafe_allow_html=True)
    k5.markdown(kpi_colored("Avg Handling (AHT)", fmt_m(df_kpi["AHT (min)"].mean()           if not df_kpi.empty else 0), "card-aht"), unsafe_allow_html=True)
    k6.markdown(kpi_colored("Avg Service (TAT)",  fmt_m(df_kpi["Request Take (min)"].mean()   if not df_kpi.empty else 0), "card-tat"), unsafe_allow_html=True)

    st.write(""); st.divider()
    st.markdown("### 📊 Expert Performance Scorecard Dashboard")

    EXCL = ["mohammed shehta", "muhammad shehta", "muhammed shehta", "unassigned"]
    df_sc = df_t2[~df_t2["Assigned By"].astype(str).str.strip().str.lower().isin(EXCL)].copy()

    if not df_sc.empty:
        rtl = df_sc["Request Type"].astype(str).str.lower()
        df_sc["_jhah"]  = rtl.str.contains("jhah", na=False)
        df_sc["_rfb"]   = rtl.str.contains("report|feedback", na=False)
        df_sc["_c_ok"]  = (df_sc["Status"].astype(str).str.contains("Closed", case=False, na=False) & ~df_sc["Status"].astype(str).str.contains("issue", case=False, na=False))
        df_sc["_c_all"] = df_sc["Status"].astype(str).str.contains("Closed", case=False, na=False)

        grp = df_sc.groupby("Assigned By")
        sc  = pd.DataFrame(index=grp.groups.keys())
        sc.index.name = "Assigned By"
        sc["Working Days"]         = grp["Date Only"].nunique().astype(int)
        sc["Tickets Count"]        = grp["Request ID"].count()
        sc["JHAH Requests"]        = grp["_jhah"].sum().astype(int)
        sc["Reporting & Feedback"] = grp["_rfb"].sum().astype(int)
        sc["Email Counts"]         = grp["Is Email"].sum().astype(int)

        tavg = sc["Tickets Count"].mean()
        sc["% Achievement from Target"] = ((sc["Tickets Count"] / tavg * 100).round(1).astype(str) + "%" if tavg > 0 else "0.0%")
        sc["Service Time"] = grp["Request Take (min)"].mean().apply(fmt_m)
        sc["Service Quality"] = (grp["_c_ok"].sum() / grp["_c_all"].sum().replace(0,1) * 100).round(1).astype(str) + "%"
        sc = sc.reset_index().rename(columns={"Assigned By": "Expert"})

        # Apply system administrative manual data overrides
        for i, row in sc.iterrows():
            ov = overrides().get(row["Expert"], {})
            for col, val in ov.items(): sc.at[i, col] = val

        team_row = {
            "Expert": "🏆 Team AVG", 
            "Working Days": round(sc["Working Days"].mean(), 1), 
            "Tickets Count": round(sc["Tickets Count"].mean(), 1),
            "JHAH Requests": round(sc["JHAH Requests"].mean(), 1), 
            "Reporting & Feedback": round(sc["Reporting & Feedback"].mean(), 1),
            "Email Counts": round(sc["Email Counts"].mean(), 1), 
            "% Achievement from Target": "100.0%", 
            "Service Time": "00:00:00", 
            "Service Quality": "100.0%"
        }
        
        # Apply override to Team AVG if exists
        team_ov = overrides().get("🏆 Team AVG", {})
        for col, val in team_ov.items():
            team_row[col] = val

        # Base Matrix
        sc_final = pd.concat([pd.DataFrame([team_row]), sc], ignore_index=True) if is_admin() else pd.concat([pd.DataFrame([team_row]), sc[sc["Expert"] == aname]], ignore_index=True)

        # ── TOP PERFORMERS SMART COLOR HIGHLIGHTING ──────────────────────────────────
        rank_df = sc.copy()
        rank_df["_sort_val"] = pd.to_numeric(rank_df["Tickets Count"], errors="coerce").fillna(0)
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

        # Applying colors AND forcing the Expert column names to be intensely bold
        styled_df = display_df.style.apply(style_performers, axis=1)
        styled_df = styled_df.set_properties(subset=['Expert'], **{'font-weight': '900', 'color': '#0f172a'})
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # ── MANUAL KPI OVERRIDE EDITOR (Admin Only) ───────────────────────────────────
        if is_admin():
            st.divider()
            st.markdown("#### ✏️ Manual KPI Override Editor")
            
            agent_opts = list(sc["Expert"]) + ["🏆 Team AVG"]
            sel_agent  = st.selectbox("Choose agent to edit", agent_opts, key="agent_ov_sel")
            
            if sel_agent == "🏆 Team AVG":
                dv = team_row
            else:
                ar = sc[sc["Expert"] == sel_agent]
                dv = ar.iloc[0].to_dict() if not ar.empty else {}
                
            cur = overrides().get(sel_agent, {})
            def gv(k, t=int):
                val = cur.get(k, dv.get(k, 0 if t == int else ""))
                if t == int:
                    try: return int(float(val))
                    except: return 0
                return str(val)

            with st.form(f"ov_form_{sel_agent}"):
                fc1, fc2, fc3, fc4 = st.columns(4)
                with fc1:
                    nwd  = st.number_input("Working Days", min_value=0, value=gv("Working Days", int), step=1)
                    ntc  = st.number_input("Tickets Count", min_value=0, value=gv("Tickets Count", int), step=1)
                with fc2:
                    njh  = st.number_input("JHAH Requests", min_value=0, value=gv("JHAH Requests", int), step=1)
                    nrfb = st.number_input("Reporting & Feedback", min_value=0, value=gv("Reporting & Feedback", int), step=1)
                with fc3:
                    nem  = st.number_input("Email Counts", min_value=0, value=gv("Email Counts", int), step=1)
                    nach = st.text_input("% Achievement from Target", value=gv("% Achievement from Target", str))
                with fc4:
                    nst  = st.text_input("Service Time (HH:MM:SS)", value=gv("Service Time", str))
                    nsq  = st.text_input("Service Quality (%)", value=gv("Service Quality", str))
                
                sc_col, rc_col = st.columns(2)
                with sc_col: do_save  = st.form_submit_button("💾 Save Override", use_container_width=True)
                with rc_col: do_clear = st.form_submit_button("🔄 Clear Override", use_container_width=True)

            if do_save:
                overrides()[sel_agent] = {
                    "Working Days": nwd, "Tickets Count": ntc, "JHAH Requests": njh,
                    "Reporting & Feedback": nrfb, "Email Counts": nem,
                    "% Achievement from Target": nach,
                    "Service Time": nst, "Service Quality": nsq,
                }
                _save_store()
                st.success(f"✅ Override parameters applied for **{sel_agent}**.")
                st.rerun()

            if do_clear:
                if sel_agent in overrides():
                    overrides().pop(sel_agent)
                    _save_store()
                    st.success(f"🔄 Dropped local overrides back to dynamic context for **{sel_agent}**.")
                    st.rerun()
                else:
                    st.warning("No active overrides found to clear.")

            active_ovs = overrides()
            if active_ovs:
                st.write("")
                with st.expander("🗂️ Active Metric Overrides"):
                    st.json(active_ovs)
            
            # ── ✉️ END OF MONTH EMAIL GENERATOR ──────────────────────────────────────────
            st.divider()
            st.markdown("#### ✉️ End of Month Achievement Emails")
            
            email_agents_list = [x for x in display_df["Expert"] if "🏆 Team AVG" not in x]
            selected_email_agent = st.selectbox("Select Agent for Email Draft", email_agents_list)
            
            if selected_email_agent:
                agent_row = display_df[display_df["Expert"] == selected_email_agent].iloc[0]
                
                achiev_str = agent_row["% Achievement from Target"]
                achiev_val = float(str(achiev_str).replace('%', '')) if isinstance(achiev_str, str) else 0
                
                qual_str = agent_row["Service Quality"]
                qual_val = float(str(qual_str).replace('%', '')) if isinstance(qual_str, str) else 0
                
                if achiev_val >= 100:
                    perf_word = "outstanding"
                    target_msg = f"You successfully exceeded the team target with a brilliant **{achiev_str}** achievement rate!"
                elif achiev_val >= 80:
                    perf_word = "solid"
                    target_msg = f"You reached a solid **{achiev_str}** of the target. Great effort, and let's push for 100% next month!"
                else:
                    perf_word = "developing"
                    target_msg = f"You achieved **{achiev_str}** of the target. We believe in your potential and are here to support you in hitting higher milestones next month."
                
                if qual_val >= 95:
                    qual_msg = f"Your service quality is top-tier at **{qual_str}**. Keep up the flawless work!"
                elif qual_val >= 85:
                    qual_msg = f"Your service quality is strong at **{qual_str}**."
                else:
                    qual_msg = f"Your service quality sits at **{qual_str}**. Let's focus on accuracy and quality in the upcoming period."
                
                clean_name = selected_email_agent.replace("🥇 ", "").replace("🥈 ", "").replace("🥉 ", "")
                
                email_body = f"""Dear {clean_name},

I hope this email finds you well. 

As we wrap up the month, I wanted to personally share your performance metrics and highlight your {perf_word} contributions to the team.

📊 Your Monthly Performance Overview:
- Total Tickets Resolved: {agent_row['Tickets Count']}
- Working Days: {agent_row['Working Days']}
- Service Time (Avg): {agent_row['Service Time']}

🎯 Targets & Quality:
{target_msg}
{qual_msg}

Thank you for your hard work and dedication to our success. Should you need any support or wish to discuss your metrics further, my door is always open.

Best regards,
Mohammed Shehta
Team Leader"""
                
                st.text_area("Drafted Email (Ready to Copy)", value=email_body, height=350)
                
                subject_encoded = urllib.parse.quote(f"Your Monthly Performance Review - {clean_name}")
                body_encoded = urllib.parse.quote(email_body)
                mailto_link = f"mailto:?subject={subject_encoded}&body={body_encoded}"
                
                st.markdown(
                    f'<a href="{mailto_link}" style="display:inline-block; padding:0.6rem 1.2rem; background-color:#1d4ed8; color:white; text-decoration:none; border-radius:8px; font-weight:800; font-size:1.05rem;">'
                    f'📧 Open in Default Email Client</a>', 
                    unsafe_allow_html=True
                )

st.info(f"⏱️ Operational Sync Status: Metrics loaded completely across {len(df)} synced records.")
# --- END OF SCRIPT ---
