import hashlib
import json
import pathlib
import re
import time
import urllib.parse
from datetime import timedelta

import gspread
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from google.oauth2.service_account import Credentials
from plotly.subplots import make_subplots

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
            "admin": {"display_name": "Mohammed Shehta", "password_hash": _hash("admin123"), "role": "admin", "agent_name": None},
            "50107": {"display_name": "Ahmed El-Kholy", "password_hash": _hash("50107"), "role": "expert", "agent_name": "Ahmed El-Kholy"},
            "50399": {"display_name": "Ahmed Kadry", "password_hash": _hash("50399"), "role": "expert", "agent_name": "Ahmed Kadry"},
            "50187": {"display_name": "Amr El-Sayed", "password_hash": _hash("50187"), "role": "expert", "agent_name": "Amr El-Sayed"},
            "50461": {"display_name": "Eslam Ramadan", "password_hash": _hash("50461"), "role": "expert", "agent_name": "Eslam Ramadan"},
            "50274": {"display_name": "Mohamed Abdelmageed", "password_hash": _hash("50274"), "role": "expert", "agent_name": "Mohamed Abdelmageed"},
            "50476": {"display_name": "Mohamed Khalifa", "password_hash": _hash("50476"), "role": "expert", "agent_name": "Mohamed Khalifa"},
            "50114": {"display_name": "Yahia Ali Shafei", "password_hash": _hash("50114"), "role": "expert", "agent_name": "Yahia Ali Shafei"}
        },
        "requests":  [],
        "overrides": {},
    }
    
    if _DATA_FILE.exists():
        try:
            loaded = json.loads(_DATA_FILE.read_text())
            if "users" in loaded:
                default_store["users"].update(loaded["users"])
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
#  WHATSAPP ADMIN NOTIFICATION
# ══════════════════════════════════════════════════════════════════════════════════
def notify_admin_whatsapp(logged_in_user):
    try:
        if "whatsapp" in st.secrets and "api_key" in st.secrets["whatsapp"]:
            api_key = st.secrets["whatsapp"]["api_key"]
            phone = "+201129217380"
            msg = f"🚨 *System Login Alert*%0AUser: *{logged_in_user}*%0ATime: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={msg}&apikey={api_key}"
            requests.get(url, timeout=3)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════════
#  CSS — CLEAN, MODERN, PROFESSIONAL LIGHT THEME
# ══════════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* Global Background & Typography */
.stApp {
    background-color: #f8fafc !important;
    color: #0f172a !important;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif !important;
}
h1, h2, h3, h4 { color: #0f172a !important; font-weight: 700 !important; }
h1 { font-size: 2.2rem !important; }
h2 { font-size: 1.8rem !important; margin-top: 1rem !important; }
h3 { font-size: 1.4rem !important; }
p, span, label { color: #334155 !important; }

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
}
[data-testid="stSidebar"] hr { border-color: #f1f5f9 !important; }

/* Clean KPI Cards */
.kpi-container {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
    position: relative;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    transition: transform 0.2s, box-shadow 0.2s;
    margin-bottom: 1rem;
    min-height: 110px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.kpi-container:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.kpi-label {
    font-size: 0.85rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b !important;
    font-weight: 600;
    margin-bottom: 0.4rem;
}
.kpi-value {
    font-size: 1.8rem !important;
    font-weight: 800 !important;
    color: #0f172a;
}
/* Color Accents for Cards (Top Border) */
.card-total { border-top: 4px solid #0284c7; }
.card-completed { border-top: 4px solid #10b981; }
.card-issue { border-top: 4px solid #ef4444; }
.card-aht, .card-tat { border-top: 4px solid #8b5cf6; }
.card-store, .card-actions { border-top: 4px solid #f59e0b; }
.card-dark-green { border-top: 4px solid #0f766e; }

.card-small { min-height: 85px; padding: 0.8rem; border-radius: 10px; }
.card-small .kpi-value { font-size: 1.4rem !important; }
.card-small .kpi-label { font-size: 0.75rem !important; }

/* Inputs and Buttons */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    border-radius: 8px !important;
    border: 1px solid #cbd5e1 !important;
    box-shadow: none !important;
}
.stTextInput input:focus { border-color: #3b82f6 !important; box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important; }
.stButton > button {
    background-color: #2563eb !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    border: none !important;
    box-shadow: 0 2px 4px rgba(37,99,235,0.2) !important;
    transition: all 0.2s;
}
.stButton > button:hover {
    background-color: #1d4ed8 !important;
    transform: translateY(-1px);
}

/* Authentication Screen */
.login-wrap {
    max-width: 420px; margin: 6rem auto; padding: 2.5rem;
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px;
    box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05);
}
.login-title { font-size: 1.8rem !important; font-weight: 800; text-align: center; color: #0f172a; margin-bottom: 0.5rem; }
.login-sub { font-size: 0.95rem; text-align: center; color: #64748b; margin-bottom: 1.5rem; }

/* Scorecard Table */
.scorecard-container {
    width: 100%; overflow-x: auto; margin: 1rem 0;
    border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    border: 1px solid #e2e8f0;
}
.scorecard-container table { width: 100%; border-collapse: collapse; background: #fff; }
.scorecard-container th {
    background-color: #f1f5f9 !important;
    color: #334155 !important;
    font-weight: 700 !important; font-size: 0.9rem !important;
    padding: 10px !important; text-align: center !important;
    border-bottom: 2px solid #e2e8f0;
}
.scorecard-container td {
    padding: 10px !important; font-size: 0.9rem !important;
    text-align: center !important; border-bottom: 1px solid #e2e8f0; color: #1e293b;
}
.scorecard-container td:first-child { font-weight: 700 !important; text-align: left !important; padding-left: 16px !important; }
</style>
""", unsafe_allow_html=True)

THEME = dict(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#334155", margin=dict(l=10, r=10, t=40, b=10))

# ══════════════════════════════════════════════════════════════════════════════════
#  SESSION & HELPERS
# ══════════════════════════════════════════════════════════════════════════════════
def generate_token(uname: str) -> str: return hashlib.sha256((uname + "SECRET_ALDAWAA_TOKEN").encode()).hexdigest()

if "store" not in st.session_state: st.session_state.store = _load_store()
if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "username": None, "role": None, "page": "dashboard", "force_onboard": False, "view_request_form": False})
    if "usr" in st.query_params and "tok" in st.query_params:
        q_usr, q_tok = st.query_params["usr"], st.query_params["tok"]
        udata = st.session_state.store["users"].get(q_usr)
        if udata and generate_token(q_usr) == q_tok:
            st.session_state.update({"authenticated": True, "username": q_usr, "role": udata["role"]})

def users(): return st.session_state.store["users"]
def requests(): return st.session_state.store["requests"]
def overrides(): return st.session_state.store["overrides"]
def me(): return st.session_state.username
def is_admin(): return st.session_state.role == "admin"
def cur_user(): return users().get(me(), {})
def my_agent_name(): return users().get(me(), {}).get("agent_name")
def pending_count(): return sum(1 for r in requests() if r["status"] == "pending")

def push_request(uname, rtype, new_value):
    requests().append({"id": int(time.time() * 1000), "requester": uname, "type": rtype, "new_value": new_value, "status": "pending", "ts": time.strftime("%Y-%m-%d %H:%M")})
    _save_store()

def approve_request(req_id):
    for r in requests():
        if r["id"] == req_id and r["status"] == "pending":
            u = r["requester"]
            if r["type"] == "display_name": users()[u]["display_name"] = r["new_value"]
            elif r["type"] == "password": users()[u]["password_hash"] = _hash(r["new_value"])
            elif r["type"] == "visitor_access":
                ukey = u.strip().lower().replace(" ", "_")
                users()[ukey] = {"display_name": u.strip(), "password_hash": _hash("123456789"), "role": "expert", "agent_name": u.strip()}
            r["status"] = "approved"; _save_store(); return True
    return False

def reject_request(req_id):
    for r in requests():
        if r["id"] == req_id and r["status"] == "pending":
            r["status"] = "rejected"; _save_store(); return True
    return False

def calc_change(curr, prev):
    curr, prev = curr if pd.notna(curr) else 0, prev if pd.notna(prev) else 0
    if prev == 0: return 100.0 if curr > 0 else 0.0
    return ((curr - prev) / prev) * 100.0

def kpi_colored(label, value, cls, change=None, inverse=False, neutral=False):
    change_html = ""
    if change is not None:
        color = "#64748b" if neutral else ("#ef4444" if (change > 0 and inverse) or (change < 0 and not inverse) else "#10b981")
        color = color if change != 0 else "#94a3b8"
        arrow = "▲" if change > 0 else ("▼" if change < 0 else "−")
        change_html = f'<div style="position: absolute; top: 12px; right: 12px; font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; font-weight: 700; color: {color}; background-color: {color}15;">{arrow} {abs(change):.1f}%</div>'
    return f'<div class="kpi-container {cls}"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>{change_html}</div>'

def time_to_minutes(s):
    try: p = str(s).strip().split(":"); return int(p[0]) * 60 + int(p[1])
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

DAYS_AR = {"Saturday": "السبت", "Sunday": "الأحد", "Monday": "الإثنين", "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة"}

OFFICIAL_EXPERTS = ["Ahmed El-Kholy", "Ahmed Kadry", "Amr El-Sayed", "Eslam Ramadan", "Mohamed Abdelmageed", "Mohamed Khalifa", "Yahia Ali Shafei"]
EXPERT_ID_MAP = {"Ahmed El-Kholy": "50107", "Ahmed Kadry": "50399", "Amr El-Sayed": "50187", "Eslam Ramadan": "50461", "Mohamed Abdelmageed": "50274", "Mohamed Khalifa": "50476", "Yahia Ali Shafei": "50114"}
AGENT_ALIASES = {"mohamed abdelmajid": "Mohamed Abdelmageed", "محمد عبد المجيد": "Mohamed Abdelmageed", "50274": "Mohamed Abdelmageed", "احمد الخولى": "Ahmed El-Kholy", "50107": "Ahmed El-Kholy", "يحي علي شافعي": "Yahia Ali Shafei", "50114": "Yahia Ali Shafei", "عمرو محمد السيد": "Amr El-Sayed", "50187": "Amr El-Sayed", "أحمد محمد قدري": "Ahmed Kadry", "50399": "Ahmed Kadry", "إسلام رمضان خليل": "Eslam Ramadan", "50461": "Eslam Ramadan", "محمد خليفة جاب الله": "Mohamed Khalifa", "50476": "Mohamed Khalifa"}
EXCLUSION_LIST = ['off', 'اوف', 'أوف', 'راحة', 'annual', 'casual', 'عارضة', 'عارضه', 'v', 'a', 'vacation', 'resign', 'استقالة', 'مستقيل', 'sick', 'مرضي', 'nan', 'none', '']

def normalize_expert_name(name):
    n_lower = str(name).lower().strip()
    if n_lower in AGENT_ALIASES: return AGENT_ALIASES[n_lower]
    id_to_name = {v: k for k, v in EXPERT_ID_MAP.items()}
    return id_to_name.get(name, name)

# ══════════════════════════════════════════════════════════════════════════════════
#  LOGIN MODULE
# ══════════════════════════════════════════════════════════════════════════════════
if not st.session_state.authenticated:
    st.markdown("<div class='login-wrap'><div class='login-title'>💊 Dashboard Login</div><div class='login-sub'>In-Store Requests · AlDawaa</div></div>", unsafe_allow_html=True)
    _, lc, _ = st.columns([1, 1.4, 1])
    with lc:
        if not st.session_state.view_request_form:
            inp_u = st.text_input("Username / ID", key="li_u")
            inp_p = st.text_input("Password", type="password", key="li_p")
            if st.button("🔐 Login", use_container_width=True):
                uname = inp_u.strip().lower()
                udata = users().get(uname)
                if udata and udata["password_hash"] == _hash(inp_p):
                    notify_admin_whatsapp(udata.get("display_name", uname) + " ✅ Success")
                    st.query_params["usr"] = uname
                    st.query_params["tok"] = generate_token(uname)
                    st.session_state.update({"username": uname, "role": udata["role"], "authenticated": True})
                    if inp_u.strip() == inp_p.strip() and udata["role"] == "expert": st.session_state.force_onboard = True
                    st.rerun()
                else:
                    st.error("❌ Incorrect username or password.")
            if st.button("🚫 Request Access", use_container_width=True): st.session_state.view_request_form = True; st.rerun()
        else:
            visitor_name = st.text_input("Enter Your Full Name")
            if st.button("📤 Submit Request", use_container_width=True):
                if visitor_name.strip():
                    push_request(visitor_name.strip(), "visitor_access", "123456789")
                    st.success("✅ Request sent! Username will be your name, default password will be 123456789.")
                    time.sleep(2); st.session_state.view_request_form = False; st.rerun()
            if st.button("← Back to Login", use_container_width=True): st.session_state.view_request_form = False; st.rerun()
    st.stop()

if st.session_state.force_onboard:
    st.info("🚨 This is your first login. You must update your password.")
    with st.form("onboard_pass_form"):
        new_ob1, new_ob2 = st.text_input("New Password", type="password"), st.text_input("Confirm", type="password")
        if st.form_submit_button("💾 Save"):
            if new_ob1 != new_ob2 or len(new_ob1) < 6: st.error("❌ Passwords mismatch or too short.")
            else:
                users()[me()]["password_hash"] = _hash(new_ob1); _save_store()
                st.session_state.update({"role": users()[me()]["role"], "force_onboard": False, "page": "dashboard"})
                st.rerun()
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════════
#  SIDEBAR & DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"👤 **{cur_user().get('display_name', '–')}** ({'ADMIN' if is_admin() else 'EXPERT'})")
    sb1, sb2 = st.columns(2)
    if sb1.button("⚙️ Settings", use_container_width=True): st.session_state.page = "settings"; st.rerun()
    if sb2.button("🚪 Logout", use_container_width=True):
        st.query_params.clear(); st.session_state.clear(); st.rerun()
    if is_admin() and pending_count() > 0: st.warning(f"🔔 {pending_count()} pending requests")

    @st.cache_data(ttl=600, show_spinner="Syncing data...")
    def load_data():
        try:
            creds = Credentials.from_service_account_info(json.loads(st.secrets["gspread"]["credentials"]), scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
            client = gspread.authorize(creds)
            sheet = client.open("AlDawaa Tickets Data")
            all_dfs, roster_df, out_req_df = [], pd.DataFrame(), pd.DataFrame()
            
            for ws in sheet.worksheets():
                data = ws.get_all_values()
                if len(data) < 2: continue
                title = ws.title.strip()
                if title == "Working Days": roster_df = pd.DataFrame(data[1:], columns=[str(c).strip() for c in data[0]]); continue
                elif title == "Out Requests": out_req_df = pd.DataFrame(data); continue
                
                dft = pd.DataFrame(data[1:], columns=[str(c).strip() for c in data[0]])
                mp, seen = {}, set()
                for col in dft.columns:
                    cl = col.lower(); t = None
                    if "id" in cl and "req" in cl: t = "Request ID"
                    elif "date" in cl: t = "Request Date"
                    elif "type" in cl: t = "Request Type"
                    elif "status" in cl and "count" in cl: t = "Status Count"
                    elif "status" in cl: t = "Status"
                    elif "assigned" in cl or "agent" in cl: t = "Assigned By"
                    elif "response" in cl and "take" in cl: t = "Response Take"
                    elif "action" in cl and "take" in cl: t = "First Action Take"
                    elif "request" in cl and "take" in cl: t = "Request Take"
                    elif "email" in cl or "special" in cl: t = "Is Special Request(By Email)"
                    elif "hic" in cl or "insurance" in cl: t = "HIC"
                    elif "store" in cl or "branch" in cl: t = "Store ID"
                    if t and t not in seen: mp[col] = t; seen.add(t)
                dft.rename(columns=mp, inplace=True); all_dfs.append(dft)
            
            df = pd.concat(all_dfs, ignore_index=True, sort=False) if all_dfs else pd.DataFrame()
            if not df.empty:
                df.replace("", np.nan, inplace=True)
                for c in ["Request ID", "Request Date", "Request Type", "Status", "Status Count", "Request Take", "Response Take", "Assigned By", "Is Special Request(By Email)", "HIC"]:
                    if c not in df.columns: df[c] = np.nan
                df["Status"] = df["Status"].fillna("Unknown")
                df["Status Count"] = pd.to_numeric(df["Status Count"], errors="coerce").fillna(0).astype(int)
                df["HIC"] = df["HIC"].fillna("Unknown")
                df["Store ID"] = df.get("Store ID", "Unknown").fillna("Unknown").astype(str)
                df["Assigned By"] = df["Assigned By"].fillna("Unassigned").apply(normalize_expert_name)
                dp = pd.to_datetime(df["Request Date"], errors="coerce")
                df["Date Only"], df["Hour"], df["Day Name"] = dp.dt.date, dp.dt.hour.fillna(0).astype(int), dp.dt.day_name().fillna("Unknown")
                df["Request Take (min)"] = df.get("Request Take", pd.Series()).apply(time_to_minutes).fillna(0)
                df["Response Take (min)"] = df.get("Response Take", pd.Series()).apply(time_to_minutes).fillna(0)
                df["Is Email"] = (df["Is Special Request(By Email)"].astype(str).str.strip().str.lower() == "yes")
            return df, roster_df, out_req_df
        except Exception:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df_raw, df_roster, df_out_req = load_data()
    if df_raw.empty: st.warning("Empty source records."); st.stop()

    st.markdown("### 🔍 Filters")
    min_d, max_d = df_raw["Date Only"].dropna().min(), df_raw["Date Only"].dropna().max()
    date_range = st.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    d_from, d_to = date_range if isinstance(date_range, (list, tuple)) and len(date_range) == 2 else (min_d, max_d)
    delta_days = (d_to - d_from).days + 1
    prev_d_to = d_from - timedelta(days=1)
    prev_d_from = prev_d_to - timedelta(days=delta_days - 1)
    sel_hic = st.multiselect("HIC", sorted(df_raw["HIC"].dropna().unique()))

out_req_dict, global_jhah, global_support = {}, 0, 0
if not df_out_req.empty and len(df_out_req) > 2:
    row0 = df_out_req.iloc[0].values
    col_idx = next((i for i, v in enumerate(row0) if str(v).strip() == d_to.strftime("%m-%Y")), -1)
    if col_idx != -1:
        for i in range(2, len(df_out_req)):
            norm_name = normalize_expert_name(str(df_out_req.iloc[i, 1]).strip()).lower()
            if not norm_name: continue
            q_v = str(df_out_req.iloc[i, col_idx]).strip() if col_idx < len(df_out_req.columns) else ""
            j_v = str(df_out_req.iloc[i, col_idx+1]).strip() if col_idx+1 < len(df_out_req.columns) else ""
            s_v = str(df_out_req.iloc[i, col_idx+2]).strip() if col_idx+2 < len(df_out_req.columns) else ""
            out_req_dict[norm_name] = {"Quality": q_v, "JHAH": j_v, "Support Req": s_v}
            try: global_jhah += int(float(j_v)) if j_v else 0; global_support += int(float(s_v)) if s_v else 0
            except: pass

# Optimized Global Dataframe Filtering
df = df_raw[(df_raw["Date Only"] >= d_from) & (df_raw["Date Only"] <= d_to)].copy()
df_prev_all = df_raw[(df_raw["Date Only"] >= prev_d_from) & (df_raw["Date Only"] <= prev_d_to)].copy()
if sel_hic:
    df, df_prev_all = df[df["HIC"].isin(sel_hic)], df_prev_all[df_prev_all["HIC"].isin(sel_hic)]

# ══════════════════════════════════════════════════════════════════════════════════
#  DASHBOARD MODULE
# ══════════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "settings":
    if st.button("← Back to Dashboard"): st.session_state.page = "dashboard"; st.rerun()
    st.warning("Settings panel active. (Code structure retained but collapsed for brevity).")
    st.stop()

st.markdown("## 💊 In-Store Requests Matrix")
st.caption(f"🔍 Period: {d_from} to {d_to}")

tab1, tab2 = st.tabs(["📈 Operational Insights", "👥 Team Performance & KPIs"])

with tab1:
    c1, c2 = st.columns(2)
    esc, nesc = c1.checkbox("🔥 Escalated Cases Only"), c2.checkbox("🟢 Non-Escalated Cases Only")

    # Reusing the filtered dataframe globally
    dfm = df.copy()
    dfm_prev = df_prev_all.copy()
    if esc and not nesc: dfm, dfm_prev = dfm[dfm["Is Email"] == True], dfm_prev[dfm_prev["Is Email"] == True]
    elif nesc and not esc: dfm, dfm_prev = dfm[dfm["Is Email"] == False], dfm_prev[dfm_prev["Is Email"] == False]

    total, prev_total = len(dfm), len(dfm_prev)
    ss, ss_prev = dfm["Status"].astype(str), dfm_prev["Status"].astype(str)
    ok = dfm[ss.str.contains("Closed", case=False) & ~ss.str.contains("issue", case=False)].shape[0]
    issue = dfm[ss.str.contains("Closed", case=False) & ss.str.contains("issue", case=False)].shape[0]
    prev_ok = dfm_prev[ss_prev.str.contains("Closed", case=False) & ~ss_prev.str.contains("issue", case=False)].shape[0]
    prev_issue = dfm_prev[ss_prev.str.contains("Closed", case=False) & ss_prev.str.contains("issue", case=False)].shape[0]

    c_afr, p_afr = dfm["Response Take (min)"].mean() if not dfm.empty else 0, dfm_prev["Response Take (min)"].mean() if not dfm_prev.empty else 0
    c_tat, p_tat = dfm["Request Take (min)"].mean() if not dfm.empty else 0, dfm_prev["Request Take (min)"].mean() if not dfm_prev.empty else 0
    st_count, p_st_count = dfm["Store ID"].nunique(), dfm_prev["Store ID"].nunique()
    
    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
    r1c1.markdown(kpi_colored("Total Tickets", f"{total:,}", "card-total", calc_change(total, prev_total), neutral=True), unsafe_allow_html=True)
    r1c2.markdown(kpi_colored("Stores Served", f"{st_count:,}", "card-store", calc_change(st_count, p_st_count), neutral=True), unsafe_allow_html=True)
    r1c3.markdown(kpi_colored("Closed Completed", f"{ok:,}", "card-completed", calc_change((ok/total*100) if total else 0, (prev_ok/prev_total*100) if prev_total else 0)), unsafe_allow_html=True)
    r1c4.markdown(kpi_colored("Avg Response (AFR)", fmt_m(c_afr), "card-aht", calc_change(c_afr, p_afr), inverse=True), unsafe_allow_html=True)
    r1c5.markdown(kpi_colored("Avg Service (TAT)", fmt_m(c_tat), "card-tat", calc_change(c_tat, p_tat), inverse=True), unsafe_allow_html=True)

    st.divider()

    if not dfm.empty:
        st.markdown("### ⏳ Ticket Flow Rate (Hourly)")
        hrs = dfm.groupby("Hour").agg(Volume=("Request ID", "count"), AR=("Response Take (min)", "mean")).reindex(range(24), fill_value=0).reset_index()
        hrs["Hour Label"] = [f"{h} AM" if h < 12 else f"{h - 12} PM" for h in hrs["Hour"]]
        
        fig_r = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"], y=hrs["Volume"], name="Volume", fill="tozeroy", line=dict(color="#0ea5e9")), secondary_y=False)
        fig_r.add_trace(go.Scatter(x=hrs["Hour Label"], y=hrs["AR"], name="Avg Response (min)", mode="lines+markers", line=dict(color="#f59e0b")), secondary_y=True)
        fig_r.update_layout(**THEME, height=400, hovermode="x unified")
        st.plotly_chart(fig_r, use_container_width=True)

        st.divider()
        st.markdown("### 🏥 Insurance Provider (HIC) Breakdown")
        hic_counts = dfm.groupby("HIC").agg(Volume=("Request ID", "count")).reset_index().sort_values("Volume", ascending=False)
        fig_hic = px.bar(hic_counts, x="HIC", y="Volume", text="Volume", color="HIC", color_discrete_sequence=px.colors.qualitative.Prism)
        fig_hic.update_layout(**THEME, height=400, showlegend=False)
        st.plotly_chart(fig_hic, use_container_width=True)

with tab2:
    st.markdown("### 👥 Team Performance and KPIs")
    sel_agents_t2 = st.multiselect("Filter by Expert", sorted(df_raw["Assigned By"].dropna().unique()))
    df_t2 = df.copy()
    if sel_agents_t2: df_t2 = df_t2[df_t2["Assigned By"].isin(sel_agents_t2)]
    
    aname = my_agent_name()
    df_kpi = df_t2[df_t2["Assigned By"] == aname].copy() if not is_admin() and aname else df_t2.copy()
    
    k1, k2, k3 = st.columns(3)
    k1.markdown(kpi_colored("Your Total Tickets", len(df_kpi), "card-total"), unsafe_allow_html=True)
    k2.markdown(kpi_colored("Your AFR", fmt_m(df_kpi["Response Take (min)"].mean() if not df_kpi.empty else 0), "card-aht"), unsafe_allow_html=True)
    k3.markdown(kpi_colored("Your TAT", fmt_m(df_kpi["Request Take (min)"].mean() if not df_kpi.empty else 0), "card-tat"), unsafe_allow_html=True)

    st.markdown("### 📊 Expert Scorecard")
    sc = pd.DataFrame({"Expert": OFFICIAL_EXPERTS})
    if not df_t2.empty:
        df_sc = df_t2[df_t2["Assigned By"].isin(OFFICIAL_EXPERTS)]
        stats = df_sc.groupby("Assigned By").agg(
            Tickets_Count=("Request ID", "count"),
            AFR_val=("Response Take (min)", "mean"),
            TAT_val=("Request Take (min)", "mean")
        ).reset_index()
        sc = sc.merge(stats, left_on="Expert", right_on="Assigned By", how="left").fillna(0)
    
    # Styling and presenting the simplified Scorecard
    sc["Tickets"] = sc.get("Tickets_Count", 0).astype(int)
    sc["AFR"] = sc.get("AFR_val", 0).apply(fmt_m)
    sc["Service Time (TAT)"] = sc.get("TAT_val", 0).apply(fmt_m)
    
    display_df = sc[["Expert", "Tickets", "AFR", "Service Time (TAT)"]]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
