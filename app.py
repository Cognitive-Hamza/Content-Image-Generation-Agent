"""
Al-Nafi Content & Image Pipeline

Single Streamlit entrypoint merging the content-generation agent (research ->
write -> refine, plus social captions) and the image-generation agent
(OpenAI / Gemini image generation with brand logo overlays, plus batch
translation) into one app. Each half also works fully standalone — the
"send to image generator" hand-off is an optional accelerator, not a
requirement.
"""
from dotenv import load_dotenv

load_dotenv()  # Must run before pipeline/tools imports — Anthropic/Tavily read env vars at instantiation

import streamlit as st

from ui.page_generate_content import render_generate_content
from ui.page_generate_image import render_generation
from ui.page_history import render_history
from ui.page_landing import render_landing
from ui.page_translate import render_translation

st.set_page_config(
    page_title="Al-Nafi Content & Image Pipeline",
    page_icon="AN",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    [data-testid="collapsedControl"] { display: none; }
    .stApp { background-color: #FFFFFF; }

    .panel-header {
        background: linear-gradient(135deg, #2D6FBC 0%, #5B9BE0 100%);
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        margin: 6px 0;
        font-weight: 700;
        font-size: 14px;
        letter-spacing: 0.5px;
        text-align: center;
    }

    .prompt-box {
        background: #F5F9FF;
        border: 1px solid #2D6FBC;
        border-radius: 10px;
        padding: 16px;
        font-family: monospace;
        font-size: 13px;
        color: #1A2B3C;
        white-space: pre-wrap;
        max-height: 400px;
        overflow-y: auto;
    }

    .status-pill {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        margin: 2px 4px;
    }
    .pill-ready { background: #DFF5E1; color: #1B5E20; }
    .pill-missing { background: #FDEAEA; color: #B71C1C; }

    .landing-card {
        background: linear-gradient(145deg, #FFFFFF 0%, #EAF3FF 100%);
        border: 1px solid #CFE3FF;
        border-radius: 16px;
        padding: 40px 30px;
        text-align: center;
        transition: border-color 0.2s;
    }
    .landing-card:hover { border-color: #2D6FBC; }
    .landing-card h2 { color: #1A4A8A; margin: 16px 0 8px 0; font-size: 24px; }
    .landing-card p { color: #5A6B7A; font-size: 14px; line-height: 1.5; }
    .landing-icon { font-size: 42px; color: #2D6FBC; font-weight: 700; }

    .ref-image-frame {
        border: 2px solid #CFE3FF;
        border-radius: 12px;
        padding: 8px;
        background: #F5F9FF;
    }

    .logo-preview {
        background: #F5F9FF;
        border: 1px solid #CFE3FF;
        border-radius: 10px;
        padding: 12px;
        margin: 8px 0;
        text-align: center;
    }
</style>
""",
    unsafe_allow_html=True,
)

if "page" not in st.session_state:
    st.session_state.page = "landing"

page = st.session_state.page

if page == "landing":
    render_landing()
elif page == "content":
    render_generate_content()
elif page == "generation":
    render_generation()
elif page == "translation":
    render_translation()
elif page == "history":
    render_history()
else:
    st.session_state.page = "landing"
    st.rerun()
