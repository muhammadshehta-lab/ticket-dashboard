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
.login-sub { font-size:.86rem; text-align:center; color:#64748b; margin-bottom:1.2rem; }

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

# 👥 إعدادات ثيم القوالب لـ Plotly بالوضع الفاتح
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

    # ── دالة جلب البيانات من شيت جوجل ──
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
                        eu_role = st.selectbox("Role", ["expert","admin"], index=0 if urow["role"] != "admin" else 1, key=f"rl_{uname}")
                        saved   = st.form_submit_button("💾 Update User Settings", use_container_width=True)
                    if saved:
                        if eu_dn.strip(): users()[uname]["display_name"] = eu_dn.strip()
                        users()[uname]["agent_name"] = eu_an.strip() if eu_an.strip() else None
                        users()[uname]["role"] = eu_role
                        if eu_p1 and eu_p1 == eu_p2: users()[uname]["password_hash"] = _hash(eu_p1)
                        _save_store(); st.success("✅ User settings updated."); st.rerun()
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
        
        # 🌀 مصفوفة السنبورست المحدثة لإظهار الاسم والعدد والنسبة بداخل مساحات الرسم مباشرة
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
        hrs = dfm.groupby("Hour").agg(Volume=("Request ID", "count"), AR=("Response Take (min)" , "mean")).reset_index()
        hrs = hrs.set_index("Hour").reindex(range(24)).fillna(0).reset_index()
        hl = ["12 AM" if h == 0 else ("12 PM" if h == 12 else (f"{h} AM" if h < 12 else f"{h - 12} PM")) for h in hrs["Hour"]]
        hrs["Hour Label"] = hl
        fig_r = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"], y=hrs["Volume"], name="Volume", fill="tozeroy", line=dict(color="#58a6ff", width=2)), secondary_y=False)
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"], y=hrs["AR"], name="FRT (Avg Response)", mode="lines+markers", line=dict(color="#f0883e", width=3, shape="spline")), secondary_y=True)
        fig_r.update_layout(**THEME, height=450, hovermode="x unified")
        st.plotly_chart(fig_r, use_container_width=True)

# ── TAB 2 — Team Performance and KPIs (منظومة عزل العرض الحساسة بالـ ID للموظف) ──
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

    kpi_ss  = df_kpi["Status"].astype(str).str.strip()
    kpi_ok  = df_kpi[kpi_ss.str.contains("Closed", na=False, case=False) & ~kpi_ss.str.contains("issue", na=False, case=False)].shape[0]
    kpi_iss = df_kpi[kpi_ss.str.contains("Closed", na=False, case=False) & kpi_ss.str.contains("issue", na=False, case=False)].shape[0]

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.markdown(kpi_colored("Total Tickets",      f"{len(df_kpi):,}", "card-total"),     unsafe_allow_html=True)
    k2.markdown(kpi_colored("Closed Completed",   f"{kpi_ok:,}",      "card-completed"), unsafe_allow_html=True)
    k3.markdown(kpi_colored("Closed with Issue",  f"{kpi_iss:,}",     "card-issue"),     unsafe_allow_html=True)
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

        for i, row in sc.iterrows():
            ov = overrides().get(row["Expert"], {})
            for col, val in ov.items(): sc.at[i, col] = val

        team_row = {
            "Expert": "🏆 Team AVG", "Working Days": round(sc["Working Days"].mean(), 1), "Tickets Count": round(sc["Tickets Count"].mean(), 1),
            "JHAH Requests": round(sc["JHAH Requests"].mean(), 1), "Reporting & Feedback": round(sc["Reporting & Feedback"].mean(), 1),
            "Email Counts": round(sc["Email Counts"].mean(), 1), "% Achievement from Target": "100.0%", "Service Time": "00:00:00", "Service Quality": "100.0%"
        }

        sc_final = pd.concat([pd.DataFrame([team_row]), sc], ignore_index=True) if is_admin() else pd.concat([pd.DataFrame([team_row]), sc[sc["Expert"] == aname]], ignore_index=True)
        st.dataframe(sc_final, use_container_width=True, hide_index=True)

st.info(f"⏱️ Operational Sync Status: Light metrics layout loaded completely across {len(df)} synced records.")
