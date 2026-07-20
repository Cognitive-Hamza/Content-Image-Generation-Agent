import io
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import streamlit as st

from imagegen import config as igcfg
from imagegen.providers import generate_translation_image


def _translate_one(api_key, img_bytes, img_name, target_language,
                   provider_id, quality_tier, canvas_size, sector_info, colors):
    """Worker function: translate a single image to a single language. Returns dict."""
    file_like = io.BytesIO(img_bytes)
    file_like.name = img_name
    image_bytes, usage, error = generate_translation_image(
        api_key, file_like, target_language,
        provider_id, quality_tier, canvas_size,
        sector_info, colors,
    )
    return {
        "img_name": img_name,
        "language": target_language,
        "image_bytes": image_bytes,
        "error": error,
    }


def render_translation():
    main_col, controls_col = st.columns([65, 35], gap="medium")

    # ── RIGHT: Controls ──
    with controls_col:
        if st.button("Back to Home", key="trans_back"):
            st.session_state.page = "landing"
            st.rerun()

        st.markdown('<div class="panel-header">Batch Translate Posts</div>', unsafe_allow_html=True)

        # ── CREDENTIALS ──
        with st.expander("CREDENTIALS", expanded=True):
            provider_label = st.selectbox(
                "Provider",
                ["gpt-image-2 (OpenAI) -- Default", "gpt-image-1 (OpenAI)"],
                index=0,
                key="trans_prov",
                help="Translation uses OpenAI's image edit endpoint",
            )
            provider_id = {
                "gpt-image-2 (OpenAI) -- Default": "gpt-image-2",
                "gpt-image-1 (OpenAI)": "gpt-image-1",
            }[provider_label]
            quality_tier = "low"
            env_key = os.getenv("OPENAI_API_KEY", "")
            if env_key:
                st.success("Using OPENAI_API_KEY from environment.")
                api_key = env_key
                if st.checkbox("Override with a different key for this session", key="trans_override_cb"):
                    typed = st.text_input("API Key", type="password", key="trans_api")
                    if typed:
                        api_key = typed
            else:
                api_key = st.text_input("API Key", type="password", key="trans_api")

        # ── UPLOAD IMAGES ──
        with st.expander("UPLOAD IMAGES (up to 100)", expanded=True):
            ref_images = st.file_uploader(
                "Upload posts to translate",
                type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True,
                key="trans_imgs",
            )
            if ref_images and len(ref_images) > 100:
                st.warning("Maximum 100 images. Only the first 100 will be used.")
                ref_images = ref_images[:100]

        # ── LANGUAGES ──
        with st.expander("TARGET LANGUAGES", expanded=True):
            target_languages = st.multiselect(
                "Select one or more languages",
                igcfg.TRANSLATION_LANGUAGES,
                default=["Urdu"],
                key="trans_langs",
            )

    # ── Derived values ──
    sector = "Al Nafi International College"
    sector_info = igcfg.ALNAFI_SECTORS[sector]
    colors = {
        "primary": sector_info["color_primary"],
        "secondary": sector_info["color_secondary"],
        "accent": sector_info["color_accent"],
    }
    canvas_size = "1080x1080"

    n_images = len(ref_images) if ref_images else 0
    n_langs = len(target_languages)
    total_jobs = n_images * n_langs

    # ── LEFT: Workspace ──
    with main_col:
        st.markdown(
            '<h2 style="margin:0 0 4px 0; color:#2D6FBC;">Batch Translate Posts</h2>',
            unsafe_allow_html=True,
        )

        # Status bar
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            pill = "pill-ready" if n_images else "pill-missing"
            st.markdown(f'<span class="status-pill {pill}">{n_images} image{"s" if n_images != 1 else ""}</span>', unsafe_allow_html=True)
        with s2:
            pill = "pill-ready" if n_langs else "pill-missing"
            st.markdown(f'<span class="status-pill {pill}">{n_langs} language{"s" if n_langs != 1 else ""}</span>', unsafe_allow_html=True)
        with s3:
            pill = "pill-ready" if total_jobs else "pill-missing"
            st.markdown(f'<span class="status-pill {pill}">{total_jobs} total jobs</span>', unsafe_allow_html=True)
        with s4:
            pill = "pill-ready" if api_key else "pill-missing"
            st.markdown(f'<span class="status-pill {"pill-ready" if api_key else "pill-missing"}">{"API Ready" if api_key else "No API Key"}</span>', unsafe_allow_html=True)

        # Preview thumbnails of uploaded images
        if ref_images:
            st.markdown("**Uploaded images:**")
            thumb_cols = st.columns(min(n_images, 5))
            for i, img_file in enumerate(ref_images[:5]):
                with thumb_cols[i]:
                    st.image(img_file, use_container_width=True, caption=img_file.name[:18])
            if n_images > 5:
                st.caption(f"... and {n_images - 5} more")
        else:
            st.info("Upload images from the right panel to get started.")

        st.markdown("")

        # Translate button
        can_gen = n_images > 0 and n_langs > 0 and bool(api_key)
        gen_btn = st.button(
            f"Translate {total_jobs} image{'s' if total_jobs != 1 else ''}  (20 parallel workers)",
            type="primary",
            use_container_width=True,
            disabled=not can_gen,
            key="trans_gen_btn",
        )

        if gen_btn and can_gen:
            # Read all file bytes upfront (UploadedFile is not thread-safe)
            image_payloads = [(f.name, f.read()) for f in ref_images]

            # Build all (img_name, img_bytes, language) jobs
            jobs = [
                (name, data, lang)
                for name, data in image_payloads
                for lang in target_languages
            ]

            progress_bar = st.progress(0.0, text="Starting...")
            status_placeholder = st.empty()
            results = []
            errors = []
            start_time = time.time()

            with ThreadPoolExecutor(max_workers=20) as executor:
                future_map = {
                    executor.submit(
                        _translate_one,
                        api_key, img_bytes, img_name, lang,
                        provider_id, quality_tier, canvas_size, sector_info, colors,
                    ): (img_name, lang)
                    for img_name, img_bytes, lang in jobs
                }

                completed = 0
                for future in as_completed(future_map):
                    completed += 1
                    img_name, lang = future_map[future]
                    try:
                        res = future.result()
                    except Exception as exc:
                        res = {"img_name": img_name, "language": lang,
                               "image_bytes": None, "error": str(exc)}

                    if res["error"]:
                        errors.append(res)
                    else:
                        results.append(res)

                    pct = completed / total_jobs
                    progress_bar.progress(pct, text=f"{completed}/{total_jobs} done — {img_name} → {lang}")
                    status_placeholder.caption(f"Completed {completed}/{total_jobs}")

            elapsed = time.time() - start_time
            progress_bar.progress(1.0, text="Done!")
            status_placeholder.empty()

            st.success(f"Finished {len(results)} translations in {elapsed:.1f}s  ({len(errors)} errors)")

            if errors:
                with st.expander(f"{len(errors)} failed jobs"):
                    for e in errors:
                        st.error(f"{e['img_name']} → {e['language']}: {e['error']}")

            # ── ZIP download ──
            if results:
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for res in results:
                        base = os.path.splitext(res["img_name"])[0]
                        lang_safe = res["language"].lower().replace(" ", "_").replace("/", "").replace("(", "").replace(")", "")
                        zf.writestr(f"{base}_{lang_safe}.png", res["image_bytes"])
                zip_buf.seek(0)
                st.download_button(
                    f"Download all {len(results)} images as ZIP",
                    data=zip_buf,
                    file_name=f"alnafi_translations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

                # ── Per-language result grid ──
                for lang in target_languages:
                    lang_results = [r for r in results if r["language"] == lang]
                    if not lang_results:
                        continue
                    st.markdown(f"#### {lang}")
                    grid_cols = st.columns(min(len(lang_results), 3))
                    for i, res in enumerate(lang_results):
                        with grid_cols[i % 3]:
                            st.image(res["image_bytes"], caption=res["img_name"], use_container_width=True)
                            base = os.path.splitext(res["img_name"])[0]
                            lang_safe = res["language"].lower().replace(" ", "_").replace("/", "").replace("(", "").replace(")", "")
                            st.download_button(
                                "Download",
                                data=res["image_bytes"],
                                file_name=f"{base}_{lang_safe}.png",
                                mime="image/png",
                                use_container_width=True,
                                key=f"dl_{base}_{lang_safe}_{i}",
                            )
