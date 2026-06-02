import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json, hashlib, time, os, pathlib

# ══════════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG  (must be first Streamlit call)
# ══════════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="In-Store Requests Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════════
#  PERSISTENCE — all mutable state is saved to a single JSON file next to this
#  script so it survives Streamlit server restarts.
# ══════════════════════════════════════════════════════════════════════════════════
_DATA_FILE = pathlib.Path(__file__).parent / ".dashboard_data.json"

def _load_store() -> dict:
    if _DATA_FILE.exists():
        try:
            return json.loads(_DATA_FILE.read_text())
        except Exception:
            pass
    # ── default factory ───────────────────────────────────────────────────────
    return {
        "users": {
            "admin": {
                "display_name":  "Mohammed Shehta",
                "password_hash": _hash("admin123"),
                "role":          "admin",
            },
            "team": {
                "display_name":  "Team Viewer",
                "password_hash": _hash("team2024"),
                "role":          "viewer",
            },
        },
        "requests":  [],   # change-request queue
        "overrides": {},   # KPI manual overrides
    }

def _save_store():
    _DATA_FILE.write_text(json.dumps(st.session_state.store, indent=2))

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# ══════════════════════════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── base ── */
.stApp{background:#0d1117;color:#e6edf3;}
[data-testid="stSidebar"]{background:#0d1117;border-right:1px solid #21262d;}

/* ── KPI cards ── */
.kpi-container{border-radius:14px;padding:1.2rem .8rem;text-align:center;
  min-height:110px;display:flex;flex-direction:column;
  justify-content:center;margin-bottom:1rem;}
.kpi-label{font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;
  color:#8b949e;margin-bottom:.4rem;font-weight:600;}
.kpi-value{font-size:1.5rem;font-weight:800;}
.card-total    {background:#111a2e;border:1px solid #58a6ff;color:#58a6ff;}
.card-completed{background:#12221b;border:1px solid #3fb950;color:#3fb950;}
.card-issue    {background:#261f12;border:1px solid #d29922;color:#d29922;}
.card-frt      {background:#2b1c11;border:1px solid #f0883e;color:#f0883e;}
.card-aht      {background:#221230;border:1px solid #bc8cff;color:#bc8cff;}
.card-tat      {background:#111a2e;border:1px solid #58a6ff;color:#58a6ff;}

/* ── login card ── */
.login-wrap{max-width:430px;margin:5rem auto 0;padding:2.5rem 2rem;
  background:#161b22;border:1px solid #30363d;border-radius:16px;}
.login-title{font-size:1.6rem;font-weight:800;text-align:center;
  margin-bottom:.3rem;color:#e6edf3;}
.login-sub{font-size:.85rem;text-align:center;color:#8b949e;margin-bottom:1.6rem;}

/* ── role badges ── */
.badge{display:inline-block;font-size:.68rem;border-radius:6px;
  padding:2px 8px;margin-left:6px;font-weight:700;letter-spacing:.06em;}
.badge-admin {background:#1f2d1f;border:1px solid #3fb950;color:#3fb950;}
.badge-viewer{background:#1a2236;border:1px solid #58a6ff;color:#58a6ff;}

/* ── request status banners ── */
.req-pending {background:#1f1f00;border:1px solid #d29922;border-radius:10px;
  padding:.7rem 1rem;margin-bottom:.8rem;color:#d29922;font-size:.88rem;}
.req-approved{background:#0d2218;border:1px solid #3fb950;border-radius:10px;
  padding:.7rem 1rem;margin-bottom:.8rem;color:#3fb950;font-size:.88rem;}
.req-rejected{background:#2a0d0d;border:1px solid #f85149;border-radius:10px;
  padding:.7rem 1rem;margin-bottom:.8rem;color:#f85149;font-size:.88rem;}

/* ── section card ── */
.section-card{background:#161b22;border:1px solid #30363d;border-radius:12px;
  padding:1.4rem 1.6rem;margin-bottom:1.2rem;}
</style>
""", unsafe_allow_html=True)

THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9",
    margin=dict(l=10,r=10,t=50,b=10)
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
    st.session_state.page = "dashboard"   # dashboard | settings

# ── store shortcuts ────────────────────────────────────────────────────────────────
def users()     -> dict: return st.session_state.store["users"]
def requests()  -> list: return st.session_state.store["requests"]
def overrides() -> dict: return st.session_state.store["overrides"]
def me()        -> str:  return st.session_state.username
def is_admin()  -> bool: return st.session_state.role == "admin"
def cur_user()  -> dict: return users().get(me(), {})

def pending_count() -> int:
    return sum(1 for r in requests() if r["status"] == "pending")

def my_requests(uname: str, status_filter=None) -> list:
    return [r for r in requests()
            if r["requester"] == uname and
            (status_filter is None or r["status"] == status_filter)]

def push_request(uname: str, rtype: str, new_value: str):
    requests().append({
        "id":        int(time.time() * 1000),
        "requester": uname,
        "type":      rtype,       # "display_name" | "password"
        "new_value": new_value,
        "status":    "pending",
        "ts":        time.strftime("%Y-%m-%d %H:%M"),
    })
    _save_store()

def approve_request(req_id: int):
    for r in requests():
        if r["id"] == req_id and r["status"] == "pending":
            # apply change
            uname = r["requester"]
            if r["type"] == "display_name":
                users()[uname]["display_name"] = r["new_value"]
            elif r["type"] == "password":
                users()[uname]["password_hash"] = _hash(r["new_value"])
            r["status"] = "approved"
            _save_store()
            return True
    return False

def reject_request(req_id: int):
    for r in requests():
        if r["id"] == req_id and r["status"] == "pending":
            r["status"] = "rejected"
            _save_store()
            return True
    return False

# ══════════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════════
def kpi_colored(label, value, cls):
    return (f'<div class="kpi-container {cls}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div></div>')

def time_to_minutes(s):
    try:
        p = str(s).strip().split(":")
        return int(p[0])*60 + int(p[1])
    except: return 0

def fmt_m(v):
    if pd.isna(v) or v<=0: return "00:00:00"
    t = int(round(v*60))
    return f"{t//3600:02d}:{(t%3600)//60:02d}:{t%60:02d}"

def assign_time_tier(m):
    if m<=15: return "Under 15 Mins"
    if m<=30: return "15-30 Mins"
    if m<=45: return "30-45 Mins"
    if m<=60: return "45-60 Mins"
    return "Over 1 Hour"

DAYS_AR = {
    "Saturday":"السبت","Sunday":"الأحد","Monday":"الإثنين",
    "Tuesday":"الثلاثاء","Wednesday":"الأربعاء",
    "Thursday":"الخميس","Friday":"الجمعة"
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
    _, lc, _ = st.columns([1,1.4,1])
    with lc:
        inp_u = st.text_input("Username", placeholder="Enter username", key="li_u")
        inp_p = st.text_input("Password", type="password", placeholder="Enter password", key="li_p")
        if st.button("🔐 Login", use_container_width=True):
            uname = inp_u.strip().lower()
            udata = users().get(uname)
            if udata and udata["password_hash"] == _hash(inp_p):
                st.session_state.authenticated = True
                st.session_state.username      = uname
                st.session_state.role          = udata["role"]
                st.session_state.page          = "dashboard"
                st.rerun()
            else:
                st.error("❌ Incorrect username or password.")
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 💊 Navigation & Filters")

    badge_cls = "badge-admin" if is_admin() else "badge-viewer"
    badge_txt = "ADMIN"       if is_admin() else "VIEWER"
    st.markdown(
        f"👤 **{cur_user().get('display_name','–')}** "
        f"<span class='badge {badge_cls}'>{badge_txt}</span>",
        unsafe_allow_html=True
    )

    sb1, sb2 = st.columns(2)
    with sb1:
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()
    with sb2:
        if st.button("🚪 Logout", use_container_width=True):
            for k in ("authenticated","username","role","page"):
                st.session_state.pop(k, None)
            st.rerun()

    if is_admin() and pending_count() > 0:
        pc = pending_count()
        st.warning(f"🔔 {pc} pending change request{'s' if pc>1 else ''}")

    st.success("📡 Live Sync Active")
    if is_admin() and st.button("🔄 Refresh Data Now", use_container_width=True):
        st.cache_data.clear()

    @st.cache_data(ttl=600, show_spinner="Fetching live data…")
    def load_data():
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
                if len(data)<2: continue
                dft = pd.DataFrame(data[1:], columns=[str(c).strip() for c in data[0]])
                mp={};seen=set()
                for col in dft.columns:
                    cl=col.lower(); t=None
                    if   "id"       in cl and "req"   in cl: t="Request ID"
                    elif "date"     in cl:                    t="Request Date"
                    elif "type"     in cl:                    t="Request Type"
                    elif "status"   in cl:                    t="Status"
                    elif "assigned" in cl or "agent"  in cl: t="Assigned By"
                    elif "response" in cl and "take"  in cl: t="Response Take"
                    elif "action"   in cl and "take"  in cl: t="First Action Take"
                    elif "request"  in cl and "take"  in cl: t="Request Take"
                    elif "email"    in cl or "special" in cl:t="Is Special Request(By Email)"
                    if t and t not in seen: mp[col]=t; seen.add(t)
                dft.rename(columns=mp, inplace=True)
                all_dfs.append(dft)
            if not all_dfs: return pd.DataFrame()
            df=pd.concat(all_dfs,ignore_index=True,sort=False)
            df.replace("",np.nan,inplace=True)
            for c in ["Request ID","Request Date","Request Type","Status","Request Take",
                      "Response Take","First Action Take","Assigned By","Is Special Request(By Email)"]:
                if c not in df.columns: df[c]=np.nan
            df["Status"]      =df["Status"].fillna("Unknown")
            df["Assigned By"] =df["Assigned By"].fillna("Unassigned")
            df["Request Type"]=df["Request Type"].fillna("Unknown Type")
            dp=pd.to_datetime(df["Request Date"],errors="coerce")
            df["Request Date"]=dp; df["Date Only"]=dp.dt.date
            df["Hour"]=dp.dt.hour.fillna(0).astype(int)
            df["Day Name"]=dp.dt.day_name().fillna("Unknown")
            df["Request Take (min)"]=df["Request Take"].apply(time_to_minutes).fillna(0)
            df["Response Take (min)"]=df["Response Take"].apply(time_to_minutes).fillna(0)
            df["First Action Take (min)"]=df["First Action Take"].apply(time_to_minutes).fillna(0)
            df["AHT (min)"]=df["First Action Take (min)"]
            df["Is Email"]=(df["Is Special Request(By Email)"].astype(str).str.strip().str.lower()=="yes")
            return df
        except Exception as e:
            st.error(f"❌ Connection Error: {e}"); return pd.DataFrame()

    df_raw = load_data()
    if df_raw.empty:
        st.warning("Waiting for data…"); st.stop()

    st.divider()
    min_d=df_raw["Date Only"].dropna().min()
    max_d=df_raw["Date Only"].dropna().max()
    date_range=st.date_input("Date Range",value=(min_d,max_d),min_value=min_d,max_value=max_d)
    d_from,d_to=(
        date_range if isinstance(date_range,(list,tuple)) and len(date_range)==2
        else (min_d,max_d))
    if d_from==d_to:
        st.caption(f"📅 {DAYS_AR.get(pd.to_datetime(d_from).day_name(),'')}")
    st.divider()
    sel_agents=st.multiselect("Agent Filter",   sorted(df_raw["Assigned By"].dropna().unique()))
    sel_types =st.multiselect("Request Type Filter",sorted(df_raw["Request Type"].dropna().unique()))

df=df_raw[(df_raw["Date Only"]>=d_from)&(df_raw["Date Only"]<=d_to)].copy()
if sel_agents: df=df[df["Assigned By"].isin(sel_agents)]
if sel_types:  df=df[df["Request Type"].isin(sel_types)]

# ══════════════════════════════════════════════════════════════════════════════════
#  SETTINGS PAGE
# ══════════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "settings":

    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

    # ──────────────────────────────────────────────────────────────────────────────
    #  ADMIN SETTINGS
    # ──────────────────────────────────────────────────────────────────────────────
    if is_admin():
        st.markdown("## ⚙️ Admin Panel")
        atab1, atab2, atab3 = st.tabs(["👤 My Profile", "🔔 Change Requests", "👥 Manage Users"])

        # ── My Profile ────────────────────────────────────────────────────────────
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
                        _save_store()
                        st.success("✅ Display name updated.")
                        st.rerun()
                    else:
                        st.warning("No change detected.")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div class='section-card'>", unsafe_allow_html=True)
            st.markdown("**🔑 Change Password**")
            with st.form("admin_pw_form"):
                old_pw  = st.text_input("Current Password",  type="password")
                new_pw1 = st.text_input("New Password",      type="password")
                new_pw2 = st.text_input("Confirm Password",  type="password")
                if st.form_submit_button("💾 Update Password", use_container_width=True):
                    if _hash(old_pw) != urow["password_hash"]:
                        st.error("❌ Current password is incorrect.")
                    elif new_pw1 != new_pw2:
                        st.error("❌ Passwords do not match.")
                    elif len(new_pw1) < 6:
                        st.error("❌ Minimum 6 characters.")
                    else:
                        users()[me()]["password_hash"] = _hash(new_pw1)
                        _save_store()
                        st.success("✅ Password updated.")
            st.markdown("</div>", unsafe_allow_html=True)

        # ── Change Requests ────────────────────────────────────────────────────────
        with atab2:
            st.markdown("### 🔔 Pending Change Requests")
            pending = [r for r in requests() if r["status"]=="pending"]

            if not pending:
                st.info("✅ No pending requests.")
            else:
                for req in pending:
                    udata_r   = users().get(req["requester"],{})
                    udisp     = udata_r.get("display_name", req["requester"])
                    req_label = "Display Name" if req["type"]=="display_name" else "Password"
                    val_show  = req["new_value"] if req["type"]=="display_name" else "••••••••"

                    st.markdown(f"""
                    <div class='req-pending'>
                        🕐 <b>{req['ts']}</b> &nbsp;|&nbsp;
                        👤 <b>{udisp}</b> (@{req['requester']}) &nbsp;|&nbsp;
                        Wants to change <b>{req_label}</b>
                        {f"→ <b>{val_show}</b>" if req['type']=='display_name' else ""}
                    </div>""", unsafe_allow_html=True)

                    rc1, rc2, rc3 = st.columns([3,1,1])
                    with rc2:
                        if st.button("✅ Approve", key=f"apr_{req['id']}", use_container_width=True):
                            approve_request(req["id"])
                            st.success(f"Approved {req_label} change for {udisp}.")
                            st.rerun()
                    with rc3:
                        if st.button("❌ Reject", key=f"rej_{req['id']}", use_container_width=True):
                            reject_request(req["id"])
                            st.warning("Request rejected.")
                            st.rerun()

            history = [r for r in requests() if r["status"]!="pending"]
            if history:
                st.divider()
                with st.expander(f"📋 Request History ({len(history)} records)"):
                    for req in reversed(history):
                        udisp     = users().get(req["requester"],{}).get("display_name",req["requester"])
                        req_label = "Display Name" if req["type"]=="display_name" else "Password"
                        css       = "req-approved" if req["status"]=="approved" else "req-rejected"
                        icon      = "✅" if req["status"]=="approved" else "❌"
                        st.markdown(f"""
                        <div class='{css}'>
                            {icon} <b>{req['ts']}</b> &nbsp;|&nbsp;
                            {udisp} — {req_label} — <b>{req['status'].upper()}</b>
                        </div>""", unsafe_allow_html=True)

        # ── Manage Users (admin can edit anyone directly) ──────────────────────────
        with atab3:
            st.markdown("### 👥 All Users")
            st.caption("As admin you can update any user's name or password directly — no approval needed.")
            for uname, urow in users().items():
                role_icon = "🔑" if urow["role"]=="admin" else "👁️"
                with st.expander(f"{role_icon} {urow['display_name']} (@{uname}) — {urow['role'].upper()}"):

                    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
                    with st.form(f"admin_edit_{uname}"):
                        eu_dn  = st.text_input("Display Name", value=urow["display_name"], key=f"dn_{uname}")
                        eu_p1  = st.text_input("New Password (blank = keep)", type="password", key=f"p1_{uname}")
                        eu_p2  = st.text_input("Confirm Password",            type="password", key=f"p2_{uname}")
                        saved  = st.form_submit_button("💾 Update", use_container_width=True)
                    if saved:
                        msgs=[]
                        if eu_dn.strip() and eu_dn.strip()!=urow["display_name"]:
                            users()[uname]["display_name"]=eu_dn.strip(); msgs.append("Name updated.")
                        if eu_p1:
                            if eu_p1!=eu_p2:          st.error("❌ Passwords don't match.")
                            elif len(eu_p1)<6:         st.error("❌ Minimum 6 characters.")
                            else:
                                users()[uname]["password_hash"]=_hash(eu_p1); msgs.append("Password updated.")
                        if msgs: _save_store(); st.success("✅ "+" ".join(msgs)); st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────────────
    #  VIEWER SETTINGS
    # ──────────────────────────────────────────────────────────────────────────────
    else:
        st.markdown("## ⚙️ My Profile Settings")
        urow = users()[me()]

        # ── Status of my pending/resolved requests ─────────────────────────────────
        my_pend = my_requests(me(), "pending")
        my_done = [r for r in requests() if r["requester"]==me() and r["status"]!="pending"]

        if my_pend:
            st.markdown("**🕐 Your Pending Requests:**")
            for req in my_pend:
                lbl = "Display Name" if req["type"]=="display_name" else "Password"
                st.markdown(f"""
                <div class='req-pending'>
                    🕐 <b>{req['ts']}</b> — <b>{lbl}</b> change is awaiting admin approval.
                </div>""", unsafe_allow_html=True)

        for req in my_done[-3:]:
            lbl  = "Display Name" if req["type"]=="display_name" else "Password"
            css  = "req-approved" if req["status"]=="approved" else "req-rejected"
            icon = "✅" if req["status"]=="approved" else "❌"
            st.markdown(f"""
            <div class='{css}'>
                {icon} <b>{req['ts']}</b> — <b>{lbl}</b> request was <b>{req['status'].upper()}</b>.
            </div>""", unsafe_allow_html=True)

        st.divider()

        # ── Request Display Name Change ────────────────────────────────────────────
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("### ✏️ Request Display Name Change")
        st.caption("Submitted requests are sent to the admin for approval before taking effect.")
        already_dn = any(r["requester"]==me() and r["type"]=="display_name" and r["status"]=="pending"
                         for r in requests())
        if already_dn:
            st.warning("⏳ You already have a pending name change request.")
        else:
            with st.form("viewer_name_form"):
                req_name = st.text_input("New Display Name", placeholder=urow["display_name"])
                if st.form_submit_button("📤 Submit Request", use_container_width=True):
                    if not req_name.strip():
                        st.error("Name cannot be empty.")
                    elif req_name.strip()==urow["display_name"]:
                        st.warning("That is already your current name.")
                    else:
                        push_request(me(), "display_name", req_name.strip())
                        st.success("✅ Request submitted! Waiting for admin approval.")
                        st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # ── Request Password Change ────────────────────────────────────────────────
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("### 🔑 Request Password Change")
        st.caption("Your current password is required to verify the request before it is sent to admin.")
        already_pw = any(r["requester"]==me() and r["type"]=="password" and r["status"]=="pending"
                         for r in requests())
        if already_pw:
            st.warning("⏳ You already have a pending password change request.")
        else:
            with st.form("viewer_pw_form"):
                cur_pw  = st.text_input("Current Password",  type="password")
                new_p1  = st.text_input("New Password",      type="password")
                new_p2  = st.text_input("Confirm Password",  type="password")
                if st.form_submit_button("📤 Submit Request", use_container_width=True):
                    if _hash(cur_pw)!=urow["password_hash"]:
                        st.error("❌ Current password is incorrect.")
                    elif new_p1!=new_p2:
                        st.error("❌ New passwords do not match.")
                    elif len(new_p1)<6:
                        st.error("❌ Minimum 6 characters.")
                    else:
                        push_request(me(), "password", new_p1)
                        st.success("✅ Request submitted! Waiting for admin approval.")
                        st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()   # Don't render dashboard while in settings

# ══════════════════════════════════════════════════════════════════════════════════
#  DASHBOARD HEADER
# ══════════════════════════════════════════════════════════════════════════════════
caption_text=(
    f"🔍 Search Period: {d_from} ({DAYS_AR.get(pd.to_datetime(d_from).day_name(),'')})"
    if d_from==d_to else f"🔍 Search Period: {d_from} to {d_to}"
)
st.markdown("## 💊 In-Store Requests")
st.caption(caption_text)

# ══════════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["📈 Tab 1: Operational Insights",
                       "👥 Tab 2: Team Performance and KPIs"])

# ══════════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Operational Insights
# ══════════════════════════════════════════════════════════════════════════════════
with tab1:
    c1,c2=st.columns(2)
    with c1: esc  = st.checkbox("🔥 Show Escalated Cases Only",    value=False, key="t1_esc")
    with c2: nesc = st.checkbox("🟢 Show Non-Escalated Cases Only", value=False, key="t1_nesc")

    dfm=df.copy()
    if esc  and not nesc: dfm=dfm[dfm["Is Email"]==True]
    elif nesc and not esc: dfm=dfm[dfm["Is Email"]==False]

    total=len(dfm)
    ss=dfm["Status"].astype(str).str.strip()
    ok   =dfm[ss.str.contains("Closed",na=False,case=False)&~ss.str.contains("issue",na=False,case=False)].shape[0]
    issue=dfm[ss.str.contains("Closed",na=False,case=False)& ss.str.contains("issue",na=False,case=False)].shape[0]
    h_frt=fmt_m(dfm["Response Take (min)"].mean() if not dfm.empty else 0)
    h_aht=fmt_m(dfm["AHT (min)"].mean()           if not dfm.empty else 0)
    h_tat=fmt_m(dfm["Request Take (min)"].mean()   if not dfm.empty else 0)

    a,b,c_,d,e,f=st.columns(6)
    a.markdown(kpi_colored("Total Tickets",      f"{total:,}", "card-total"),     unsafe_allow_html=True)
    b.markdown(kpi_colored("Closed Completed",   f"{ok:,}",    "card-completed"), unsafe_allow_html=True)
    c_.markdown(kpi_colored("Closed with Issue", f"{issue:,}", "card-issue"),     unsafe_allow_html=True)
    d.markdown(kpi_colored("Avg Response (FRT)", h_frt,        "card-frt"),       unsafe_allow_html=True)
    e.markdown(kpi_colored("Avg Handling (AHT)", h_aht,        "card-aht"),       unsafe_allow_html=True)
    f.markdown(kpi_colored("Avg Service (TAT)",  h_tat,        "card-tat"),       unsafe_allow_html=True)
    st.write("")

    if not dfm.empty:
        dfm["Response Tier"]=dfm["Response Take (min)"].apply(assign_time_tier)
        dfm["Service Tier"] =dfm["Request Take (min)"].apply(assign_time_tier)
        rd=dfm.groupby("Response Tier").size().reset_index(name="Tickets")
        rd["SLA Category"]="Response Time"; rd.rename(columns={"Response Tier":"SLA Tier"},inplace=True)
        sd=dfm.groupby("Service Tier").size().reset_index(name="Tickets")
        sd["SLA Category"]="Service Resolution"; sd.rename(columns={"Service Tier":"SLA Tier"},inplace=True)
        sb_df=pd.concat([rd,sd],ignore_index=True)
        t_ord=["Under 15 Mins","15-30 Mins","30-45 Mins","45-60 Mins","Over 1 Hour"]
        c_ord=["Response Time","Service Resolution"]
        sb_df["SLA Category"]=pd.Categorical(sb_df["SLA Category"],categories=c_ord,ordered=True)
        sb_df["SLA Tier"]=pd.Categorical(sb_df["SLA Tier"],categories=t_ord,ordered=True)
        sb_df=sb_df.sort_values(["SLA Category","SLA Tier"]).reset_index(drop=True)
        sb_df["SLA Category"]=sb_df["SLA Category"].astype(str)
        sb_df["SLA Tier"]=sb_df["SLA Tier"].astype(str)
        fig_sb=px.sunburst(sb_df,path=["SLA Category","SLA Tier"],values="Tickets",color="SLA Tier",
            color_discrete_map={"Under 15 Mins":"#2ea44f","15-30 Mins":"#2188ff",
                                "30-45 Mins":"#bc8cff","45-60 Mins":"#f9c513","Over 1 Hour":"#ea4a5a"},
            branchvalues="total")
        fig_sb.update_traces(sort=False,textinfo="label+percent parent",
            hovertemplate="<b>%{label}</b><br>Tickets: %{value:,}<br>%{percentParent:.1%}")
        fig_sb.update_layout(**THEME,height=520,
            title_text="SLA Compliance & Time Tiers Breakdown",
            title_font_size=18,title_font_family="Inter, sans-serif",
            title_font_color="#e6edf3",hoverlabel_font_size=14,
            hoverlabel_font_family="Inter, sans-serif")
        st.plotly_chart(fig_sb,use_container_width=True)

    st.divider()

    if not dfm.empty:
        hrs=dfm.groupby("Hour").agg(Volume=("Request ID","count"),
            AR=("Response Take (min)","mean")).reset_index()
        hrs=hrs.set_index("Hour").reindex(range(24)).fillna(0).reset_index()
        hl=["12 AM" if h==0 else("12 PM" if h==12 else(f"{h} AM" if h<12 else f"{h-12} PM"))
            for h in hrs["Hour"]]
        hrs["Hour Label"]=hl
        fig_r=make_subplots(specs=[[{"secondary_y":True}]])
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"],y=hrs["Volume"],name="Volume",
            fill="tozeroy",line=dict(color="#58a6ff",width=2)),secondary_y=False)
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"],y=hrs["AR"],name="FRT (Avg Response)",
            mode="lines+markers",line=dict(color="#f0883e",width=3,shape="spline")),secondary_y=True)
        fig_r.update_xaxes(type="category",categoryorder="array",categoryarray=hl)
        fig_r.update_layout(**THEME,height=450,hovermode="x unified",
            legend_orientation="h",legend_y=1.1,
            title_text="Hourly Performance: Ticket Volume vs Average Response Time (FRT)",
            title_font_size=18,title_font_family="Inter, sans-serif",
            title_font_color="#e6edf3",hoverlabel_font_size=14,
            hoverlabel_font_family="Inter, sans-serif")
        st.plotly_chart(fig_r,use_container_width=True)

    st.info(f"⏱️ **Avg Service Resolution Time (TAT):** {h_tat} (HH:MM:SS) Per Ticket")
    st.write("")
    st.markdown("### 📋 Detailed Request Type Breakdown & Handling SLA")
    if not dfm.empty:
        bkd=dfm.groupby("Request Type").agg(Count=("Request ID","count"),
            Avg_S=("Request Take (min)","mean"),Avg_A=("AHT (min)","mean")).reset_index()
        bkd["Pct of Total"]=(bkd["Count"]/total*100).round(1).astype(str)+"%"
        bkd["Avg AHT"]=bkd["Avg_A"].apply(fmt_m)
        bkd["Avg Service"]=bkd["Avg_S"].apply(fmt_m)
        st.dataframe(bkd[["Request Type","Count","Pct of Total","Avg AHT","Avg Service"]]
                     .sort_values("Count",ascending=False),
                     hide_index=True,use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Team Performance and KPIs
# ══════════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 👥 Team Performance and KPIs")
    st.write("")

    t2c1,t2c2=st.columns(2)
    with t2c1: t2e =st.checkbox("🔥 Show Escalated Cases Only",    value=False,key="t2_esc")
    with t2c2: t2ne=st.checkbox("🟢 Show Non-Escalated Cases Only", value=False,key="t2_nesc")

    df_t2=df.copy()
    if t2e  and not t2ne: df_t2=df_t2[df_t2["Is Email"]==True]
    elif t2ne and not t2e: df_t2=df_t2[df_t2["Is Email"]==False]

    t2_ss=df_t2["Status"].astype(str).str.strip()
    t2_ok =df_t2[t2_ss.str.contains("Closed",na=False,case=False)&~t2_ss.str.contains("issue",na=False,case=False)].shape[0]
    t2_iss=df_t2[t2_ss.str.contains("Closed",na=False,case=False)& t2_ss.str.contains("issue",na=False,case=False)].shape[0]

    k1,k2,k3,k4,k5,k6=st.columns(6)
    k1.markdown(kpi_colored("Total Tickets",      f"{len(df_t2):,}","card-total"),     unsafe_allow_html=True)
    k2.markdown(kpi_colored("Closed Completed",   f"{t2_ok:,}",     "card-completed"), unsafe_allow_html=True)
    k3.markdown(kpi_colored("Closed with Issue",  f"{t2_iss:,}",    "card-issue"),     unsafe_allow_html=True)
    k4.markdown(kpi_colored("Avg Response (FRT)", fmt_m(df_t2["Response Take (min)"].mean() if not df_t2.empty else 0),"card-frt"),unsafe_allow_html=True)
    k5.markdown(kpi_colored("Avg Handling (AHT)", fmt_m(df_t2["AHT (min)"].mean()           if not df_t2.empty else 0),"card-aht"),unsafe_allow_html=True)
    k6.markdown(kpi_colored("Avg Service (TAT)",  fmt_m(df_t2["Request Take (min)"].mean()   if not df_t2.empty else 0),"card-tat"),unsafe_allow_html=True)

    st.write(""); st.divider()
    st.markdown("### 📊 Expert Performance Scorecard")

    EXCL=["mohammed shehta"]
    df_t2=df_t2[~df_t2["Assigned By"].astype(str).str.strip().str.lower().isin(EXCL)].copy()

    if df_t2.empty:
        st.warning("No data available.")
    else:
        rtl=df_t2["Request Type"].astype(str).str.lower()
        df_t2["_jhah"] =rtl.str.contains("jhah",na=False)
        df_t2["_rfb"]  =rtl.str.contains("report|feedback",na=False)
        df_t2["_c_ok"] =(df_t2["Status"].astype(str).str.contains("Closed",case=False,na=False)&
                         ~df_t2["Status"].astype(str).str.contains("issue",case=False,na=False))
        df_t2["_c_all"]=df_t2["Status"].astype(str).str.contains("Closed",case=False,na=False)

        dc=(df_t2.groupby(["Assigned By","Date Only"])["Request ID"]
            .count().reset_index(name="_n"))
        active_days=(dc[dc["_n"]>15].groupby("Assigned By")["Date Only"]
                     .nunique().rename("Working Days"))

        grp=df_t2.groupby("Assigned By")
        sc=pd.DataFrame(index=grp.groups.keys())
        sc.index.name="Assigned By"
        sc["Working Days"]        =active_days.reindex(sc.index).fillna(0).astype(int)
        sc["Tickets Count"]       =grp["Request ID"].count()
        sc["JHAH Requests"]       =grp["_jhah"].sum().astype(int)
        sc["Reporting & Feedback"]=grp["_rfb"].sum().astype(int)
        sc["Email Counts"]        =grp["Is Email"].sum().astype(int)
        tavg=sc["Tickets Count"].mean()
        sc["% Achievement from Target"]=(
            (sc["Tickets Count"]/tavg*100).round(1).astype(str)+"%"
            if tavg>0 else "0.0%")
        avg_svc=grp["Request Take (min)"].mean()
        sc["Service Time"]=avg_svc.apply(fmt_m)
        ca=grp["_c_all"].sum(); co=grp["_c_ok"].sum()
        sq=(co/ca.replace(0,np.nan)*100).round(1)
        sc["Service Quality"]=sq.fillna(0).astype(str)+"%"
        sc=sc.reset_index().rename(columns={"Assigned By":"Expert"})

        # Apply saved overrides
        for i,row in sc.iterrows():
            ov=overrides().get(row["Expert"],{})
            for col,val in ov.items():
                sc.at[i,col]=val

        def _pct_avg(s):
            return f"{s.astype(str).str.rstrip('%').astype(float).mean():.1f}%"

        tl_ov=overrides().get("__TL__",{})
        tl_row={
            "Expert":"👑 Mohammed Shehta (TL)",
            "Working Days":        tl_ov.get("Working Days",0),
            "Tickets Count":       tl_ov.get("Tickets Count",0),
            "JHAH Requests":       tl_ov.get("JHAH Requests",0),
            "Reporting & Feedback":tl_ov.get("Reporting & Feedback",0),
            "Email Counts":        tl_ov.get("Email Counts",0),
            "% Achievement from Target":tl_ov.get("% Achievement from Target","0.0%"),
            "Service Time":        tl_ov.get("Service Time","00:00:00"),
            "Service Quality":     tl_ov.get("Service Quality","0.0%"),
        }
        team_row={
            "Expert":"🏆 Team AVG",
            "Working Days":        round(sc["Working Days"].astype(float).mean(),1),
            "Tickets Count":       round(sc["Tickets Count"].astype(float).mean(),1),
            "JHAH Requests":       round(sc["JHAH Requests"].astype(float).mean(),1),
            "Reporting & Feedback":round(sc["Reporting & Feedback"].astype(float).mean(),1),
            "Email Counts":        round(sc["Email Counts"].astype(float).mean(),1),
            "% Achievement from Target":"100.0%",
            "Service Time":        fmt_m(avg_svc.mean()),
            "Service Quality":     _pct_avg(sc["Service Quality"]),
        }

        sc_final=pd.concat(
            [pd.DataFrame([team_row]),sc,pd.DataFrame([tl_row])],
            ignore_index=True
        )

        col_cfg={
            "Expert":                    st.column_config.TextColumn("Expert"),
            "Working Days":              st.column_config.NumberColumn("Working Days",         format="%g"),
            "Tickets Count":             st.column_config.NumberColumn("Tickets Count",        format="%g"),
            "JHAH Requests":             st.column_config.NumberColumn("JHAH Requests",        format="%g"),
            "Reporting & Feedback":      st.column_config.NumberColumn("Reporting & Feedback", format="%g"),
            "Email Counts":              st.column_config.NumberColumn("Email Counts",          format="%g"),
            "% Achievement from Target": st.column_config.TextColumn("% Achievement"),
            "Service Time":              st.column_config.TextColumn("Service Time (HH:MM:SS)"),
            "Service Quality":           st.column_config.TextColumn("Service Quality"),
        }

        # ── VIEWER: read-only scorecard ───────────────────────────────────────────
        if not is_admin():
            st.dataframe(sc_final,hide_index=True,use_container_width=True,column_config=col_cfg)

        # ── ADMIN: scorecard + per-agent editor ───────────────────────────────────
        else:
            st.info("✏️ **Admin Mode** — Scorecard is live below. Use the editor to override any agent's KPI values.")
            st.dataframe(sc_final,hide_index=True,use_container_width=True,column_config=col_cfg)

            st.divider()
            st.markdown("#### ✏️ Manual KPI Override — Per Agent Editor")

            agent_opts=list(sc["Expert"])+["Mohammed Shehta (TL)"]
            sel_agent=st.selectbox("Choose agent to edit",agent_opts,key="agent_sel")

            if sel_agent=="Mohammed Shehta (TL)":
                akey="__TL__"
                cur=overrides().get(akey,{})
                dv={"Working Days":0,"Tickets Count":0,"JHAH Requests":0,
                    "Reporting & Feedback":0,"Email Counts":0,
                    "% Achievement from Target":"0.0%",
                    "Service Time":"00:00:00","Service Quality":"0.0%"}
            else:
                akey=sel_agent
                cur=overrides().get(akey,{})
                ar=sc[sc["Expert"]==sel_agent]
                if not ar.empty:
                    r=ar.iloc[0]
                    dv={"Working Days":int(r["Working Days"]),"Tickets Count":int(r["Tickets Count"]),
                        "JHAH Requests":int(r["JHAH Requests"]),
                        "Reporting & Feedback":int(r["Reporting & Feedback"]),
                        "Email Counts":int(r["Email Counts"]),
                        "% Achievement from Target":str(r["% Achievement from Target"]),
                        "Service Time":str(r["Service Time"]),
                        "Service Quality":str(r["Service Quality"])}
                else:
                    dv={"Working Days":0,"Tickets Count":0,"JHAH Requests":0,
                        "Reporting & Feedback":0,"Email Counts":0,
                        "% Achievement from Target":"0.0%",
                        "Service Time":"00:00:00","Service Quality":"0.0%"}

            def gv(k): return cur.get(k,dv[k])

            with st.form(f"form_{sel_agent}"):
                st.markdown(f"**Editing: {sel_agent}**")
                fc1,fc2,fc3,fc4=st.columns(4)
                with fc1:
                    nwd =st.number_input("Working Days",         min_value=0,value=int(gv("Working Days")),        step=1)
                    ntc =st.number_input("Tickets Count",        min_value=0,value=int(gv("Tickets Count")),       step=1)
                with fc2:
                    njh =st.number_input("JHAH Requests",        min_value=0,value=int(gv("JHAH Requests")),       step=1)
                    nrfb=st.number_input("Reporting & Feedback", min_value=0,value=int(gv("Reporting & Feedback")),step=1)
                with fc3:
                    nem =st.number_input("Email Counts",         min_value=0,value=int(gv("Email Counts")),        step=1)
                    nach=st.text_input("% Achievement from Target",value=str(gv("% Achievement from Target")))
                with fc4:
                    nst =st.text_input("Service Time (HH:MM:SS)",value=str(gv("Service Time")))
                    nsq =st.text_input("Service Quality (%)",     value=str(gv("Service Quality")))
                sc_col,rc_col=st.columns(2)
                with sc_col: do_save =st.form_submit_button("💾 Save Override",  use_container_width=True)
                with rc_col: do_reset=st.form_submit_button("🔄 Reset to Auto",  use_container_width=True)

            if do_save:
                overrides()[akey]={
                    "Working Days":nwd,"Tickets Count":ntc,"JHAH Requests":njh,
                    "Reporting & Feedback":nrfb,"Email Counts":nem,
                    "% Achievement from Target":nach,
                    "Service Time":nst,"Service Quality":nsq,
                }
                _save_store()
                st.success(f"✅ Override saved for **{sel_agent}**. Scroll up to see updated table.")
                st.rerun()

            if do_reset:
                overrides().pop(akey,None)
                _save_store()
                st.success(f"🔄 Reverted to auto values for **{sel_agent}**.")
                st.rerun()

            if overrides():
                st.divider()
                with st.expander(f"🗂️ Active Overrides ({len(overrides())} agents)"):
                    for ak,av in overrides().items():
                        lbl="Mohammed Shehta (TL)" if ak=="__TL__" else ak
                        st.markdown(f"**{lbl}**")
                        st.json(av)
                if st.button("🗑️ Clear ALL Overrides",type="secondary"):
                    st.session_state.store["overrides"]={}
                    _save_store()
                    st.rerun()
