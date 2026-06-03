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
    if _DATA_FILE.exists():
        try:
            return json.loads(_DATA_FILE.read_text())
        except Exception:
            pass
    
    # Pre-seeded database with strict Employee ID mappings
    return {
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

def _save_store():
    _DATA_FILE.write_text(json.dumps(st.session_state.store, indent=2))

# ══════════════════════════════════════════════════════════════════════════════════
#  CSS  — Standard default Streamlit sans-serif styling
# ══════════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ══ BASE ════════════════════════════════════════════════════════════ */
.stApp {
    background: radial-gradient(ellipse at 20% 10%, #1a0533 0%, #0e0120 40%, #060012 100%);
    color: #e8d5ff;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d0120 0%, #120028 60%, #0a001e 100%);
    border-right: 1px solid #3d1060;
}
[data-testid="stSidebar"] * { color: #cda8ff !important; }
[data-testid="stSidebar"] .stButton button {
    background: linear-gradient(135deg,#1e0545,#2a0660) !important;
    border: 1px solid #7b2fff !important;
    color: #d4a8ff !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: linear-gradient(135deg,#2e0870,#3a0a88) !important;
    border-color: #b060ff !important;
    color: #f0d8ff !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent; color: #7a4aaa; font-weight: 700;
    border-bottom: 2px solid transparent;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #e040fb !important; border-bottom: 2px solid #e040fb !important;
}
h2,h3 { color:#f0d8ff !important; }
.stMarkdown p { color:#c09ee0; }
hr { border-color:#3d1060 !important; }
.stTextInput input, .stNumberInput input, .stSelectbox select, .stDateInput input {
    background: #12002a !important; border: 1px solid #6020b0 !important;
    color: #e8d5ff !important; border-radius: 10px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #e040fb !important;
    box-shadow: 0 0 0 3px rgba(224,64,251,.18) !important;
}
.stButton > button {
    background: linear-gradient(135deg, #2a0060 0%, #48009a 100%) !important;
    border: 1px solid #9030e0 !important; color: #e8b8ff !important;
    border-radius: 10px !important; font-weight: 700 !important;
    transition: all .2s ease;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #3a0090 0%, #6000cc 100%) !important;
    border-color: #d060ff !important; color: #f8e0ff !important;
    transform: translateY(-2px); box-shadow: 0 6px 20px rgba(180,60,255,.3);
}
.stAlert { border-radius: 12px !important; }

/* ══ KPI CARDS ═══════════════════════════════════════════════════════ */
.kpi-container {
    border-radius: 18px; padding: 1.3rem 1rem; text-align: center;
    min-height: 118px; display: flex; flex-direction: column;
    justify-content: center; margin-bottom: 1rem;
    position: relative; overflow: hidden; transition: transform .25s, box-shadow .25s;
}
.kpi-container:hover { transform: translateY(-4px); }
.kpi-container::before {
    content:''; position:absolute; inset:0;
    background:linear-gradient(135deg,rgba(255,255,255,.06) 0%,transparent 55%);
    pointer-events:none;
}
.kpi-label {
    font-size: .66rem; letter-spacing: .14em; text-transform: uppercase;
    margin-bottom: .45rem; font-weight: 700; opacity: .7;
}
.kpi-value { font-size: 1.55rem; font-weight: 800; letter-spacing: -.01em; }
.card-total     { background:linear-gradient(135deg,#2a0040,#3d006a); border:1px solid #e040fb; color:#f580ff; box-shadow:0 0 24px rgba(224,64,251,.2); }
.card-completed { background:linear-gradient(135deg,#0a2000,#163400); border:1px solid #76ff03; color:#aaff57; box-shadow:0 0 24px rgba(118,255,3,.15); }
.card-issue     { background:linear-gradient(135deg,#2a0e00,#401800); border:1px solid #ff6d00; color:#ff9e40; box-shadow:0 0 24px rgba(255,109,0,.18); }
.card-frt       { background:linear-gradient(135deg,#2a0020,#400035); border:1px solid #f50057; color:#ff6090; box-shadow:0 0 24px rgba(245,0,87,.18); }
.card-aht       { background:linear-gradient(135deg,#00103a,#001a5a); border:1px solid #2979ff; color:#6ea8ff; box-shadow:0 0 24px rgba(41,121,255,.18); }
.card-tat       { background:linear-gradient(135deg,#001e22,#003038); border:1px solid #00e5ff; color:#40f8ff; box-shadow:0 0 24px rgba(0,229,255,.16); }

/* ══ LOGIN ════════════════════════════════════════════════════════════ */
.login-wrap {
    max-width:440px; margin:3rem auto 0; padding:2rem 2.4rem 1rem;
    background:linear-gradient(160deg,#0e0025,#180038);
    border:1px solid #6020b0; border-radius:22px;
    box-shadow:0 24px 70px rgba(160,0,255,.25);
}
.login-title {
    font-size:1.75rem; font-weight:800; text-align:center; margin-bottom:.3rem;
    background:linear-gradient(90deg,#e040fb,#40c4ff,#76ff03);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.login-sub { font-size:.86rem; text-align:center; color:#8050b0; margin-bottom:1.2rem; }

/* ══ BADGES ══════════════════════════════════════════════════════════ */
.badge { display:inline-block; font-size:.64rem; border-radius:7px; padding:2px 9px; margin-left:6px; font-weight:800; letter-spacing:.1em; }
.badge-admin  { background:#1a0030; border:1px solid #e040fb; color:#f580ff; }
.badge-expert { background:#001020; border:1px solid #00e5ff; color:#40f8ff; }

/* ══ REQUEST BANNERS ══════════════════════════════════════════════════ */
.req-pending  { background:linear-gradient(90deg,#1e1000,#2a1800); border:1px solid #ff6d00; border-radius:12px; padding:.75rem 1.2rem; margin-bottom:.8rem; color:#ff9e40; font-size:.88rem; }
.req-approved { background:linear-gradient(90deg,#0a2000,#102800); border:1px solid #76ff03; border-radius:12px; padding:.75rem 1.2rem; margin-bottom:.8rem; color:#aaff57; font-size:.88rem; }
.req-rejected { background:linear-gradient(90deg,#200010,#2e0018); border:1px solid #f50057; border-radius:12px; padding:.75rem 1.2rem; margin-bottom:.8rem; color:#ff6090; font-size:.88rem; }

/* ══ SECTION CARD ═════════════════════════════════════════════════════ */
.section-card { background:linear-gradient(135deg,#0e0025,#16003a); border:1px solid #4a1080; border-radius:16px; padding:1.5rem 1.8rem; margin-bottom:1.2rem; }
</style>
""", unsafe_allow_html=True)

THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(18,0,40,.5)",
    font_color="#cda8ff",
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

# ── Store Management Helpers ────────────────══════════════════════════════════════
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
                # Create a fresh expert account from the approved visitor request
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
                    # Check first-time login scenario (ID matched password string input)
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
            visitor_name = st.text_input("Enter Your Full Name (Display Name)", placeholder="e.g. John Doe")
            
            if st.button("📤 Submit Access Request", use_container_width=True):
                if visitor_name.strip():
                    # Format as request
                    push_request(visitor_name.strip(), "visitor_access", "123456789")
                    st.success("✅ Request sent to admin! Username will be your name, default password will be 123456789 upon approval.")
                    time.sleep(2)
                    st.session_state.view_request_form = False
                    st.rerun()
                else:
                    st.error("Name field cannot be left empty.")
            
            if st.button("← Back to Login", use_container_width=True):
                st.session_state.view_request_form = False
                st.rerun()
    st.stop()

# Forced onboarding view wrapper if active
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
#  SIDEBAR MANAGEMENT & LIVE DATA FETCHING
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

    # ── Live Sync Data Pipeline Loader ──
    @st.cache_data(ttl=600, show_spinner="Syncing database tables…")
    def load_data():
        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets",
                      "https://www.googleapis.com/auth/drive"]
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
    date_range = st.date_input("Date Range", value=(min_d, max_d),
                               min_value=min_d, max_value=max_d)
    d_from, d_to = (
        date_range if isinstance(date_range, (list, tuple)) and len(date_range) == 2
        else (min_d, max_d)
    )
    if d_from == d_to:
        st.caption(f"📅 {DAYS_AR.get(pd.to_datetime(d_from).day_name(), '')}")
    st.divider()
    sel_agents = st.multiselect("Agent Filter",
                                sorted(df_raw["Assigned By"].dropna().unique()))
    sel_types  = st.multiselect("Request Type Filter",
                                sorted(df_raw["Request Type"].dropna().unique()))

df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_agents: df = df[df["Assigned By"].isin(sel_agents)]
if sel_types:  df = df[df["Request Type"].isin(sel_types)]

# ══════════════════════════════════════════════════════════════════════════════════
#  SETTINGS PANEL (ADMIN CONTROL / ACCOUNT ADJUSTMENTS)
# ══════════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "settings":
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"; st.rerun()

    # ── ADMIN VIEW SETTINGS PANEL ──
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
                    else: st.warning("No value variation detected.")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div class='section-card'>", unsafe_allow_html=True)
            st.markdown("**🔑 Change Password**")
            with st.form("admin_pw_form"):
                old_pw  = st.text_input("Current Account Password", type="password")
                new_pw1 = st.text_input("New Secure Password",     type="password")
                new_pw2 = st.text_input("Confirm Secure Password", type="password")
                if st.form_submit_button("💾 Update Password", use_container_width=True):
                    if _hash(old_pw) != urow["password_hash"]:
                        st.error("❌ Password input incorrect.")
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
                st.info("✅ No system requests pending approval.")
            else:
                for req in pending:
                    if req["type"] == "visitor_access":
                        st.markdown(f"""
                        <div class='req-pending'>
                            🕐 <b>{req['ts']}</b> &nbsp;|&nbsp;
                            🔑 <b>VISITOR REQUEST</b> &nbsp;|&nbsp;
                            Full Name: <b>{req['requester']}</b> wants an active account.
                        </div>""", unsafe_allow_html=True)
                        rc1, rc2, rc3 = st.columns([3, 1, 1])
                        with rc2:
                            if st.button("✅ Approve Access", key=f"apr_vis_{req['id']}", use_container_width=True):
                                approve_request(req["id"])
                                st.success(f"Approved and seeded account for visitor: {req['requester']}."); st.rerun()
                        with rc3:
                            if st.button("❌ Deny Access", key=f"rej_vis_{req['id']}", use_container_width=True):
                                reject_request(req["id"]); st.warning("Access configuration dropped."); st.rerun()
                    else:
                        udata_r   = users().get(req["requester"], {})
                        udisp     = udata_r.get("display_name", req["requester"])
                        req_label = "Display Name" if req["type"] == "display_name" else "Password"
                        val_show  = req["new_value"] if req["type"] == "display_name" else "••••••••"
                        st.markdown(f"""
                        <div class='req-pending'>
                            🕐 <b>{req['ts']}</b> &nbsp;|&nbsp;
                            👤 <b>{udisp}</b> (@{req['requester']}) &nbsp;|&nbsp;
                            Wants to adjust <b>{req_label}</b>
                            {f"→ <b>{val_show}</b>" if req['type']=='display_name' else ""}
                        </div>""", unsafe_allow_html=True)
                        rc1, rc2, rc3 = st.columns([3, 1, 1])
                        with rc2:
                            if st.button("✅ Approve", key=f"apr_{req['id']}", use_container_width=True):
                                approve_request(req["id"])
                                st.success(f"Approved {req_label} change for {udisp}."); st.rerun()
                        with rc3:
                            if st.button("❌ Reject", key=f"rej_{req['id']}", use_container_width=True):
                                reject_request(req["id"]); st.warning("Modification request rejected."); st.rerun()

            history = [r for r in requests() if r["status"] != "pending"]
            if history:
                st.divider()
                with st.expander(f"📋 Configuration History Ledger ({len(history)} entries)"):
                    for req in reversed(history):
                        udisp     = users().get(req["requester"], {}).get("display_name", req["requester"])
                        req_label = "Access/Profile Adjustment" if req["type"] == "visitor_access" else ("Display Name" if req["type"] == "display_name" else "Password")
                        css       = "req-approved" if req["status"] == "approved" else "req-rejected"
                        icon      = "✅" if req["status"] == "approved" else "❌"
                        st.markdown(f"""
                        <div class='{css}'>
                            {icon} <b>{req['ts']}</b> &nbsp;|&nbsp;
                            Identity: {udisp if req['type']!='visitor_access' else req['requester']} — Scope: {req_label} — Outcome: <b>{req['status'].upper()}</b>
                        </div>""", unsafe_allow_html=True)

        with atab3:
            st.markdown("### 👥 Manage Dashboard Users")
            for uname, urow in list(users().items()):
                role_icon = "🔑" if urow["role"] == "admin" else "👤"
                with st.expander(
                    f"{role_icon} {urow['display_name']} (@{uname}) — {urow['role'].upper()}"
                    + (f" | Agent Scope: {urow.get('agent_name','—')}" if urow.get('agent_name') else "")
                ):
                    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
                    with st.form(f"admin_edit_{uname}"):
                        eu_dn   = st.text_input("Display Username", value=urow["display_name"],           key=f"dn_{uname}")
                        eu_an   = st.text_input("Agent Key Mapping (Matches Sheets Column Exactly)",
                                                value=urow.get("agent_name") or "",                      key=f"an_{uname}")
                        eu_p1   = st.text_input("Override Password (leave blank to maintain current)", type="password",          key=f"p1_{uname}")
                        eu_p2   = st.text_input("Confirm Override Password", type="password",          key=f"p2_{uname}")
                        eu_role = st.selectbox("Assign System Role", ["expert","admin"],
                                               index=0 if urow["role"] != "admin" else 1,               key=f"rl_{uname}")
                        saved   = st.form_submit_button("💾 Update User Settings", use_container_width=True)
                    if saved:
                        msgs = []
                        if eu_dn.strip() and eu_dn.strip() != urow["display_name"]:
                            users()[uname]["display_name"] = eu_dn.strip(); msgs.append("Name column altered.")
                        an_val = eu_an.strip() if eu_an.strip() else None
                        if an_val != urow.get("agent_name"):
                            users()[uname]["agent_name"] = an_val; msgs.append("Agent column altered.")
                        if eu_role != urow["role"]:
                            users()[uname]["role"] = eu_role; msgs.append("System tier role shifted.")
                        if eu_p1:
                            if eu_p1 != eu_p2:      st.error("❌ Inputs do not synchronize.")
                            elif len(eu_p1) < 6:    st.error("❌ Length must be ≥ 6.")
                            else:
                                users()[uname]["password_hash"] = _hash(eu_p1); msgs.append("Password forced switch update completed.")
                        if msgs: _save_store(); st.success("✅ " + " ".join(msgs)); st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    # ── EXPERT ROLE PROFILE SETTINGS ──
    else:
        st.markdown("## ⚙️ My Profile Settings")
        urow = users()[me()]

        my_pend = [r for r in requests() if r["requester"] == me() and r["status"] == "pending"]
        my_done = [r for r in requests() if r["requester"] == me() and r["status"] != "pending"]

        if my_pend:
            st.markdown("**🕐 Your Pending Validation Inbound Queue:**")
            for req in my_pend:
                lbl = "Display Name" if req["type"] == "display_name" else "Password"
                st.markdown(f"<div class='req-pending'>🕐 <b>{req['ts']}</b> — <b>{lbl}</b> modification awaiting admin verification review.</div>",
                            unsafe_allow_html=True)
        for req in my_done[-3:]:
            lbl  = "Display Name" if req["type"] == "display_name" else "Password"
            css  = "req-approved" if req["status"] == "approved" else "req-rejected"
            icon = "✅" if req["status"] == "approved" else "❌"
            st.markdown(f"<div class='{css}'>{icon} <b>{req['ts']}</b> — <b>{lbl}</b> submission process marked as <b>{req['status'].upper()}</b>.</div>",
                        unsafe_allow_html=True)
        st.divider()

        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("### ✏️ Propose Profile Display Name Change")
        already_dn = any(r["requester"] == me() and r["type"] == "display_name" and r["status"] == "pending"
                         for r in requests())
        if already_dn:
            st.warning("⏳ Name change request is currently pending in queue.")
        else:
            with st.form("expert_name_form"):
                req_name = st.text_input("Proposed Display Name", placeholder=urow["display_name"])
                if st.form_submit_button("📤 Submit Request to Admin", use_container_width=True):
                    if not req_name.strip():              st.error("Text content empty.")
                    elif req_name.strip() == urow["display_name"]: st.warning("Matches current name state.")
                    else:
                        push_request(me(), "display_name", req_name.strip())
                        st.success("✅ Request delivered for management confirmation review."); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("### 🔑 Direct Password Adjuster Form")
        st.caption("Direct update — bypasses admin verification queue immediately.")
        with st.form("expert_pw_direct"):
            cur_pw  = st.text_input("Verify Current Password", type="password")
            new_p1  = st.text_input("Set New Secret Password", type="password")
            new_p2  = st.text_input("Confirm New Secret Password", type="password")
            if st.form_submit_button("💾 Save Changes", use_container_width=True):
                if _hash(cur_pw) != urow["password_hash"]:
                    st.error("❌ Validation failure: old parameter incorrect.")
                elif new_p1 != new_p2:  st.error("❌ Synchronization input error.")
                elif len(new_p1) < 6:   st.error("❌ Structural threshold error: ≥ 6 parameters required.")
                else:
                    users()[me()]["password_hash"] = _hash(new_p1)
                    _save_store(); st.success("✅ Secret credentials updated successfully.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()

# ══════════════════════════════════════════════════════════════════════════════════
#  DASHBOARD CONTROL MODULE HEADER
# ══════════════════════════════════════════════════════════════════════════════════
caption_text = (
    f"🔍 Search Period: {d_from} ({DAYS_AR.get(pd.to_datetime(d_from).day_name(), '')})"
    if d_from == d_to else f"🔍 Search Period: {d_from} to {d_to}"
)
st.markdown("## 💊 In-Store Requests Matrix")
st.caption(caption_text)

if not is_admin():
    aname = my_agent_name()
    st.info(f"👤 Personalized View Context Active"
            f"{f' — Tracking Expert ID Match: **{aname}**' if aname else ''}.")

# ══════════════════════════════════════════════════════════════════════════════════
#  TABS NAVIGATION ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["📈 Tab 1: Operational Insights",
                       "👥 Tab 2: Team Performance and KPIs"])

# ══════════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Operational Insights (Publicly available context for team reference)
# ══════════════════════════════════════════════════════════════════════════════════
with tab1:
    c1, c2 = st.columns(2)
    with c1: esc  = st.checkbox("🔥 Filter: Escalated Cases Only",    value=False, key="t1_esc")
    with c2: nesc = st.checkbox("🟢 Filter: Non-Escalated Cases Only", value=False, key="t1_nesc")

    dfm = df.copy()
    if esc  and not nesc: dfm = dfm[dfm["Is Email"] == True]
    elif nesc and not esc: dfm = dfm[dfm["Is Email"] == False]

    total = len(dfm)
    ss    = dfm["Status"].astype(str).str.strip()
    ok    = dfm[ss.str.contains("Closed", na=False, case=False) &
                ~ss.str.contains("issue", na=False, case=False)].shape[0]
    issue = dfm[ss.str.contains("Closed", na=False, case=False) &
                 ss.str.contains("issue", na=False, case=False)].shape[0]
    h_frt = fmt_m(dfm["Response Take (min)"].mean() if not dfm.empty else 0)
    h_aht = fmt_m(dfm["AHT (min)"].mean()           if not dfm.empty else 0)
    h_tat = fmt_m(dfm["Request Take (min)"].mean()   if not dfm.empty else 0)

    a, b, c_, d, e, f_ = st.columns(6)
    a.markdown(kpi_colored("Total Tickets",      f"{total:,}", "card-total"),     unsafe_allow_html=True)
    b.markdown(kpi_colored("Closed Completed",   f"{ok:,}",    "card-completed"), unsafe_allow_html=True)
    c_.markdown(kpi_colored("Closed with Issue", f"{issue:,}", "card-issue"),     unsafe_allow_html=True)
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
        t_ord = ["Under 15 Mins", "15-30 Mins", "30-45 Mins", "45-60 Mins", "Over 1 Hour"]
        c_ord = ["Response Time", "Service Resolution"]
        sb_df["SLA Category"] = pd.Categorical(sb_df["SLA Category"], categories=c_ord, ordered=True)
        sb_df["SLA Tier"]     = pd.Categorical(sb_df["SLA Tier"],     categories=t_ord, ordered=True)
        sb_df = sb_df.sort_values(["SLA Category", "SLA Tier"]).reset_index(drop=True)
        sb_df["SLA Category"] = sb_df["SLA Category"].astype(str)
        sb_df["SLA Tier"]     = sb_df["SLA Tier"].astype(str)
        fig_sb = px.sunburst(
            sb_df, path=["SLA Category", "SLA Tier"], values="Tickets", color="SLA Tier",
            color_discrete_map={"Under 15 Mins": "#2ea44f", "15-30 Mins": "#2188ff",
                                "30-45 Mins": "#bc8cff", "45-60 Mins": "#f9c51
