import streamlit as st

from db import content_repo
from pipeline import config as pcfg
from pipeline.brief import parse_content_design_brief
from pipeline.page_finder import HIGH_CONFIDENCE_THRESHOLD, find_best_page
from pipeline.pipeline import generate_long_form_content, generate_social_captions
from ui._shared import render_content_history_row, send_content_to_image_generator


def _page_picker_multi(plat_name: str, pages: dict, default_key: str):
    """Free-text 'type a subject' page picker (e.g. type "AIOps" instead of
    scrolling a ~90-entry dropdown) that supports adding MORE THAN ONE page
    to promote in the same piece — useful for a Pillar Page or Article that
    reasonably covers several related programs. Returns a list of
    (name, url, description) tuples; falls back to the platform's single
    default page when nothing has been added yet."""
    state_key = f"cc_selected_pages__{plat_name}"
    if state_key not in st.session_state:
        st.session_state[state_key] = []

    # A text_input's session_state value can't be reset after the widget has
    # already been instantiated in the same run — bumping this counter to
    # change the widget's key is the standard workaround to clear the search
    # box once a page has been added, so the user can search the next topic.
    reset_key = "cc_page_query_reset_counter"
    if reset_key not in st.session_state:
        st.session_state[reset_key] = 0

    query = st.text_input(
        'Search a topic to add (e.g. "AIOps", "Cyber Security", "IELTS")',
        key=f"cc_page_query_{st.session_state[reset_key]}",
    )
    if query:
        matches = find_best_page(query, platform=plat_name, top_n=5)
        if not matches:
            st.warning("No matches found for this platform.")
        else:
            labels = [f"{m.page_name} — {m.url}" for m in matches]
            if matches[0].score >= HIGH_CONFIDENCE_THRESHOLD:
                st.success(f"Matched: **{matches[0].page_name}** → {matches[0].url}")
                best = matches[0]
                if st.checkbox("Not right? Choose from other matches", key="cc_page_change"):
                    choice = st.radio("Other matches", labels, key="cc_page_alt")
                    best = matches[labels.index(choice)]
            else:
                st.info("No high-confidence match — pick the closest one:")
                choice = st.radio("Closest matches", labels, key="cc_page_alt2")
                best = matches[labels.index(choice)]

            if st.button("+ Add this page to promote", key="cc_page_add"):
                entry = (best.page_name, best.url, best.description)
                if entry not in st.session_state[state_key]:
                    st.session_state[state_key].append(entry)
                st.session_state[reset_key] += 1
                st.rerun()

    selected = st.session_state[state_key]
    if selected:
        st.markdown(f"**Pages to promote ({len(selected)}):**")
        for i, (name, url, _desc) in enumerate(selected):
            row_l, row_r = st.columns([5, 1])
            with row_l:
                st.caption(f"{i + 1}. {name} — {url}")
            with row_r:
                if st.button("Remove", key=f"cc_page_remove_{i}"):
                    selected.pop(i)
                    st.rerun()
        return selected

    name, url, desc = pages.get(default_key, list(pages.values())[0])
    st.caption(f"No topics added yet — using default: {name} — {url}")
    return [(name, url, desc)]


def render_generate_content():
    st.markdown('<h2 style="margin:0 0 4px 0; color:#2D6FBC;">Generate Content</h2>', unsafe_allow_html=True)
    if st.button("Back to Home", key="cc_back"):
        st.session_state.page = "landing"
        st.rerun()

    mode = st.radio("Mode", ["New", "History", "Retrieve by ID"], horizontal=True, key="cc_mode")

    if mode == "History":
        st.caption("Full history with search also lives on the History page from the home screen.")
        rows = content_repo.list_recent(15)
        if not rows:
            st.info("No previous generations yet.")
        else:
            for r in rows:
                render_content_history_row(r, key_prefix="cc_hist")
        return

    if mode == "Retrieve by ID":
        row_id = st.number_input("ID", min_value=1, step=1, key="cc_retrieve_id")
        if st.button("Retrieve", key="cc_retrieve_btn"):
            row = content_repo.get_generation(int(row_id))
            if row:
                st.markdown(
                    f"**Topic:** {row['topic']}  \n**Platform:** {row['platform']}  \n"
                    f"**Type:** {row['content_type']}  \n**Created:** {row['created_at']}"
                )
                st.markdown("---")
                st.markdown(row["final_content"])
                if st.button("Send to Image Generator →", key="cc_retrieve_send"):
                    sent = send_content_to_image_generator(
                        row["content_type"], row["platform"], row["final_content"], row["id"],
                    )
                    if sent:
                        st.session_state.page = "generation"
                        st.rerun()
                    else:
                        st.warning("No Content Design Brief found in this piece — nothing to auto-fill.")
            else:
                st.error("Record not found.")
        return

    # ── New generation ──
    topic = st.text_input("Topic", key="cc_topic")
    keywords = st.text_input("Target keywords (comma-separated)", key="cc_keywords")
    audience = st.text_input("Target audience", value="general readers", key="cc_audience")

    content_type_label = st.selectbox(
        "Content Type", [v[0] for v in pcfg.CONTENT_TYPES.values()], key="cc_content_type"
    )
    content_type, word_count = next(v for v in pcfg.CONTENT_TYPES.values() if v[0] == content_type_label)

    chosen_platforms, post_type, caption_goal = [], "", ""
    tone = "Professional"
    if content_type == "Social Media Captions":
        chosen_platforms = st.multiselect(
            "Which platforms?", ["LinkedIn", "Instagram", "Twitter/X", "Facebook"],
            default=["LinkedIn", "Instagram", "Twitter/X", "Facebook"], key="cc_soc_platforms",
        )
        post_type = st.selectbox("Post Type", list(pcfg.SOCIAL_POST_TYPES.values()), key="cc_post_type")
        caption_goal = st.selectbox(
            "Caption Goal",
            ["Drive enrollment / link clicks", "Build brand awareness",
             "Get comments and engagement", "Share knowledge / educate"],
            key="cc_caption_goal",
        )
    else:
        tone = st.selectbox("Tone", list(pcfg.TONES.values()), key="cc_tone")

    plat_label = st.selectbox("Platform", [v[0] for v in pcfg.PLATFORMS.values()], key="cc_platform")
    plat_name, plat_domain, plat_pages, plat_default = next(
        v for v in pcfg.PLATFORMS.values() if v[0] == plat_label
    )

    selected_pages = _page_picker_multi(plat_name, plat_pages, plat_default)
    alnafi_promo = "\n\n".join(
        f"{i + 1}. {name} ({plat_name}): {url}\n    {desc}"
        for i, (name, url, desc) in enumerate(selected_pages)
    )

    if st.button("Generate", type="primary", key="cc_generate_btn", disabled=not topic):
        status_box = st.status("Starting...", expanded=True)

        def on_stage(stage):
            labels = {"researching": "Researching...", "writing": "Writing...",
                      "refining": "Refining...", "done": "Done!"}
            status_box.update(label=labels.get(stage, stage))

        if content_type == "Social Media Captions":
            status_box.update(label="Writing captions...")
            result = generate_social_captions(
                topic=topic, keywords=keywords, audience=audience,
                plat_name=plat_name, plat_domain=plat_domain, alnafi_promo=alnafi_promo,
                chosen_platforms=chosen_platforms, post_type=post_type, caption_goal=caption_goal,
            )
            status_box.update(label="Done!", state="complete")
            content, db_id = result.content, result.db_id
        else:
            result = generate_long_form_content(
                topic=topic, keywords=keywords, audience=audience,
                content_type=content_type, word_count=word_count, tone=tone,
                plat_name=plat_name, plat_domain=plat_domain, alnafi_promo=alnafi_promo,
                on_stage=on_stage,
            )
            status_box.update(label="Done!", state="complete")
            content, db_id = result.final_content, result.db_id

        st.session_state["cc_last_content"] = content
        st.session_state["cc_last_db_id"] = db_id
        st.session_state["cc_last_content_type"] = content_type
        st.session_state["cc_last_plat_name"] = plat_name

    if st.session_state.get("cc_last_content"):
        st.markdown("---")
        st.markdown(st.session_state["cc_last_content"])

        brief = parse_content_design_brief(st.session_state["cc_last_content"])
        st.markdown("---")
        if not brief.is_empty:
            st.markdown("**Content Design Brief detected** — send it straight to the image generator:")
            if st.button("Send to Image Generator →", key="cc_send_to_image"):
                send_content_to_image_generator(
                    st.session_state.get("cc_last_content_type", ""),
                    st.session_state.get("cc_last_plat_name", ""),
                    st.session_state["cc_last_content"],
                    st.session_state.get("cc_last_db_id"),
                )
                st.session_state.page = "generation"
                st.rerun()
        else:
            st.caption("No Content Design Brief detected in this output (social captions don't include one) — "
                       "nothing to auto-fill on the image page.")
