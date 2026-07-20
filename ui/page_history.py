import streamlit as st

from db import content_repo, image_repo
from ui._shared import render_content_history_row


def _render_content_history():
    rows = content_repo.list_recent(50)
    if not rows:
        st.info("No content generated yet. Generate your first piece to see it here.")
        return

    st.markdown(f"**{len(rows)} generation(s) saved**")
    search = st.text_input("Search by topic or platform", placeholder="e.g. AIOps, Academy...", key="hist_content_search")
    if search:
        q = search.lower()
        rows = [r for r in rows if q in (r["topic"] or "").lower() or q in (r["platform"] or "").lower()]

    st.markdown("---")
    for r in rows:
        render_content_history_row(r, key_prefix="hist_content")


def _render_image_history():
    posts = image_repo.load_all_posts()
    if not posts:
        st.info("No posts generated yet. Generate your first post to see it here.")
        return

    st.markdown(f"**{len(posts)} post(s) saved**")
    st.markdown("---")

    # Search / filter bar
    search = st.text_input("Search by headline or sector", placeholder="e.g. Azure, Academy...", key="hist_search")
    if search:
        q = search.lower()
        posts = [p for p in posts if q in (p["headline"] or "").lower() or q in (p["sector"] or "").lower()]

    for i in range(0, len(posts), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            if i + j >= len(posts):
                break
            p = posts[i + j]
            with col:
                img_bytes = p["image_data"]
                ts = p["timestamp"][:19].replace("T", "  ")
                st.image(img_bytes, use_container_width=True)
                st.markdown(
                    f"**{p['headline'] or '(no headline)'}**  \n"
                    f"<span style='font-size:11px;color:#888;'>{p['sector']} &nbsp;|&nbsp; "
                    f"{p['post_type']} &nbsp;|&nbsp; {p['canvas_size']}</span>  \n"
                    f"<span style='font-size:10px;color:#555;'>{ts}</span>",
                    unsafe_allow_html=True,
                )
                dl_name = f"alnafi_{(p['post_type'] or 'post').lower().replace(' ','_')}_{p['id']}.png"
                st.download_button(
                    "Download",
                    data=img_bytes,
                    file_name=dl_name,
                    mime="image/png",
                    use_container_width=True,
                    key=f"dl_{p['id']}",
                )
                if p.get("generation_id"):
                    src = content_repo.get_generation(p["generation_id"])
                    if src:
                        with st.expander("View source content", expanded=False):
                            st.markdown(
                                f"**Topic:** {src['topic']}  \n"
                                f"**Type:** {src['content_type']}  \n"
                                f"**Created:** {src['created_at']}"
                            )
                with st.expander("Prompts", expanded=False):
                    st.markdown("**Image Prompt**")
                    st.code(p["image_prompt"] or "", language="text")
                    if p.get("system_prompt"):
                        st.markdown("**System Prompt**")
                        st.code(p["system_prompt"], language="text")
                if st.button("Delete", key=f"del_{p['id']}", type="secondary"):
                    image_repo.delete_post_from_db(p["id"])
                    st.rerun()
                st.markdown("---")


def render_history():
    st.markdown(
        '<h2 style="margin:0 0 8px 0; color:#2D6FBC;">History</h2>',
        unsafe_allow_html=True,
    )

    if st.button("Back to Home", key="hist_back"):
        st.session_state.page = "landing"
        st.rerun()

    tab_content, tab_images = st.tabs(["Generated Content", "Generated Images"])
    with tab_content:
        _render_content_history()
    with tab_images:
        _render_image_history()
