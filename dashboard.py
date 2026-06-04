import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json, hashlib, time, pathlib, re

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
#  PERSISTENCE  — single JSON file next to the script
# ══════════════════════════════════════════════════════════════════════════════════
_DATA_FILE = pathlib.Path(__file__).parent / ".dashboard_data.json"

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def _make_ukey(agent_name: str) -> str:
    """Convert 'Assigned By' display name → safe lowercase username key."""
    return re.sub(r"[^a-z0-9_]", "_", agent_name.strip().lower())

def _load_store() -> dict:
    if _DATA_FILE.exists():
        try:
            return json.loads(_DATA_FILE.read_text())
        except Exception:
            pass
    # Default factory — only admin pre-seeded; experts auto-seeded at runtime
    return {
        "users": {
            "admin": {
                "display_name":  "Mohammed Shehta",
                "password_hash": _hash("admin123"),
                "role":          "admin",
                "agent_name":    None,   # admin sees all
            },
        },
        "requests":  [],
        "overrides": {},
    }

def _save_store():
    _DATA_FILE.write_text(json.dumps(st.session_state.store, indent=2))

# ══════════════════════════════════════════════════════════════════════════════════
#  CSS  — Streamlit default font family; custom dark purple theme kept
# ══════════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ══ BASE — Streamlit default font; custom dark theme kept ═══════════ */
.stApp {
    background: radial-gradient(ellipse at 20% 10%, #1a0533 0%, #0e0120 40%, #060012 100%);
    color: #e8d5ff;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}
* { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important; }
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
    background: transparent; color: #7a4aaa; font-weight: 600;
    border-bottom: 2px solid transparent;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #e040fb !important; border-bottom: 2px solid #e040fb !important;
}
h2, h3 { color: #f0d8ff !important; }
.stMarkdown p { color: #c09ee0; }
hr { border-color: #3d1060 !important; }
.stTextInput input, .stNumberInput input, .stSelectbox select, .stDateInput input {
    background: #12002a !important;
    border: 1px solid #6020b0 !important;
    color: #e8d5ff !important;
    border-radius: 8px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #e040fb !important;
    box-shadow: 0 0 0 3px rgba(224,64,251,.18) !important;
}
.stButton > button {
    background: linear-gradient(135deg, #2a0060 0%, #48009a 100%) !important;
    border: 1px solid #9030e0 !important;
    color: #e8b8ff !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all .2s ease;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #3a0090 0%, #6000cc 100%) !important;
    border-color: #d060ff !important;
    color: #f8e0ff !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(180,60,255,.28);
}
.stAlert { border-radius: 10px !important; }

/* ══ KPI CARDS ════════════════════════════════════════════════════════ */
.kpi-container {
    border-radius: 14px; padding: 1.2rem 0.9rem; text-align: center;
    min-height: 112px; display: flex; flex-direction: column;
    justify-content: center; margin-bottom: 1rem;
    position: relative; overflow: hidden; transition: transform .2s;
}
.kpi-container:hover { transform: translateY(-3px); }
.kpi-container::before {
    content:''; position:absolute; inset:0;
    background: linear-gradient(135deg,rgba(255,255,255,.05) 0%,transparent 55%);
    pointer-events: none;
}
.kpi-label {
    font-size: .68rem; letter-spacing: .12em; text-transform: uppercase;
    margin-bottom: .4rem; font-weight: 700; opacity: .72;
}
.kpi-value { font-size: 1.5rem; font-weight: 800; }
.card-total     { background:linear-gradient(135deg,#2a0040,#3d006a); border:1px solid #e040fb; color:#f580ff; box-shadow:0 0 22px rgba(224,64,251,.2);  }
.card-completed { background:linear-gradient(135deg,#0a2000,#163400); border:1px solid #76ff03; color:#aaff57; box-shadow:0 0 22px rgba(118,255,3,.15);   }
.card-issue     { background:linear-gradient(135deg,#2a0e00,#401800); border:1px solid #ff6d00; color:#ff9e40; box-shadow:0 0 22px rgba(255,109,0,.18);   }
.card-frt       { background:linear-gradient(135deg,#2a0020,#400035); border:1px solid #f50057; color:#ff6090; box-shadow:0 0 22px rgba(245,0,87,.18);    }
.card-aht       { background:linear-gradient(135deg,#00103a,#001a5a); border:1px solid #2979ff; color:#6ea8ff; box-shadow:0 0 22px rgba(41,121,255,.18);  }
.card-tat       { background:linear-gradient(135deg,#001e22,#003038); border:1px solid #00e5ff; color:#40f8ff; box-shadow:0 0 22px rgba(0,229,255,.16);   }

/* ══ LOGIN ════════════════════════════════════════════════════════════ */
.login-wrap {
    max-width: 440px; margin: 5rem auto 0; padding: 2.6rem 2.2rem;
    background: linear-gradient(160deg,#0e0025,#180038);
    border: 1px solid #6020b0; border-radius: 20px;
    box-shadow: 0 20px 60px rgba(160,0,255,.22);
}
.login-title {
    font-size: 1.65rem; font-weight: 800; text-align: center; margin-bottom: .3rem;
    background: linear-gradient(90deg,#e040fb,#40c4ff,#76ff03);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.login-sub { font-size:.84rem; text-align:center; color:#8050b0; margin-bottom:1.6rem; }

/* ══ BADGES ══════════════════════════════════════════════════════════ */
.badge { display:inline-block; font-size:.62rem; border-radius:6px; padding:2px 8px; margin-left:5px; font-weight:800; letter-spacing:.1em; }
.badge-admin  { background:#1a0030; border:1px solid #e040fb; color:#f580ff; }
.badge-expert { background:#001020; border:1px solid #00e5ff; color:#40f8ff; }

/* ══ REQUEST BANNERS ══════════════════════════════════════════════════ */
.req-pending  { background:linear-gradient(90deg,#1e1000,#2a1800); border:1px solid #ff6d00; border-radius:10px; padding:.7rem 1.1rem; margin-bottom:.7rem; color:#ff9e40; font-size:.87rem; }
.req-approved { background:linear-gradient(90deg,#0a2000,#102800); border:1px solid #76ff03; border-radius:10px; padding:.7rem 1.1rem; margin-bottom:.7rem; color:#aaff57; font-size:.87rem; }
.req-rejected { background:linear-gradient(90deg,#200010,#2e0018); border:1px solid #f50057; border-radius:10px; padding:.7rem 1.1rem; margin-bottom:.7rem; color:#ff6090; font-size:.87rem; }

/* ══ SECTION CARD ════════════════════════════════════════════════════ */
.section-card { background:linear-gradient(135deg,#0e0025,#16003a); border:1px solid #4a1080; border-radius:14px; padding:1.4rem 1.6rem; margin-bottom:1.1rem; }
</style>
""", unsafe_allow_html=True)

THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(18,0,40,.45)",
    font_color="#cda8ff",
    margin=dict(l=10, r=10, t=55, b=10)
)

# ══════════════════════════════════════════════════════════════════════════════════
#  SESSION STATE BOOT
# ══════════════════════════════════════════════════════════════════════════════════
if "store" not in st.session_state:
    st.session_state.store = _load_store()
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username      = None
    st.session_state.role          = None
if "page" not in st.session_state:
    st.session_state.page = "dashboard"

# ── Store shortcuts ───────────────────────────────────────────────────────────────
def users()     -> dict: return st.session_state.store["users"]
def requests()  -> list: return st.session_state.store["requests"]
def overrides() -> dict: return st.session_state.store["overrides"]
def me()        -> str:  return st.session_state.username
def is_admin()  -> bool: return st.session_state.role == "admin"
def cur_user()  -> dict: return users().get(me(), {})

def my_agent_name() -> str | None:
    """The exact 'Assigned By' string for the logged-in expert (None for admin)."""
    return cur_user().get("agent_name")

def pending_count() -> int:
    return sum(1 for r in requests() if r["status"] == "pending")

def push_request(uname: str, rtype: str, new_value: str):
    requests().append({
        "id": int(time.time() * 1000), "requester": uname,
        "type": rtype, "new_value": new_value,
        "status": "pending", "ts": time.strftime("%Y-%m-%d %H:%M"),
    })
    _save_store()

def approve_request(req_id: int):
    for r in requests():
        if r["id"] == req_id and r["status"] == "pending":
            u = r["requester"]
            if r["type"] == "display_name": users()[u]["display_name"] = r["new_value"]
            elif r["type"] == "password":   users()[u]["password_hash"] = _hash(r["new_value"])
            r["status"] = "approved"; _save_store(); return True
    return False

def reject_request(req_id: int):
    for r in requests():
        if r["id"] == req_id and r["status"] == "pending":
            r["status"] = "rejected"; _save_store(); return True
    return False

# ══════════════════════════════════════════════════════════════════════════════════
#  METRIC HELPERS
# ══════════════════════════════════════════════════════════════════════════════════
def kpi_colored(label: str, value: str, cls: str) -> str:
    return (f'<div class="kpi-container {cls}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div></div>')

def time_to_minutes(s) -> float:
    try:
        p = str(s).strip().split(":")
        return int(p[0]) * 60 + int(p[1])
    except:
        return 0

def fmt_m(v) -> str:
    """Convert fractional minutes → HH:MM:SS string."""
    try:
        if pd.isna(v) or float(v) <= 0: return "00:00:00"
    except: return "00:00:00"
    t = int(round(float(v) * 60))
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"

def assign_time_tier(m: float) -> str:
    if m <= 15: return "Under 15 Mins"
    if m <= 30: return "15-30 Mins"
    if m <= 45: return "30-45 Mins"
    if m <= 60: return "45-60 Mins"
    return "Over 1 Hour"

DAYS_AR = {
    "Saturday": "السبت", "Sunday": "الأحد", "Monday": "الإثنين",
    "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء",
    "Thursday": "الخميس", "Friday": "الجمعة",
}

# ══════════════════════════════════════════════════════════════════════════════════
#  LOGIN GATE
# ══════════════════════════════════════════════════════════════════════════════════
if not st.session_state.authenticated:
    st.markdown("""
    <div class='login-wrap'>
        <div class='login-title'>💊 Dashboard Login</div>
        <div class='login-sub'>In-Store Requests · AlDawaa</div>
    </div>""", unsafe_allow_html=True)

    _, lc, _ = st.columns([1, 1.4, 1])
    with lc:
        st.write("")
        inp_u = st.text_input("Username", placeholder="Enter username", key="li_u")
        inp_p = st.text_input("Password", type="password", placeholder="Enter password", key="li_p")
        if st.button("🔐 Login", use_container_width=True):
            # Try exact match first, then generated key
            uname_try = [
                inp_u.strip().lower(),
                _make_ukey(inp_u.strip()),
            ]
            matched = None
            for attempt in uname_try:
                if attempt in users():
                    matched = attempt
                    break
            udata = users().get(matched) if matched else None
            if udata and udata["password_hash"] == _hash(inp_p):
                st.session_state.authenticated = True
                st.session_state.username      = matched
                st.session_state.role          = udata["role"]
                st.session_state.page          = "dashboard"
                st.rerun()
            else:
                st.error("❌ Incorrect username or password.")
        st.caption("💡 Default expert password: **pass1234**")
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 💊 Navigation & Filters")

    badge_cls = "badge-admin" if is_admin() else "badge-expert"
    badge_txt = "ADMIN"       if is_admin() else "EXPERT"
    st.markdown(
        f"👤 **{cur_user().get('display_name', '–')}**"
        f"<span class='badge {badge_cls}'>{badge_txt}</span>",
        unsafe_allow_html=True
    )

    sb1, sb2 = st.columns(2)
    with sb1:
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.page = "settings"; st.rerun()
    with sb2:
        if st.button("🚪 Logout", use_container_width=True):
            for k in ("authenticated", "username", "role", "page"):
                st.session_state.pop(k, None)
            st.rerun()

    if is_admin() and pending_count() > 0:
        pc = pending_count()
        st.warning(f"🔔 {pc} pending change request{'s' if pc > 1 else ''}")

    st.success("📡 Live Sync Active")
    if is_admin() and st.button("🔄 Refresh Data Now", use_container_width=True):
        st.cache_data.clear()

    # ── Data Load ──────────────────────────────────────────────────────────────────
    @st.cache_data(ttl=600, show_spinner="Fetching live data…")
    def load_data() -> pd.DataFrame:
        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets",
                      "https://www.googleapis.com/auth/drive"]
            if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
                creds = Credentials.from_service_account_info(
                    json.loads(st.secrets["gspread"]["credentials"]), scopes=scopes)
            else:
                st.error("❌ Secrets not configured."); return pd.DataFrame()
            client = gspread.authorize(creds)
            sheet  = client.open("AlDawaa Tickets Data")
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
            df["Request Date"]            = dp
            df["Date Only"]               = dp.dt.date
            df["Hour"]                    = dp.dt.hour.fillna(0).astype(int)
            df["Day Name"]                = dp.dt.day_name().fillna("Unknown")
            df["Request Take (min)"]      = df["Request Take"].apply(time_to_minutes).fillna(0)
            df["Response Take (min)"]     = df["Response Take"].apply(time_to_minutes).fillna(0)
            df["First Action Take (min)"] = df["First Action Take"].apply(time_to_minutes).fillna(0)
            df["AHT (min)"]               = df["First Action Take (min)"]
            df["Is Email"] = (
                df["Is Special Request(By Email)"].astype(str).str.strip().str.lower() == "yes")
            return df
        except Exception as e:
            st.error(f"❌ Connection Error: {e}"); return pd.DataFrame()

    df_raw = load_data()
    if df_raw.empty:
        st.warning("Waiting for data…"); st.stop()

    # ── Auto-seed expert user accounts from live Assigned By values ───────────────
    EXCL_NAMES = {"mohammed shehta", "muhammad shehta", "muhammed shehta", "unassigned"}
    live_agents = [
        a.strip() for a in df_raw["Assigned By"].dropna().unique()
        if str(a).strip().lower() not in EXCL_NAMES
    ]
    changed = False
    for agent in live_agents:
        ukey = _make_ukey(agent)
        if ukey not in users():
            users()[ukey] = {
                "display_name":  agent,
                "password_hash": _hash("pass1234"),   # default password
                "role":          "expert",
                "agent_name":    agent,                # exact "Assigned By" string
            }
            changed = True
    if changed:
        _save_store()

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
        day_en = pd.to_datetime(d_from).day_name()
        st.caption(f"📅 {DAYS_AR.get(day_en, day_en)}")
    st.divider()

    # Experts can only filter their own records; admins see everyone
    aname = my_agent_name()
    if not is_admin() and aname:
        # lock the agent filter to self — no sidebar multiselect for experts
        sel_agents = [aname]
        st.info(f"🔒 Viewing data for: **{aname}**")
        sel_types = st.multiselect("Request Type Filter",
                                   sorted(df_raw["Request Type"].dropna().unique()))
    else:
        sel_agents = st.multiselect("Agent Filter",
                                    sorted(df_raw["Assigned By"].dropna().unique()))
        sel_types  = st.multiselect("Request Type Filter",
                                    sorted(df_raw["Request Type"].dropna().unique()))

# Apply global sidebar filters to base dataframe
df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_agents: df = df[df["Assigned By"].isin(sel_agents)]
if sel_types:  df = df[df["Request Type"].isin(sel_types)]

# ══════════════════════════════════════════════════════════════════════════════════
#  SETTINGS PAGE
# ══════════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "settings":
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"; st.rerun()

    # ── ADMIN SETTINGS ────────────────────────────────────────────────────────────
    if is_admin():
        st.markdown("## ⚙️ Admin Panel")
        atab1, atab2, atab3 = st.tabs(["👤 My Profile", "🔔 Change Requests", "👥 Manage Users"])

        # My Profile
        with atab1:
            st.markdown("### Update Your Profile")
            urow = users()[me()]
            st.markdown("<div class='section-card'>", unsafe_allow_html=True)
            st.markdown("**✏️ Display Name**")
            with st.form("admin_name_form"):
                new_dn = st.text_input("New Display Name", value=urow["display_name"])
                if st.form_submit_button("💾 Save Name", use_container_width=True):
                    if new_dn.strip() and new_dn.strip() != urow["display_name"]:
                        users()[me()]["display_name"] = new_dn.strip()
                        _save_store(); st.success("✅ Display name updated."); st.rerun()
                    else: st.warning("No change detected.")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div class='section-card'>", unsafe_allow_html=True)
            st.markdown("**🔑 Change Password**")
            with st.form("admin_pw_form"):
                old_pw  = st.text_input("Current Password", type="password")
                new_pw1 = st.text_input("New Password",     type="password")
                new_pw2 = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("💾 Update Password", use_container_width=True):
                    if _hash(old_pw) != urow["password_hash"]:
                        st.error("❌ Current password is incorrect.")
                    elif new_pw1 != new_pw2: st.error("❌ Passwords do not match.")
                    elif len(new_pw1) < 6:   st.error("❌ Minimum 6 characters.")
                    else:
                        users()[me()]["password_hash"] = _hash(new_pw1)
                        _save_store(); st.success("✅ Password updated.")
            st.markdown("</div>", unsafe_allow_html=True)

        # Change Requests
        with atab2:
            st.markdown("### 🔔 Pending Change Requests")
            pending = [r for r in requests() if r["status"] == "pending"]
            if not pending:
                st.info("✅ No pending requests.")
            else:
                for req in pending:
                    udata_r   = users().get(req["requester"], {})
                    udisp     = udata_r.get("display_name", req["requester"])
                    req_label = "Display Name" if req["type"] == "display_name" else "Password"
                    val_show  = req["new_value"] if req["type"] == "display_name" else "••••••••"
                    st.markdown(f"""
                    <div class='req-pending'>
                        🕐 <b>{req['ts']}</b> &nbsp;|&nbsp;
                        👤 <b>{udisp}</b> (@{req['requester']}) &nbsp;|&nbsp;
                        Wants to change <b>{req_label}</b>
                        {f"→ <b>{val_show}</b>" if req['type']=='display_name' else ""}
                    </div>""", unsafe_allow_html=True)
                    rc1, rc2, rc3 = st.columns([3, 1, 1])
                    with rc2:
                        if st.button("✅ Approve", key=f"apr_{req['id']}", use_container_width=True):
                            approve_request(req["id"])
                            st.success(f"Approved for {udisp}."); st.rerun()
                    with rc3:
                        if st.button("❌ Reject", key=f"rej_{req['id']}", use_container_width=True):
                            reject_request(req["id"]); st.warning("Rejected."); st.rerun()

            history = [r for r in requests() if r["status"] != "pending"]
            if history:
                st.divider()
                with st.expander(f"📋 Request History ({len(history)})"):
                    for req in reversed(history):
                        udisp     = users().get(req["requester"], {}).get("display_name", req["requester"])
                        req_label = "Display Name" if req["type"] == "display_name" else "Password"
                        css       = "req-approved" if req["status"] == "approved" else "req-rejected"
                        icon      = "✅" if req["status"] == "approved" else "❌"
                        st.markdown(f"<div class='{css}'>{icon} <b>{req['ts']}</b> | {udisp} — {req_label} — <b>{req['status'].upper()}</b></div>",
                                    unsafe_allow_html=True)

        # Manage Users
        with atab3:
            st.markdown("### 👥 All Users")
            st.caption("As admin you can update any account directly — no approval flow needed.")
            for uname_k, urow_k in list(users().items()):
                role_icon = "🔑" if urow_k["role"] == "admin" else "👤"
                agent_info = f" | Agent: {urow_k['agent_name']}" if urow_k.get("agent_name") else ""
                with st.expander(f"{role_icon} {urow_k['display_name']} (@{uname_k}) — {urow_k['role'].upper()}{agent_info}"):
                    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
                    with st.form(f"admin_edit_{uname_k}"):
                        eu_dn   = st.text_input("Display Name",                  value=urow_k["display_name"],            key=f"dn_{uname_k}")
                        eu_an   = st.text_input("Agent Name (Assigned By match)", value=urow_k.get("agent_name") or "",   key=f"an_{uname_k}")
                        eu_p1   = st.text_input("New Password (blank = keep)",    type="password",                         key=f"p1_{uname_k}")
                        eu_p2   = st.text_input("Confirm Password",               type="password",                         key=f"p2_{uname_k}")
                        eu_role = st.selectbox("Role", ["expert", "admin"],
                                               index=0 if urow_k["role"] != "admin" else 1,  key=f"rl_{uname_k}")
                        saved = st.form_submit_button("💾 Update", use_container_width=True)
                    if saved:
                        msgs = []
                        if eu_dn.strip() and eu_dn.strip() != urow_k["display_name"]:
                            users()[uname_k]["display_name"] = eu_dn.strip(); msgs.append("Name updated.")
                        an_val = eu_an.strip() if eu_an.strip() else None
                        if an_val != urow_k.get("agent_name"):
                            users()[uname_k]["agent_name"] = an_val; msgs.append("Agent link updated.")
                        if eu_role != urow_k["role"]:
                            users()[uname_k]["role"] = eu_role; msgs.append("Role updated.")
                        if eu_p1:
                            if eu_p1 != eu_p2:   st.error("❌ Passwords don't match.")
                            elif len(eu_p1) < 6: st.error("❌ Minimum 6 characters.")
                            else:
                                users()[uname_k]["password_hash"] = _hash(eu_p1); msgs.append("Password updated.")
                        if msgs: _save_store(); st.success("✅ " + " ".join(msgs)); st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    # ── EXPERT SETTINGS ───────────────────────────────────────────────────────────
    else:
        st.markdown("## ⚙️ My Profile Settings")
        urow = users()[me()]

        my_pend = [r for r in requests() if r["requester"] == me() and r["status"] == "pending"]
        my_done = [r for r in requests() if r["requester"] == me() and r["status"] != "pending"]

        if my_pend:
            st.markdown("**🕐 Your Pending Requests:**")
            for req in my_pend:
                lbl = "Display Name" if req["type"] == "display_name" else "Password"
                st.markdown(f"<div class='req-pending'>🕐 <b>{req['ts']}</b> — <b>{lbl}</b> change awaiting admin approval.</div>",
                            unsafe_allow_html=True)
        for req in my_done[-3:]:
            lbl  = "Display Name" if req["type"] == "display_name" else "Password"
            css  = "req-approved" if req["status"] == "approved" else "req-rejected"
            icon = "✅" if req["status"] == "approved" else "❌"
            st.markdown(f"<div class='{css}'>{icon} <b>{req['ts']}</b> — <b>{lbl}</b> request was <b>{req['status'].upper()}</b>.</div>",
                        unsafe_allow_html=True)

        st.divider()
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("### ✏️ Request Display Name Change")
        st.caption("Submitted requests are sent to the admin for approval before taking effect.")
        already_dn = any(r["requester"] == me() and r["type"] == "display_name" and r["status"] == "pending"
                         for r in requests())
        if already_dn:
            st.warning("⏳ You already have a pending name change request.")
        else:
            with st.form("expert_name_form"):
                req_name = st.text_input("New Display Name", placeholder=urow["display_name"])
                if st.form_submit_button("📤 Submit Request", use_container_width=True):
                    if not req_name.strip():                         st.error("Name cannot be empty.")
                    elif req_name.strip() == urow["display_name"]:  st.warning("That is already your name.")
                    else:
                        push_request(me(), "display_name", req_name.strip())
                        st.success("✅ Request submitted! Waiting for admin approval."); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("### 🔑 Change Password")
        st.caption("You can change your own password directly — no admin approval needed.")
        with st.form("expert_pw_direct"):
            cur_pw  = st.text_input("Current Password", type="password")
            new_pw1 = st.text_input("New Password",     type="password")
            new_pw2 = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("💾 Change Password", use_container_width=True):
                if _hash(cur_pw) != urow["password_hash"]:
                    st.error("❌ Current password is incorrect.")
                elif new_pw1 != new_pw2:  st.error("❌ Passwords do not match.")
                elif len(new_pw1) < 6:    st.error("❌ Minimum 6 characters.")
                else:
                    users()[me()]["password_hash"] = _hash(new_pw1)
                    _save_store(); st.success("✅ Password changed successfully.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()

# ══════════════════════════════════════════════════════════════════════════════════
#  DASHBOARD HEADER
# ══════════════════════════════════════════════════════════════════════════════════
caption_text = (
    f"🔍 {d_from} ({DAYS_AR.get(pd.to_datetime(d_from).day_name(), '')})"
    if d_from == d_to else f"🔍 {d_from} → {d_to}"
)
st.markdown("## 💊 In-Store Requests Dashboard")
st.caption(caption_text)

# ── Tab 1 always operates on full-team data (date + type filters only, no agent lock) ──
df_tab1 = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
if sel_types: df_tab1 = df_tab1[df_tab1["Request Type"].isin(sel_types)]

tab1, tab2 = st.tabs(["📈 Tab 1: Operational Insights",
                       "👥 Tab 2: Team Performance and KPIs"])

# ══════════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Operational Insights  (ALL roles see full team data — no expert restriction)
# ══════════════════════════════════════════════════════════════════════════════════
with tab1:
    c1, c2 = st.columns(2)
    with c1: esc  = st.checkbox("🔥 Show Escalated Cases Only",    value=False, key="t1_esc")
    with c2: nesc = st.checkbox("🟢 Show Non-Escalated Cases Only", value=False, key="t1_nesc")

    # Always use full team data — Tab 1 is not role-restricted
    dfm = df_tab1.copy()
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

    a, b, c_, d_, e, f_ = st.columns(6)
    a.markdown(kpi_colored("Total Tickets",      f"{total:,}", "card-total"),     unsafe_allow_html=True)
    b.markdown(kpi_colored("Closed Completed",   f"{ok:,}",    "card-completed"), unsafe_allow_html=True)
    c_.markdown(kpi_colored("Closed with Issue", f"{issue:,}", "card-issue"),     unsafe_allow_html=True)
    d_.markdown(kpi_colored("Avg Response (FRT)", h_frt,       "card-frt"),       unsafe_allow_html=True)
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
        t_ord = ["Under 15 Mins","15-30 Mins","30-45 Mins","45-60 Mins","Over 1 Hour"]
        c_ord = ["Response Time","Service Resolution"]
        sb_df["SLA Category"] = pd.Categorical(sb_df["SLA Category"], categories=c_ord, ordered=True)
        sb_df["SLA Tier"]     = pd.Categorical(sb_df["SLA Tier"],     categories=t_ord, ordered=True)
        sb_df = sb_df.sort_values(["SLA Category","SLA Tier"]).reset_index(drop=True)
        sb_df["SLA Category"] = sb_df["SLA Category"].astype(str)
        sb_df["SLA Tier"]     = sb_df["SLA Tier"].astype(str)
        fig_sb = px.sunburst(
            sb_df, path=["SLA Category","SLA Tier"], values="Tickets", color="SLA Tier",
            color_discrete_map={"Under 15 Mins":"#2ea44f","15-30 Mins":"#2188ff",
                                "30-45 Mins":"#bc8cff","45-60 Mins":"#f9c513","Over 1 Hour":"#ea4a5a"},
            branchvalues="total")
        fig_sb.update_traces(sort=False, textinfo="label+percent parent",
                             hovertemplate="<b>%{label}</b><br>Tickets: %{value:,}<br>%{percentParent:.1%}")
        fig_sb.update_layout(**THEME, height=520,
                             title_text="SLA Compliance & Time Tiers Breakdown",
                             title_font_size=18, title_font_color="#e6edf3", hoverlabel_font_size=14)
        st.plotly_chart(fig_sb, use_container_width=True)

    st.divider()

    if not dfm.empty:
        hrs = dfm.groupby("Hour").agg(
            Volume=("Request ID","count"), AR=("Response Take (min)","mean")).reset_index()
        hrs = hrs.set_index("Hour").reindex(range(24)).fillna(0).reset_index()
        hl  = ["12 AM" if h == 0 else ("12 PM" if h == 12 else
               (f"{h} AM" if h < 12 else f"{h-12} PM")) for h in hrs["Hour"]]
        hrs["Hour Label"] = hl
        fig_r = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"], y=hrs["Volume"], name="Volume",
                                   fill="tozeroy", line=dict(color="#58a6ff", width=2)), secondary_y=False)
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"], y=hrs["AR"], name="FRT (Avg Response)",
                                   mode="lines+markers", line=dict(color="#f0883e", width=3, shape="spline")),
                        secondary_y=True)
        fig_r.update_xaxes(type="category", categoryorder="array", categoryarray=hl)
        fig_r.update_layout(**THEME, height=450, hovermode="x unified",
                            legend_orientation="h", legend_y=1.1,
                            title_text="Hourly Performance: Ticket Volume vs Avg Response Time (FRT)",
                            title_font_size=18, title_font_color="#e6edf3", hoverlabel_font_size=14)
        st.plotly_chart(fig_r, use_container_width=True)

    st.info(f"⏱️ **Avg Service Resolution Time (TAT):** {h_tat} (HH:MM:SS) Per Ticket")
    st.write("")
    st.markdown("### 📋 Detailed Request Type Breakdown & Handling SLA")
    if not dfm.empty:
        bkd = dfm.groupby("Request Type").agg(
            Count=("Request ID","count"),
            Avg_S=("Request Take (min)","mean"),
            Avg_A=("AHT (min)","mean")).reset_index()
        bkd["Pct of Total"] = (bkd["Count"] / total * 100).round(1).astype(str) + "%"
        bkd["Avg AHT"]     = bkd["Avg_A"].apply(fmt_m)
        bkd["Avg Service"] = bkd["Avg_S"].apply(fmt_m)
        st.dataframe(
            bkd[["Request Type","Count","Pct of Total","Avg AHT","Avg Service"]]
            .sort_values("Count", ascending=False),
            hide_index=True, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Team Performance and KPIs  (role-restricted)
# ══════════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 👥 Team Performance and KPIs")
    st.write("")

    t2c1, t2c2 = st.columns(2)
    with t2c1: t2e  = st.checkbox("🔥 Show Escalated Cases Only",    value=False, key="t2_esc")
    with t2c2: t2ne = st.checkbox("🟢 Show Non-Escalated Cases Only", value=False, key="t2_nesc")

    # ── Two working sets for Tab 2 ─────────────────────────────────────────────────
    # df_t2_full: full team, date+type filtered (used to compute ALL-agent scorecard
    #             so the Team AVG baseline always reflects the real team average)
    # df_t2_kpi : expert's own slice (used only for the KPI cards when role=expert)
    df_t2_full = df_tab1.copy()   # full team, already date+type filtered
    if t2e  and not t2ne: df_t2_full = df_t2_full[df_t2_full["Is Email"] == True]
    elif t2ne and not t2e: df_t2_full = df_t2_full[df_t2_full["Is Email"] == False]

    aname = my_agent_name()

    # KPI cards → expert sees ONLY their own metrics; admin sees full team
    if not is_admin() and aname:
        df_kpi = df_t2_full[df_t2_full["Assigned By"] == aname].copy()
    else:
        df_kpi = df_t2_full.copy()

    # Alias used for scorecard building (always full team so AVG is accurate)
    df_t2 = df_t2_full

    kpi_ss  = df_kpi["Status"].astype(str).str.strip()
    kpi_ok  = df_kpi[kpi_ss.str.contains("Closed", na=False, case=False) &
                     ~kpi_ss.str.contains("issue", na=False, case=False)].shape[0]
    kpi_iss = df_kpi[kpi_ss.str.contains("Closed", na=False, case=False) &
                      kpi_ss.str.contains("issue", na=False, case=False)].shape[0]

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.markdown(kpi_colored("Total Tickets",      f"{len(df_kpi):,}", "card-total"),     unsafe_allow_html=True)
    k2.markdown(kpi_colored("Closed Completed",   f"{kpi_ok:,}",      "card-completed"), unsafe_allow_html=True)
    k3.markdown(kpi_colored("Closed with Issue",  f"{kpi_iss:,}",     "card-issue"),     unsafe_allow_html=True)
    k4.markdown(kpi_colored("Avg Response (FRT)",
                fmt_m(df_kpi["Response Take (min)"].mean() if not df_kpi.empty else 0), "card-frt"), unsafe_allow_html=True)
    k5.markdown(kpi_colored("Avg Handling (AHT)",
                fmt_m(df_kpi["AHT (min)"].mean()           if not df_kpi.empty else 0), "card-aht"), unsafe_allow_html=True)
    k6.markdown(kpi_colored("Avg Service (TAT)",
                fmt_m(df_kpi["Request Take (min)"].mean()   if not df_kpi.empty else 0), "card-tat"), unsafe_allow_html=True)

    st.write(""); st.divider()
    st.markdown("### 📊 Expert Performance Scorecard")

    # ── Build full scorecard from all non-excluded agents ─────────────────────────
    EXCL = ["mohammed shehta","muhammad shehta","muhammed shehta","unassigned"]
    df_sc = df_t2[~df_t2["Assigned By"].astype(str).str.strip().str.lower().isin(EXCL)].copy()

    if df_sc.empty:
        st.warning("No data available for the selected filters.")
    else:
        # ── Compute all agent metrics ─────────────────────────────────────────────
        rtl = df_sc["Request Type"].astype(str).str.lower()
        df_sc["_jhah"]  = rtl.str.contains("jhah", na=False)
        df_sc["_rfb"]   = rtl.str.contains("report|feedback", na=False)
        df_sc["_c_ok"]  = (df_sc["Status"].astype(str).str.contains("Closed", case=False, na=False) &
                           ~df_sc["Status"].astype(str).str.contains("issue",  case=False, na=False))
        df_sc["_c_all"] = df_sc["Status"].astype(str).str.contains("Closed", case=False, na=False)

        # Working Days = days where agent handled > 15 tickets
        dc = (df_sc.groupby(["Assigned By","Date Only"])["Request ID"]
              .count().reset_index(name="_n"))
        active_days = (dc[dc["_n"] > 15].groupby("Assigned By")["Date Only"]
                       .nunique().rename("Working Days"))

        grp = df_sc.groupby("Assigned By")
        sc  = pd.DataFrame(index=grp.groups.keys())
        sc.index.name = "Assigned By"
        sc["Working Days"]         = active_days.reindex(sc.index).fillna(0).astype(int)
        sc["Tickets Count"]        = grp["Request ID"].count()
        sc["JHAH Requests"]        = grp["_jhah"].sum().astype(int)
        sc["Reporting & Feedback"] = grp["_rfb"].sum().astype(int)
        sc["Email Counts"]         = grp["Is Email"].sum().astype(int)

        # % Achievement vs full team average (always computed over all agents)
        tavg = sc["Tickets Count"].mean()
        sc["% Achievement from Target"] = (
            (sc["Tickets Count"] / tavg * 100).round(1).astype(str) + "%"
            if tavg > 0 else "0.0%")
        avg_svc = grp["Request Take (min)"].mean()
        sc["Service Time"]    = avg_svc.apply(fmt_m)
        ca = grp["_c_all"].sum(); co = grp["_c_ok"].sum()
        sq = (co / ca.replace(0, np.nan) * 100).round(1)
        sc["Service Quality"] = sq.fillna(0).astype(str) + "%"
        sc = sc.reset_index().rename(columns={"Assigned By": "Expert"})

        # Apply manual admin overrides
        for i, row in sc.iterrows():
            ov = overrides().get(row["Expert"], {})
            for col, val in ov.items():
                sc.at[i, col] = val

        # ── Team AVG baseline row ─────────────────────────────────────────────────
        def _pct_avg(s):
            return f"{s.astype(str).str.rstrip('%').astype(float).mean():.1f}%"

        team_row = {
            "Expert":                    "🏆 Team AVG",
            "Working Days":              round(sc["Working Days"].astype(float).mean(), 1),
            "Tickets Count":             round(sc["Tickets Count"].astype(float).mean(), 1),
            "JHAH Requests":             round(sc["JHAH Requests"].astype(float).mean(), 1),
            "Reporting & Feedback":      round(sc["Reporting & Feedback"].astype(float).mean(), 1),
            "Email Counts":              round(sc["Email Counts"].astype(float).mean(), 1),
            "% Achievement from Target": "100.0%",
            "Service Time":              fmt_m(avg_svc.mean()),
            "Service Quality":           _pct_avg(sc["Service Quality"]),
        }

        # ── TL row (manual, admin only) ───────────────────────────────────────────
        tl_ov  = overrides().get("__TL__", {})
        tl_row = {
            "Expert":                    "👑 Mohammed Shehta (TL)",
            "Working Days":              tl_ov.get("Working Days", 0),
            "Tickets Count":             tl_ov.get("Tickets Count", 0),
            "JHAH Requests":             tl_ov.get("JHAH Requests", 0),
            "Reporting & Feedback":      tl_ov.get("Reporting & Feedback", 0),
            "Email Counts":              tl_ov.get("Email Counts", 0),
            "% Achievement from Target": tl_ov.get("% Achievement from Target", "0.0%"),
            "Service Time":              tl_ov.get("Service Time", "00:00:00"),
            "Service Quality":           tl_ov.get("Service Quality", "0.0%"),
        }

        # ── Role-based row visibility ─────────────────────────────────────────────
        # Admin  → Team AVG + all experts + TL row
        # Expert → Team AVG + their own row only  (no TL row)
        if is_admin():
            sc_final = pd.concat(
                [pd.DataFrame([team_row]), sc, pd.DataFrame([tl_row])],
                ignore_index=True)
        else:
            my_row = sc[sc["Expert"] == aname] if aname else pd.DataFrame()
            if my_row.empty and aname:
                st.warning(f"⚠️ No data found for **{aname}** in the selected period.")
            sc_final = pd.concat([pd.DataFrame([team_row]), my_row], ignore_index=True)

        # ── Top-performer metrics (computed over all agents for ranking) ──────────
        agent_only = sc.copy()
        agent_only["_tc_num"] = pd.to_numeric(agent_only["Tickets Count"], errors="coerce")
        agent_only["_sq_num"] = agent_only["Service Quality"].astype(str).str.rstrip("%").apply(
            pd.to_numeric, errors="coerce")
        top3_tc       = set(agent_only.nlargest(3, "_tc_num")["Expert"].tolist())
        top_sq        = set(agent_only.nlargest(1, "_sq_num")["Expert"].tolist())
        top_performers = top3_tc | top_sq
        ranked_agents  = agent_only.sort_values("_tc_num", ascending=False)["Expert"].tolist()

        def _medal(expert: str):
            return ["🥇","🥈","🥉"][ranked_agents.index(expert)] if expert in ranked_agents[:3] else None

        def _row_meta(expert: str):
            """Return (row_bg_css, left_accent_hex, badge_html)."""
            if expert == "🏆 Team AVG":
                return (
                    "background:linear-gradient(90deg,#1a003a,#22004e);", "#e040fb",
                    "<span style='background:#2a0050;border:1px solid #e040fb;color:#f580ff;"
                    "border-radius:6px;padding:2px 10px;font-size:.68rem;font-weight:700;"
                    "letter-spacing:.08em'>BASELINE</span>")
            if expert == "👑 Mohammed Shehta (TL)":
                return (
                    "background:linear-gradient(90deg,#001a38,#002050);", "#00e5ff",
                    "<span style='background:#001830;border:1px solid #00e5ff;color:#40f8ff;"
                    "border-radius:6px;padding:2px 10px;font-size:.68rem;font-weight:700;"
                    "letter-spacing:.08em'>TEAM LEAD</span>")
            badge_parts = []
            if is_admin():
                medal = _medal(expert)
                if medal:
                    mc = {"🥇":("#332000","#ffd740","#ffe57f"),
                          "🥈":("#1a1a2a","#90a4ae","#cfd8dc"),
                          "🥉":("#1e0e00","#ff6d00","#ffab40")}
                    bg, bd, fc = mc.get(medal, ("#111","#fff","#fff"))
                    badge_parts.append(
                        f"<span style='background:{bg};border:1px solid {bd};color:{fc};"
                        f"border-radius:6px;padding:2px 9px;font-size:.68rem;font-weight:700;"
                        f"margin-left:5px'>{medal} #{ranked_agents.index(expert)+1} VOL</span>")
                if expert in top_sq:
                    badge_parts.append(
                        "<span style='background:#001a00;border:1px solid #76ff03;color:#aaff57;"
                        "border-radius:6px;padding:2px 9px;font-size:.68rem;font-weight:700;"
                        "margin-left:4px'>⭐ QUALITY</span>")
            bg_style = ("background:linear-gradient(90deg,#0a1e00,#102800);"
                        if expert in top_performers and is_admin() else "")
            left_col = "#76ff03" if expert in top_performers and is_admin() else "#3d1060"
            return bg_style, left_col, " ".join(badge_parts)

        # ── Column header accents ─────────────────────────────────────────────────
        COL_COLORS = {
            "Expert":               "#e040fb",
            "Working Days":         "#00e5ff",
            "Tickets Count":        "#ffd740",
            "JHAH Requests":        "#ff6090",
            "Reporting & Feedback": "#76ff03",
            "Email Counts":         "#6ea8ff",
            "% Achievement":        "#ff9e40",
            "Service Time":         "#c77dff",
            "Service Quality":      "#40f8ff",
        }
        COLS = list(COL_COLORS.keys())

        header_cells = "".join(
            f"<th style='padding:11px 15px;text-align:left;font-size:.72rem;"
            f"letter-spacing:.1em;text-transform:uppercase;"
            f"color:{COL_COLORS[c]};font-weight:700;"
            f"border-bottom:2px solid {COL_COLORS[c]}44;white-space:nowrap'>{c}</th>"
            for c in COLS)

        rows_html = ""
        for _, row in sc_final.iterrows():
            expert_raw = str(row["Expert"])
            bg_str, left_col, badge_html = _row_meta(expert_raw)

            # % Achievement pill
            ach_str = str(row.get("% Achievement from Target","0%"))
            try:    ach_num = float(ach_str.rstrip("%"))
            except: ach_num = 0
            if ach_num >= 120: ach_bg,ach_bd,ach_fc = "#1a2e00","#76ff03","#aaff57"
            elif ach_num >= 100: ach_bg,ach_bd,ach_fc = "#001530","#2979ff","#6ea8ff"
            elif ach_num >= 80:  ach_bg,ach_bd,ach_fc = "#1e1000","#ff6d00","#ff9e40"
            else:                ach_bg,ach_bd,ach_fc = "#200010","#f50057","#ff6090"
            ach_pill = (f"<span style='background:{ach_bg};border:1px solid {ach_bd};"
                        f"color:{ach_fc};border-radius:20px;padding:3px 11px;"
                        f"font-weight:700;font-size:.82rem'>{ach_str}</span>")

            # Service Quality pill
            sq_str = str(row.get("Service Quality","0%"))
            try:    sq_num = float(sq_str.rstrip("%"))
            except: sq_num = 0
            if sq_num >= 90:   sq_bg,sq_bd,sq_fc = "#001e00","#76ff03","#aaff57"
            elif sq_num >= 75: sq_bg,sq_bd,sq_fc = "#001530","#00e5ff","#40f8ff"
            elif sq_num >= 60: sq_bg,sq_bd,sq_fc = "#1e1000","#ffd740","#ffe57f"
            else:              sq_bg,sq_bd,sq_fc = "#200010","#f50057","#ff6090"
            sq_pill = (f"<span style='background:{sq_bg};border:1px solid {sq_bd};"
                       f"color:{sq_fc};border-radius:20px;padding:3px 11px;"
                       f"font-weight:700;font-size:.82rem'>{sq_str}</span>")

            # Service Time mono cell
            svc_time = str(row.get("Service Time","00:00:00"))
            svc_cell = (f"<span style='font-family:monospace;color:#c77dff;"
                        f"font-size:.84rem;letter-spacing:.05em'>{svc_time}</span>")

            is_special = expert_raw in ("🏆 Team AVG","👑 Mohammed Shehta (TL)")
            name_fw    = "700" if is_special else "400"
            name_color = ("#f580ff" if expert_raw == "🏆 Team AVG" else
                          "#40f8ff" if expert_raw == "👑 Mohammed Shehta (TL)" else "#e8d5ff")

            def cell(val, accent=None):
                c = accent if accent else "#b898d8"
                return (f"<td style='padding:10px 15px;border-bottom:1px solid #2a0550;"
                        f"font-size:.84rem;color:{c}'>{val}</td>")

            tc_val = row.get("Tickets Count","—")
            try:    tc_disp = f"{int(float(str(tc_val).replace(',',''))):,}"
            except: tc_disp = str(tc_val)

            rows_html += (
                f"<tr style='{bg_str}border-left:3px solid {left_col};transition:background .15s' "
                f"onmouseover=\"this.style.background='rgba(160,60,255,.08)'\" "
                f"onmouseout=\"this.style.background=''\">"
                + f"<td style='padding:10px 15px;border-bottom:1px solid #2a0550;"
                  f"color:{name_color};font-weight:{name_fw};font-size:.88rem'>"
                  f"{expert_raw} {badge_html}</td>"
                + cell(row.get("Working Days","—"), "#00e5ff" if not is_special else None)
                + cell(tc_disp,                     "#ffd740" if not is_special else None)
                + cell(row.get("JHAH Requests","—"), "#ff6090")
                + cell(row.get("Reporting & Feedback","—"), "#76ff03")
                + cell(row.get("Email Counts","—"), "#6ea8ff")
                + f"<td style='padding:10px 15px;border-bottom:1px solid #2a0550'>{ach_pill}</td>"
                + f"<td style='padding:10px 15px;border-bottom:1px solid #2a0550'>{svc_cell}</td>"
                + f"<td style='padding:10px 15px;border-bottom:1px solid #2a0550'>{sq_pill}</td>"
                + "</tr>"
            )

        table_html = f"""
        <div style='overflow-x:auto;border-radius:14px;border:1px solid #4a1080;
          box-shadow:0 0 36px rgba(160,0,255,.1),0 6px 28px rgba(0,0,0,.45);margin-bottom:1rem;'>
        <table style='width:100%;border-collapse:collapse;
          background:linear-gradient(160deg,#0e0025 0%,#0a001e 100%);'>
            <thead>
              <tr style='background:linear-gradient(90deg,#1a003a,#26004e);border-bottom:2px solid #6020b0'>
                {header_cells}
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table></div>
        <div style='font-size:.72rem;color:#7a50a0;display:flex;flex-wrap:wrap;gap:12px;margin-top:4px'>
            {("🥇🥈🥉 Top 3 volume &nbsp;|&nbsp; ⭐ Best quality &nbsp;|&nbsp;" if is_admin() else "")}
            <span style='color:#aaff57'>■ ≥120% achievement</span>
            <span style='color:#6ea8ff'>■ ≥100%</span>
            <span style='color:#ff9e40'>■ ≥80%</span>
            <span style='color:#ff6090'>■ &lt;80%</span>
        </div>"""

        # ── Render table ──────────────────────────────────────────────────────────
        if not is_admin():
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.info("✏️ **Admin Mode** — Full team scorecard. Use the editor below to override any agent's KPI values.")
            st.markdown(table_html, unsafe_allow_html=True)

            # ── Admin KPI Override Editor ─────────────────────────────────────────
            st.divider()
            st.markdown("#### ✏️ Manual KPI Override — Per Agent Editor")
            agent_opts = list(sc["Expert"]) + ["Mohammed Shehta (TL)"]
            sel_agent  = st.selectbox("Choose agent to edit", agent_opts, key="agent_sel")

            if sel_agent == "Mohammed Shehta (TL)":
                akey = "__TL__"
                cur  = overrides().get(akey, {})
                dv   = {"Working Days":0,"Tickets Count":0,"JHAH Requests":0,
                        "Reporting & Feedback":0,"Email Counts":0,
                        "% Achievement from Target":"0.0%",
                        "Service Time":"00:00:00","Service Quality":"0.0%"}
            else:
                akey = sel_agent
                cur  = overrides().get(akey, {})
                ar   = sc[sc["Expert"] == sel_agent]
                if not ar.empty:
                    r  = ar.iloc[0]
                    dv = {"Working Days":              int(r["Working Days"]),
                          "Tickets Count":             int(r["Tickets Count"]),
                          "JHAH Requests":             int(r["JHAH Requests"]),
                          "Reporting & Feedback":      int(r["Reporting & Feedback"]),
                          "Email Counts":              int(r["Email Counts"]),
                          "% Achievement from Target": str(r["% Achievement from Target"]),
                          "Service Time":              str(r["Service Time"]),
                          "Service Quality":           str(r["Service Quality"])}
                else:
                    dv = {"Working Days":0,"Tickets Count":0,"JHAH Requests":0,
                          "Reporting & Feedback":0,"Email Counts":0,
                          "% Achievement from Target":"0.0%",
                          "Service Time":"00:00:00","Service Quality":"0.0%"}

            def gv(k): return cur.get(k, dv[k])

            with st.form(f"form_{sel_agent}"):
                st.markdown(f"**Editing: {sel_agent}**")
                fc1, fc2, fc3, fc4 = st.columns(4)
                with fc1:
                    nwd  = st.number_input("Working Days",         min_value=0, value=int(gv("Working Days")),        step=1)
                    ntc  = st.number_input("Tickets Count",        min_value=0, value=int(gv("Tickets Count")),       step=1)
                with fc2:
                    njh  = st.number_input("JHAH Requests",        min_value=0, value=int(gv("JHAH Requests")),       step=1)
                    nrfb = st.number_input("Reporting & Feedback", min_value=0, value=int(gv("Reporting & Feedback")), step=1)
                with fc3:
                    nem  = st.number_input("Email Counts",         min_value=0, value=int(gv("Email Counts")),        step=1)
                    nach = st.text_input("% Achievement from Target", value=str(gv("% Achievement from Target")))
                with fc4:
                    nst  = st.text_input("Service Time (HH:MM:SS)", value=str(gv("Service Time")))
                    nsq  = st.text_input("Service Quality (%)",      value=str(gv("Service Quality")))
                sc_col, rc_col = st.columns(2)
                with sc_col: do_save  = st.form_submit_button("💾 Save Override", use_container_width=True)
                with rc_col: do_reset = st.form_submit_button("🔄 Reset to Auto", use_container_width=True)

            if do_save:
                overrides()[akey] = {
                    "Working Days":nwd,"Tickets Count":ntc,"JHAH Requests":njh,
                    "Reporting & Feedback":nrfb,"Email Counts":nem,
                    "% Achievement from Target":nach,"Service Time":nst,"Service Quality":nsq,
                }
                _save_store()
                st.success(f"✅ Override saved for **{sel_agent}**."); st.rerun()

            if do_reset:
                overrides().pop(akey, None); _save_store()
                st.success(f"🔄 Reverted to auto values for **{sel_agent}**."); st.rerun()

            if overrides():
                st.divider()
                with st.expander(f"🗂️ Active Overrides ({len(overrides())} agents)"):
                    for ak, av in overrides().items():
                        st.markdown(f"**{'Mohammed Shehta (TL)' if ak == '__TL__' else ak}**")
                        st.json(av)
                if st.button("🗑️ Clear ALL Overrides", type="secondary"):
                    st.session_state.store["overrides"] = {}
                    _save_store(); st.rerun()
