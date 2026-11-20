"""
Group dashboard (MIS20080 Dashboard Project)

Run:  python3 -m streamlit run app.py

This file puts the four panels side by side as tabs. Each group member
owns one panel file; to add yours, fill in your line in PANELS below.
A panel file can either
    * have a render() function (like panels/inflation.py), or
    * be a plain Streamlit script that draws as it runs.
Both work. If a panel crashes, only its own tab shows the error.
"""

import importlib.util
from pathlib import Path

import streamlit as st

# =============================================================================
# SETTINGS - one line per panel: (tab name, file, author)
# =============================================================================
PANELS = [
    ("🛢️ Oil prices",            "panels/oil.py",       "Erin"),
    ("🚢 Shipping & insurance",  "panels/shipping.py",   "Anna Piazza"),
    ("🔥 Gas & LNG",             "panels/gas_lng.py",          "Eabha Kelly"),
    ("🧾 Inflation & households", "panels/inflation.py", "Eleena Golchin"),
]

TITLE = "Hormuz Shock: four ways the Strait's closure hits the world"
SUBTITLE = "MIS20080 Introduction to Programming · Group project · UCD 2026"

ROOT = Path(__file__).resolve().parent


def show_panel(file: str) -> None:
    """Run one panel file inside the current tab.

    The file is loaded fresh each time, so its top-level code draws into
    the tab. If it has a render() function, that is called as well.
    """
    path = ROOT / file
    if not path.exists():
        st.info(f"This panel is coming soon ({file} isn't in the repo yet).")
        return
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)       # runs the file's top-level code
        if hasattr(module, "render"):
            module.render()
    except Exception as error:                # one broken panel can't break the rest
        st.error(f"This panel hit an error: {error}")
        st.exception(error)


st.set_page_config(page_title="Group dashboard", page_icon="📊", layout="wide")
# Some panels call st.set_page_config themselves; Streamlit only allows it
# once per page, so after this point it is switched off for the panels.
st.set_page_config = lambda *args, **kwargs: None

st.title(TITLE)
st.caption(SUBTITLE)

tabs = st.tabs([name for name, _, _ in PANELS])
for tab, (name, file, author) in zip(tabs, PANELS):
    with tab:
        show_panel(file)
        st.caption(f"Panel by {author} · {file}")
      
