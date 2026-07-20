import streamlit as st

from db import content_repo, image_repo


def render_landing():
    st.markdown(
        """
        <div style="text-align:center; padding: 30px 0 10px 0;">
            <h1 style="margin:0; color:#2D6FBC; font-size:36px;">Al-Nafi Content &amp; Image Pipeline</h1>
            <p style="color:#666; margin:6px 0 0 0; font-size:16px;">
                Write, generate, and translate social media content for Al-Nafi Group
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")

    card_content, card_image, card_translate, card_history = st.columns(4)

    with card_content:
        st.markdown(
            """
            <div class="landing-card">
                <div class="landing-icon">C</div>
                <h2>Generate Content</h2>
                <p>
                    Research, write, and refine blog posts, articles, pillar pages,
                    LinkedIn articles, or social captions. Send the result straight
                    to the image generator when you're done.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Start Writing", type="primary", use_container_width=True, key="go_content"):
            st.session_state.page = "content"
            st.rerun()

    with card_image:
        st.markdown(
            """
            <div class="landing-card">
                <div class="landing-icon">+</div>
                <h2>Generate New Post</h2>
                <p>
                    Create fresh social media graphics from scratch.
                    Pick your sector, fill in content, choose visuals,
                    and generate with AI. Works standalone too.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Start Generating", type="primary", use_container_width=True, key="go_gen"):
            st.session_state.page = "generation"
            st.rerun()

    with card_translate:
        st.markdown(
            """
            <div class="landing-card">
                <div class="landing-icon">T</div>
                <h2>Translate Existing Post</h2>
                <p>
                    Upload an existing post image,
                    pick a target language, and regenerate
                    the same design in another language.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Start Translating", type="primary", use_container_width=True, key="go_trans"):
            st.session_state.page = "translation"
            st.rerun()

    with card_history:
        content_total = len(content_repo.list_recent(9999))
        image_total = len(image_repo.load_all_posts(limit=9999))
        st.markdown(
            f"""
            <div class="landing-card">
                <div class="landing-icon">H</div>
                <h2>History</h2>
                <p>
                    Browse every piece of content and every image generated so far.
                    Pick one to view, reuse, or send straight to the image generator.<br>
                    <strong>{content_total} content &nbsp;|&nbsp; {image_total} image{"s" if image_total != 1 else ""}</strong>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Open History", type="primary", use_container_width=True, key="go_hist"):
            st.session_state.page = "history"
            st.rerun()
