"""
Group dashboard (MIS20080 Dashboard Project)

Run:  python3 -m streamlit run app.py

Home page: the four panels as small cards, two on top and two below. Click
a card's title to see the full panel, and "Back to overview" to return.

Each group member owns one panel file; to add yours, fill in your line in PANELS below.
A panel file can either
    * have a render() function (like panels/inflation.py), or
    * be a plain Streamlit script that draws as it runs.
Both work. If a panel crashes, only its own card or page shows the error.

Optional: a panel can also define render_card(), a small version of itself
(two numbers and one chart) for its card on the home page. Without it, the
card just shows the panel's name and author.
"""

import importlib.util
from pathlib import Path

import streamlit as st

# SETTINGS - tab name, file, author
PANELS = [
    ("Oil prices",            "panels/oil.py",       "Erin Dolly"),
    ("Shipping & Markets",  "panels/shipping.py",   "Anna Piazza"),
    ("Gas & LNG",             "panels/gas_lng.py",          "Eabha Kelly"),
    ("Inflation & households", "panels/inflation.py", "Eleena Golchin"),
]

TITLE = "Hormuz Shock: four ways the Strait's closure hits the world"
SUBTITLE = "MIS20080 Introduction to Programming · Group project · UCD 2026"

ROOT = Path(__file__).resolve().parent


def load_module(file: str, name: str):
    """Run a panel file as a module called `name` and return it."""
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)       # runs the file's top-level code
    return module


def show_panel(file: str) -> None:
    """Run one panel file in full.
    The file is loaded fresh each time, so its top-level code draws on the page.
    It is loaded as "__main__", so the `if __name__ == "__main__"` block runs
    too (that is where a panel calls render()).
    """
    if not (ROOT / file).exists():
        st.info(f"This panel is coming soon ({file} isn't in the repo yet).")
        return
    try:
        load_module(file, "__main__")
    except Exception as error:                # one broken panel can't break the rest
        st.error(f"This panel hit an error: {error}")
        st.exception(error)


def show_card(file: str) -> None:
    """The small version of a panel, drawn on the home page.
    Only panels that define render_card() are loaded here. They are loaded under
    another name, so nothing in them runs except the function we call.
    """
    path = ROOT / file
    if not path.exists():
        st.caption("Coming soon.")
    elif "def render_card" in path.read_text(encoding="utf-8"):
        try:
            load_module(file, f"card_{path.stem}").render_card()
        except Exception as error:
            st.error(f"This card hit an error: {error}")


def open_panel(name) -> None:
    """Button action: show this panel in full (None goes back to the overview)."""
    st.session_state["open_panel"] = name


st.set_page_config(page_title="Group dashboard", page_icon="📊", layout="wide")
# Some panels call st.set_page_config themselves; Streamlit only allows it
# once per page, so after this point it is switched off for the panels.
st.set_page_config = lambda *args, **kwargs: None

# Use the full width of the screen (the default leaves wide margins on both sides).
st.markdown("<style>.block-container{max-width:100%;padding-left:2rem;padding-right:2rem}</style>",
            unsafe_allow_html=True)
# On the overview, the panel's name is the card's title and also the click target:
# the button is drawn like a plain heading (no border), and gets a hover colour so it looks clickable.
CARD_TITLE_CSS = ("<style>div[data-testid='stButton'] > button{width:100%;justify-content:flex-start;"
                  "font-size:2.3rem;font-weight:700;line-height:1.2;padding:0.2rem 0 0.6rem;border:none;background:transparent;"
                  "box-shadow:none}"
                  "div[data-testid='stButton'] > button p{font-size:2.3rem;font-weight:700;line-height:1.2}"
                  "div[data-testid='stButton'] > button:hover{background:transparent;color:#2e6fd8}</style>")

st.title(TITLE)
st.caption(SUBTITLE)

current = st.session_state.get("open_panel")
details = {name: (file, author) for name, file, author in PANELS}

if current in details:                         # one panel in full
    file, author = details[current]
    st.button("← Back to overview", key="back", on_click=open_panel, args=(None,))
    st.header(current)
    show_panel(file)
    st.caption(f"Panel by {author} · {file}")
else:                                          # overview: two cards on top, two below
    st.markdown(CARD_TITLE_CSS, unsafe_allow_html=True)
    top, bottom = st.columns(2, gap="small"), st.columns(2, gap="small")
    for slot, (name, file, author) in zip(top + bottom, PANELS):
        with slot, st.container(border=True):
            st.button(f"{name}  →", key=f"open_{file}", on_click=open_panel, args=(name,))   # click to open
            show_card(file)
