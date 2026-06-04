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
    background: linear-gradient
