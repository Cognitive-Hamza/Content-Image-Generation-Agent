"""Small helpers shared between the Generate Content and History pages —
kept out of pipeline/ and imagegen/ because they write directly to
st.session_state, which makes them UI glue rather than business logic."""
from pathlib import Path

import streamlit as st

from db import content_repo
from pipeline.brief import parse_content_design_brief

# Content-side platform display names -> imagegen sector keys. Most match
# verbatim; a couple of the sub-brands are spelled slightly differently
# between the two agents (e.g. "Al Nafi Cloud" vs "Alnafi Cloud").
PLATFORM_TO_SECTOR = {
    "Al Nafi International College": "Al Nafi International College",
    "Al Nafi Islamic College": "Al Nafi Islamic College",
    "Al Nafi Academy": "Al Nafi Academy",
    "Al Nafi Cloud": "Alnafi Cloud",
    "Annaafi ePay": "Annaafi PAY",
}

# Content type -> the closest matching imagegen Post Type. Long-form written
# content maps to "Blog Thumbnail" (the layout imagegen already special-cases
# for a headline + visual split); captions map to a plain "General Post".
CONTENT_TYPE_TO_POST_TYPE = {
    "Blog Post": "Blog Thumbnail",
    "Article": "Blog Thumbnail",
    "Pillar Page": "Blog Thumbnail",
    "LinkedIn Article": "Blog Thumbnail",
    "Social Media Captions": "General Post",
}


def send_content_to_image_generator(content_type: str, plat_name: str, content: str, db_id: int | None) -> bool:
    """Parse the Content Design Brief out of `content` and stage it in
    session_state so the Generate Image page picks it up as prefill defaults.
    Returns False (and does nothing) if no brief was found — e.g. social
    captions don't produce one."""
    brief = parse_content_design_brief(content)
    if brief.is_empty:
        return False

    st.session_state["gen_hl"] = brief.headline
    st.session_state["gen_hook"] = brief.hook_line
    st.session_state["gen_title"] = brief.title

    # The Visual Recommendation only shows up if the VISUALS panel's
    # background-category selectbox is switched to "Custom Visual" — that
    # selectbox (bg_cat) gates whether the bg_custom_area text box even
    # renders, so it must be set alongside the text itself.
    st.session_state["bg_cat"] = "Custom Visual"
    st.session_state["bg_custom_area"] = brief.visual_recommendation

    if content_type in CONTENT_TYPE_TO_POST_TYPE:
        st.session_state["gen_pt"] = CONTENT_TYPE_TO_POST_TYPE[content_type]
    if plat_name in PLATFORM_TO_SECTOR:
        st.session_state["gen_sector"] = PLATFORM_TO_SECTOR[plat_name]

    st.session_state["prefill_generation_id"] = db_id
    st.session_state["prefill_from_content"] = True
    return True


def render_content_history_row(row, key_prefix: str = "hist"):
    """One past content generation, expandable to its full text, with a
    'Send to Image Generator' action — used on both the Generate Content
    page's quick History mode and the main (landing-page) History page."""
    label = f"[{row['id']}] {row['created_at']} — {row['content_type']} ({row['platform']}) — {row['topic']}"
    with st.expander(label):
        full = content_repo.get_generation(row["id"])
        if not full:
            st.error("Record not found.")
            return
        st.markdown(full["final_content"])

        dl_name = Path(full["filepath"]).name if full["filepath"] else f"content_{row['id']}.md"
        st.download_button(
            "Download",
            data=full["final_content"],
            file_name=dl_name,
            mime="text/markdown",
            key=f"{key_prefix}_dl_{row['id']}",
        )

        if st.button("Send to Image Generator →", key=f"{key_prefix}_send_{row['id']}"):
            sent = send_content_to_image_generator(
                full["content_type"], full["platform"], full["final_content"], full["id"],
            )
            if sent:
                st.session_state.page = "generation"
                st.rerun()
            else:
                st.warning("No Content Design Brief found in this piece — nothing to auto-fill.")
