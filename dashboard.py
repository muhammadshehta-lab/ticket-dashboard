import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json, hashlib, time, pathlib, urllib.parse, re, requests
from datetime import timedelta
import smtplib
from email.message import EmailMessage
import base64
from io import BytesIO
from PIL import Image

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

def _load_store() -> dict:
    default_store = {
        "requests": [], "overrides": {}, "login_logs": []
    }
    if _DATA_FILE.exists():
        try:
            loaded = json.loads(_DATA_FILE.read_text())
            if "requests" in loaded: default_store["requests"] = loaded["requests"]
            if "overrides" in loaded: default_store["overrides"] = loaded["overrides"]
            if "login_logs" in loaded: default_store["login_logs"] = loaded["login_logs"]
        except Exception: pass
    return default_store

def _save_store(): _DATA_FILE.write_text(json.dumps(st.session_state.store, indent=2))
def _hash(pw: str) -> str: return hashlib.sha256(pw.encode()).hexdigest()

def parse_drive_link(raw_url):
    raw_url = str(raw_url).strip()
    if "drive.google.com" in raw_url:
        try:
            match = re.search(r'/d/([a-zA-Z0-9_-]+)', raw_url)
            if not match: match = re.search(r'id=([a-zA-Z0-9_-]+)', raw_url)
            if match: return f"https://drive.google.com/thumbnail?id={match.group(1)}&sz=w500"
        except: return raw_url
    return raw_url

# ══════════════════════════════════════════════════════════════════════════════════
#  GOOGLE SHEETS SYNC HELPERS
# ══════════════════════════════════════════════════════════════════════════════════
def update_sheet_password(uname: str, new_pass: str):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
            creds = Credentials.from_service_account_info(json.loads(st.secrets["gspread"]["credentials"]), scopes=scopes)
            client = gspread.authorize(creds)
            ws = client.open("AlDawaa Tickets Data").worksheet("Users")
            cell = ws.find(str(uname), in_column=1)
            if cell: ws.update_cell(cell.row, 2, str(new_pass))
    except Exception: pass

def update_sheet_profile(uname: str, profile_data: dict):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
            creds = Credentials.from_service_account_info(json.loads(st.secrets["gspread"]["credentials"]), scopes=scopes)
            client = gspread.authorize(creds)
            ws = client.open("AlDawaa Tickets Data").worksheet("Users")
            cell = ws.find(str(uname), in_column=1)
            if cell:
                row = cell.row
                ws.update_cell(row, 7, str(profile_data.get('photo', '')))
                ws.update_cell(row, 8, str(profile_data.get('grad_year', '')))
                ws.update_cell(row, 9, str(profile_data.get('join_cc', '')))
                ws.update_cell(row, 10, str(profile_data.get('join_team', '')))
                ws.update_cell(row, 11, str(profile_data.get('bio', '')))
    except Exception: pass

def add_user_to_sheet(uname, pwd, role, dname, aname):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
            creds = Credentials.from_service_account_info(json.loads(st.secrets["gspread"]["credentials"]), scopes=scopes)
            client = gspread.authorize(creds)
            ws = client.open("AlDawaa Tickets Data").worksheet("Users")
            ws.append_row([str(uname), str(pwd), str(role), str(dname), str(aname or ""), "", "", "", "", "", ""])
    except Exception: pass

def delete_user_from_sheet(uname: str):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
            creds = Credentials.from_service_account_info(json.loads(st.secrets["gspread"]["credentials"]), scopes=scopes)
            client = gspread.authorize(creds)
            ws = client.open("AlDawaa Tickets Data").worksheet("Users")
            cell = ws.find(str(uname), in_column=1)
            if cell: ws.delete_rows(cell.row)
    except Exception: pass

def update_user_role_dname_aname_sheet(uname, role, dname, aname):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gspread" in st.secrets and "credentials" in st.secrets["gspread"]:
            creds = Credentials.from_service_account_info(json.loads(st.secrets["gspread"]["credentials"]), scopes=scopes)
            client = gspread.authorize(creds)
            ws = client.open("AlDawaa Tickets Data").worksheet("Users")
            cell = ws.find(str(uname), in_column=1)
            if cell:
                row = cell.row
                if dname: ws.update_cell(row, 4, str(dname))
                ws.update_cell(row, 5, str(aname or ""))
                ws.update_cell(row, 3, str(role))
    except Exception: pass

def notify_admin_whatsapp(logged_in_user):
    try:
        if "whatsapp" in st.secrets and "api_key" in st.secrets["whatsapp"]:
            api_key = st.secrets["whatsapp"]["api_key"]
            phone = "+201129217380"
            msg = f"🚨 *System Login Alert*%0AUser: *{logged_in_user}*%0ATime: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={msg}&apikey={api_key}"
            requests.get(url, timeout=3)
    except Exception: pass

def send_approval_email(to_email, name, uid):
    try:
        if "smtp" in st.secrets and "email" in st.secrets["smtp"] and "password" in st.secrets["smtp"]:
            sender_email = st.secrets["smtp"]["email"]
            sender_password = st.secrets["smtp"]["password"]
            msg = EmailMessage()
            msg['Subject'] = "✅ AlDawaa Dashboard Access Approved"
            msg['From'] = f"Mohammed Shehta <{sender_email}>"
            msg['To'] = to_email
            dashboard_url = "https://approvals-team.streamlit.app" 
            body = f"Dear {name},\n\nYour request to access the AlDawaa In-Store Requests Dashboard has been successfully approved.\n\nHere are your login credentials:\n- Username / ID: {uid}\n- Temporary Password: {uid}\n\n(Note: You will be required to set a new, secure password upon your first login).\n\nYou can access the dashboard via the link below:\n{dashboard_url}\n\nBest regards,\nMohammed Shehta"
            msg.set_content(body)
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            return True
        return False
    except Exception: return False

# ══════════════════════════════════════════════════════════════════════════════════
#  CSS  — PROFESSIONAL CORPORATE THEME
# ══════════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
.stApp { background: #f1f5f9 !important; color: #0f172a !important; }
.stApp, p, span, label, input, select { font-size: 1.05rem !important; font-weight: 600 !important; }
h1 { font-size: 2.5rem !important; font-weight: 900 !important; color: #0f172a !important; }
h2 { font-size: 2.15rem !important; font-weight: 900 !important; color: #1e293b !important; margin-top: 1rem !important; }
h3 { font-size: 1.65rem !important; font-weight: 800 !important; color: #1e293b !important; }
h4 { font-size: 1.35rem !important; font-weight: 800 !important; color: #334155 !important; }

[data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid #e2e8f0 !important; }
[data-testid="stSidebar"] * { color: #1e293b !important; font-weight: 700 !important; }
[data-testid="stTabs"] [data-baseweb="tab"] { background: transparent; color: #64748b !important; font-weight: 700 !important; font-size: 1.15rem !important; padding-bottom: 8px !important; }
[data-testid="stTabs"] [aria-selected="true"] { color: #2563eb !important; border-bottom: 3px solid #2563eb !important; }

.stTextInput input, .stNumberInput input, .stSelectbox select, .stDateInput input { background: #ffffff !important; border: 1px solid #cbd5e1 !important; color: #0f172a !important; border-radius: 8px !important; font-weight: 600 !important; font-size: 1.05rem !important; }
.stTextInput input:focus { border-color: #2563eb !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important; }
.stButton > button { background: #2563eb !important; border: 1px solid #1d4ed8 !important; color: #ffffff !important; border-radius: 8px !important; font-weight: 700 !important; font-size: 1.1rem !important; padding: 0.5rem 1.5rem !important; box-shadow: 0 2px 4px rgba(37,99,235,0.2); }
.stButton > button:hover { background: #1d4ed8 !important; border-color: #1e40af !important; transform: translateY(-1px); box-shadow: 0 4px 6px rgba(37,99,235,0.3); }

.kpi-container { position: relative; border-radius: 12px; padding: 1.4rem 1.1rem; text-align: center; min-height: 124px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03); border-width: 1px !important; border-style: solid !important; background: #ffffff; }
.kpi-container:hover { transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05); }
.kpi-label { font-size: .8rem !important; letter-spacing: .05em; text-transform: uppercase; margin-bottom: .5rem; font-weight: 700 !important; color: #64748b !important; }
.kpi-value { font-size: 1.9rem !important; font-weight: 800 !important; letter-spacing: -.02em; color: #0f172a !important; }
.card-primary { border-color: #cbd5e1 !important; border-top: 4px solid #2563eb !important; }
.card-neutral { border-color: #e2e8f0 !important; border-top: 4px solid #94a3b8 !important; }
.card-success { background: #f0fdf4 !important; border-color: #bbf7d0 !important; border-top: 4px solid #16a34a !important; }
.card-danger { background: #fef2f2 !important; border-color: #fecaca !important; border-top: 4px solid #dc2626 !important; }
.card-small { min-height: 90px !important; padding: 0.8rem 0.5rem !important; border-radius: 10px !important; }
.card-small .kpi-label { font-size: 0.72rem !important; margin-bottom: 0.2rem !important; }
.card-small .kpi-value { font-size: 1.45rem !important; }

.login-wrap { max-width:460px; margin:5rem auto 0; padding:2.8rem 2.5rem 1.5rem; background: #ffffff; border:1px solid #cbd5e1; border-radius:16px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05); }
.login-title { font-size: 2rem !important; font-weight: 800 !important; text-align: center; margin-bottom: .4rem; color: #1e293b; }
.login-sub { font-size: 1rem !important; text-align: center; color: #64748b; margin-bottom: 2rem; font-weight: 600 !important; }

.badge { display:inline-block; font-size:.72rem !important; border-radius:6px; padding:3px 11px; margin-left:6px; font-weight:800; letter-spacing:.05em; }
.badge-admin  { background:#eff6ff; border:1px solid #bfdbfe; color:#1d4ed8; }
.badge-expert { background:#f0fdf4; border:1px solid #bbf7d0; color:#166534; }
.badge-supervisor { background:#fefce8; border:1px solid #fef08a; color:#a16207; }
.req-pending  { background:#fffbeb; border:1px solid #fde047; border-radius:8px; padding:.85rem 1.4rem; margin-bottom:.8rem; color:#92400e; font-size:.95rem; font-weight:600; }
.section-card { background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:1.6rem 2rem; margin-bottom:1.4rem; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }

.scorecard-container { width: 100%; overflow-x: auto; margin-top: 1rem; margin-bottom: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
.scorecard-container table { width: 100%; border-collapse: collapse; background-color: #ffffff; font-family: inherit; table-layout: auto; }
.scorecard-container th { background-color: #f8fafc !important; color: #334155 !important; font-weight: 800 !important; font-size: 0.9rem !important; text-align: center !important; padding: 10px 8px !important; border-bottom: 2px solid #cbd5e1; }
.scorecard-container td { text-align: center !important; padding: 10px 8px !important; font-size: 0.95rem !important; border-bottom: 1px solid #f1f5f9; color: #1e293b; }
.scorecard-container td:first-child { font-weight: 700 !important; text-align: left !important; padding-left: 12px !important; }

.profile-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.5rem; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 1.5rem; transition: transform 0.2s; }
.profile-card:hover { transform: translateY(-5px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-color: #94a3b8; }
.profile-img { width: 110px; height: 110px; border-radius: 50%; object-fit: cover; object-position: top; border: 3px solid #2563eb; margin: 0 auto 1rem; padding: 2px; }
.profile-name { font-size: 1.3rem !important; font-weight: 800 !important; color: #0f172a; margin-bottom: 2px; }
.profile-role { font-size: 0.8rem !important; color: #64748b; margin-bottom: 1.2rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 700 !important; }
.profile-detail { font-size: 0.95rem !important; color: #334155; margin-bottom: 0.4rem; text-align: left; display:flex; justify-content: space-between; border-bottom: 1px dashed #f1f5f9; padding-bottom:4px; font-weight: 600 !important;}
.profile-bio { font-size: 0.95rem !important; font-style: italic; color: #475569; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; font-weight: 500 !important;}
</style>
""", unsafe_allow_html=True)

THEME = dict(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#1e293b", margin=dict(l=10, r=10, t=55, b=10))

# ══════════════════════════════════════════════════════════════════════════════════
#  GLOBALS & CONFIGURATIONS
# ══════════════════════════════════════════════════════════════════════════════════
DAYS_AR = {"Saturday": "Saturday", "Sunday": "
