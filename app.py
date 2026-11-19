"""Hygron unified local application."""
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Hygron",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "dashboard_dark_mode" not in st.session_state:
    st.session_state.dashboard_dark_mode = True

dark_mode = st.session_state.dashboard_dark_mode

with st.sidebar:
    st.markdown("### HYGRON")
    st.caption("Environmental monitoring")
    st.toggle(
        "Dark mode",
        key="dashboard_dark_mode",
        help="Switch the Hygron appearance.",
    )

if dark_mode:
    theme_css = """
    :root {
        --hy-bg: #1c1c1e;
        --hy-surface: #2c2c2e;
        --hy-text: #f5f5f7;
        --hy-muted: #d1d1d6;
        --hy-primary: #0a84ff;
        --hy-border: rgba(255,255,255,.18);
    }
    [data-testid="stSidebar"] { background: #161618 !important; border-right: 1px solid var(--hy-border); }
    [data-testid="stSidebar"] * { color: #f5f5f7 !important; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #d1d1d6 !important; }
    """
else:
    theme_css = """
    :root {
        --hy-bg: #f5f5f7;
        --hy-surface: #ffffff;
        --hy-text: #1d1d1f;
        --hy-muted: #6e6e73;
        --hy-primary: #0071e3;
        --hy-border: rgba(128,128,128,.22);
    }
    [data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid var(--hy-border); }
    [data-testid="stSidebar"] * { color: #1d1d1f !important; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #6e6e73 !important; }
    """

st.markdown(
    f"""
    <style>
    {theme_css}
    .stApp {{ background: var(--hy-bg); }}
    [data-testid="stHeader"] {{ background: var(--hy-bg) !important; }}
    [data-testid="stSidebar"] {{
        padding: 18px 16px;
    }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {{
        font-size: .76rem !important;
        font-weight: 750;
        letter-spacing: .12em;
        text-transform: uppercase;
        margin: 6px 8px 14px;
    }}
    [data-testid="stSidebar"] [data-testid="stPageLink"] {{
        border-radius: 11px;
        padding: 3px 5px;
        margin: 3px 0;
    }}
    [data-testid="stSidebar"] [data-testid="stPageLink"]:hover {{
        background: rgba(128,128,128,.12);
    }}
    [data-testid="stSidebar"] [data-testid="stCheckbox"] {{
        margin: 14px 8px 0;
    }}
    [data-testid="stStatusWidget"],
    [data-testid="stBottomBlockContainer"],
    [data-testid="stFooter"],
    footer,
    a[href*="streamlit.io"] {{
        display: none !important;
        visibility: hidden !important;
    }}
    footer, [data-testid="stFooter"], a[href*="streamlit.io"], [class*="viewerBadge"] {{
        display:none !important;
        visibility:hidden !important;
        height:0 !important;
    }}
    [data-testid="stMain"] h1,
    [data-testid="stMain"] h2,
    [data-testid="stMain"] h3 {{ color: var(--hy-text) !important; }}
    [data-testid="stMain"] p,
    [data-testid="stMain"] label,
    [data-testid="stMain"] li {{ color: var(--hy-muted) !important; }}
    [data-testid="stMetric"] {{
        background: var(--hy-surface) !important;
        border: 1px solid var(--hy-border) !important;
    }}
    [data-testid="stMetricLabel"] {{ color: var(--hy-muted) !important; }}
    [data-testid="stMetricValue"] {{ color: var(--hy-text) !important; }}
    [data-testid="stDataFrame"] {{
        border: 1px solid var(--hy-border) !important;
    }}
    [data-testid="stExpander"] {{
        background: var(--hy-surface) !important;
        border-color: var(--hy-border) !important;
    }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary * {{ color: var(--hy-text) !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

dashboard_page = st.Page(
    str(ROOT / "dashboard" / "app.py"),
    title="Dashboard",
    icon=":material/dashboard:",
    url_path="dashboard",
    default=True,
)
methodology_page = st.Page(
    str(ROOT / "dashboard" / "methodology.py"),
    title="Methodology",
    icon=":material/info:",
    url_path="methodology",
)
workbench_page = st.Page(
    str(ROOT / "simulation" / "app.py"),
    title="IoT Workbench",
    icon=":material/memory:",
    url_path="workbench",
)

navigation = st.navigation(
    {
        "Hygron": [dashboard_page, methodology_page, workbench_page],
    }
)
navigation.run()
