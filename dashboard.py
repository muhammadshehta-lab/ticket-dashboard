import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import urllib.parse

# ── 1. إعدادات الصفحة ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="In-Store Performance Hub", 
    page_icon="💊", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# ── 2. تصميم الواجهة (CSS) ──────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background: #0d1117; color: #e6edf3; }
    .kpi-container {
        border-radius: 14px; padding: 1.2rem 0.8rem; text-align: center;
        min-height: 110px; display: flex; flex-direction: column;
        justify-content: center; margin-bottom: 1rem;
    }
    .kpi-label { 
        font-size: 0.72rem; letter-spacing: .1em; 
        text-transform: uppercase; color: #8b949e; 
        margin-bottom: .4rem; font-weight: 600; 
    }
    .kpi-value { font-size: 1.5rem; font-weight: 800; }
    .card-total { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }
    .card-completed { background: #12221b; border: 1px solid #3fb950; color: #3fb950; }
    .card-issue { background: #261f12; border: 1px solid #d29922; color: #d29922; }
    .card-frt { background: #2b1c11; border: 1px solid #f0883e; color: #f0883e; }
    .card-aht { background: #221230; border: 1px solid #bc8cff; color: #bc8cff; }
    .card-tat { background: #111a2e; border: 1px solid #58a6ff; color: #58a6ff; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        background-color: #161b22; border-radius: 10px 10px 0 0; 
        padding: 10px 20px; color: #8b949e; 
    }
    .stTabs [aria-selected="true"] { 
        background-color: #1e3a8a !important; color: white !important; 
    }
</style>
""", unsafe_allow_html=True)

THEME = dict(
    template="plotly_dark", 
    paper_bgcolor="rgba(0,0,0,0)", 
    plot_bgcolor="rgba(0,0,0,0)", 
    font_color="#c9d1d9", 
    margin=dict(l=10, r=10, t=50, b=10)
)

# ── 3. دوال مساعدة ──────────────────────────────────────────────────────────
def kpi_colored(label, value, card_class):
    return f"""
    <div class="kpi-container {card_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """

def time_to_minutes(s):
    try:
        parts = str(s).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except: 
        return 0

def format_minutes_to_hhmmss(minutes_val):
    if pd.isna(minutes_val) or minutes_val <= 0: 
        return "00:00:00"
    total_seconds = int(round(minutes_val * 60))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def assign_time_tier(m):
    if m <= 15: return "Under 15 Mins"
    if m <= 30: return
