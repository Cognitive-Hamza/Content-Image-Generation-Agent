import json
from datetime import date, datetime
from datetime import time as dt_time

import streamlit as st

from imagegen import config as igcfg
from imagegen.credentials import resolve_api_key
from imagegen.logos import get_accreditation_logos_html, get_sector_logo_html
from imagegen.prompting import build_image_prompt, build_system_prompt
from imagegen.providers import run_image_generation
from pipeline import config as pcfg
from pipeline.page_finder import find_best_page
from pipeline.pipeline import generate_quick_copy


def render_credentials_panel():
    """Render credentials controls. Returns (provider_label, provider_id, api_key, quality_tier).
    Prefers an API key from the environment (OPENAI_API_KEY / GEMINI_API_KEY);
    only prompts for manual entry when no environment key is present, or when
    the user explicitly opts to override it for this session. A manually
    entered key is never persisted — same guarantee as before this merge."""
    with st.expander("CREDENTIALS", expanded=True):
        provider_label = st.selectbox(
            "Provider",
            list(igcfg.PROVIDERS.keys()),
            index=0,
            key="prov_sel",
        )
        provider_id = igcfg.PROVIDERS[provider_label]

        api_key = ""
        quality_tier = "medium"

        if provider_id == "prompt-only":
            st.info("Prompt Only -- no API key needed.")
        else:
            env_key, source = resolve_api_key(provider_id)
            env_var_name = "OPENAI_API_KEY" if provider_id in ("gpt-image-2", "gpt-image-1") else "GEMINI_API_KEY"
            if source == "env":
                st.success(f"Using {env_var_name} from environment.")
                api_key = env_key
                if st.checkbox("Override with a different key for this session", key="override_key_cb"):
                    typed = st.text_input("API Key", type="password", key="api_key_input")
                    if typed:
                        api_key = typed
            else:
                st.warning(f"No {env_var_name} found in environment — enter a key below.")
                api_key = st.text_input("API Key", type="password", key="api_key_input")

        if provider_id in ("gpt-image-2", "gpt-image-1"):
            quality_tier = st.radio(
                "Quality Tier",
                options=["low", "medium", "high"],
                index=1,
                horizontal=True,
                key="quality_sel",
            )

    return provider_label, provider_id, api_key, quality_tier


def render_quick_copy_panel():
    """Inline 'images-only' text generator: lets a user who only wants an
    image get a headline/hook/short caption from the content bot without
    leaving this page or waiting through the full research/write/refine
    pipeline. Never touches the generations table — throwaway copy only."""
    with st.expander("Need copy? Generate quick text", expanded=False):
        qc_topic = st.text_input("Topic", key="qc_topic")
        qc_plat_label = st.selectbox(
            "Platform", [v[0] for v in pcfg.PLATFORMS.values()], key="qc_platform"
        )
        qc_plat_name, qc_plat_domain, qc_pages, qc_default = next(
            v for v in pcfg.PLATFORMS.values() if v[0] == qc_plat_label
        )
        qc_query = st.text_input(
            "Page/subject to promote (optional)",
            placeholder='e.g. "AIOps"',
            key="qc_page_query",
        )
        if qc_query:
            matches = find_best_page(qc_query, platform=qc_plat_name, top_n=1)
            if matches:
                qc_name, qc_url, qc_desc = matches[0].page_name, matches[0].url, matches[0].description
            else:
                qc_name, qc_url, qc_desc = list(qc_pages.values())[0]
        else:
            qc_name, qc_url, qc_desc = qc_pages.get(qc_default, list(qc_pages.values())[0])
        qc_promo = f"{qc_name} ({qc_plat_name}): {qc_url}\n    {qc_desc}"

        if st.button("Generate quick text", key="qc_generate_btn", disabled=not qc_topic):
            with st.spinner("Writing quick copy..."):
                qc = generate_quick_copy(
                    topic=qc_topic, plat_name=qc_plat_name, plat_domain=qc_plat_domain,
                    alnafi_promo=qc_promo,
                )
            st.session_state["gen_hl"] = qc.headline
            st.session_state["gen_hook"] = qc.hook_line
            st.session_state["gen_body"] = qc.short_caption
            st.rerun()


def render_visuals_panel(sector):
    """Render visuals controls. Returns (background_preset, background_custom, colors, font)."""
    with st.expander("VISUALS", expanded=False):
        bg_category = st.selectbox(
            "Background Category",
            ["None", "Custom Visual"] + list(igcfg.BACKGROUND_PRESETS.keys()),
            key="bg_cat",
        )

        background_preset = ""
        background_custom = ""

        if bg_category == "Custom Visual":
            background_custom = st.text_area(
                "Describe your custom visual",
                placeholder=(
                    "Be as detailed as you like — describe the scene, objects, lighting, "
                    "colors, style, mood, camera angle, etc.\n\n"
                    "Example: A 3D glowing Azure logo floating in the center against a deep navy "
                    "gradient, with subtle circuit board lines in the background and soft blue light rays."
                ),
                height=140,
                key="bg_custom_area",
            )
        elif bg_category != "None":
            background_preset = st.selectbox(
                "Background Preset",
                igcfg.BACKGROUND_PRESETS[bg_category],
                key="bg_preset",
            )

        st.markdown("**Color System**")
        sc = igcfg.ALNAFI_SECTORS[sector]
        c1, c2, c3 = st.columns(3)
        with c1:
            color_primary = st.color_picker("Primary", sc["color_primary"], key="cp1")
        with c2:
            color_secondary = st.color_picker("Secondary", sc["color_secondary"], key="cp2")
        with c3:
            color_accent = st.color_picker("Accent", "#66BB6A", key="cp3")

        font = st.selectbox("Font Style", igcfg.FONT_OPTIONS, index=0, key="font_sel")

    colors = {"primary": color_primary, "secondary": color_secondary, "accent": color_accent}
    return background_preset, background_custom, colors, font


def render_layout_panel():
    """Render layout controls. Returns (canvas_size, content_split, blend_angle, left_margin)."""
    with st.expander("LAYOUTS", expanded=False):
        canvas_preset = st.selectbox(
            "Canvas Size Preset", list(igcfg.CANVAS_PRESETS.keys()), key="canvas_sel"
        )

        if canvas_preset == "Custom":
            cw, ch = st.columns(2)
            with cw:
                custom_w = st.number_input("Width", value=1080, min_value=256, max_value=3840, step=16, key="cw")
            with ch:
                custom_h = st.number_input("Height", value=1080, min_value=256, max_value=3840, step=16, key="ch")
            canvas_size = f"{custom_w}x{custom_h}"
        else:
            canvas_size = igcfg.CANVAS_PRESETS[canvas_preset]

        content_split = None
        if st.checkbox("Content Split", key="split_cb"):
            content_split = st.slider("Text Zone %", 30, 70, 55, key="split_sl")

        blend_angle = None
        if st.checkbox("Blend Angle", key="blend_cb"):
            blend_angle = st.slider("Tilt (degrees)", -45, 45, 15, key="blend_sl")

        left_margin = None
        if st.checkbox("Custom Left Margin", key="margin_cb"):
            left_margin = st.slider("Margin (px)", 20, 120, 40, key="margin_sl")

    return canvas_size, content_split, blend_angle, left_margin


def format_event_datetime(event_date, start_time, end_time=None):
    """Format the event date and time into a display string."""
    date_str = event_date.strftime("%B %d, %Y")
    start_str = start_time.strftime("%I:%M %p")
    if end_time:
        end_str = end_time.strftime("%I:%M %p")
        return f"{date_str}  |  {start_str} - {end_str}"
    return f"{date_str}  |  {start_str}"


def render_generation():
    main_col, controls_col = st.columns([65, 35], gap="medium")

    # ── RIGHT: Controls ──
    with controls_col:
        if st.button("Back to Home", key="gen_back"):
            st.session_state.page = "landing"
            st.rerun()

        st.markdown('<div class="panel-header">Generate New Post</div>', unsafe_allow_html=True)

        if st.session_state.get("prefill_from_content"):
            st.info("Pre-filled from a content brief generated on the Generate Content page. "
                    "Edit any field below before generating.")
            if st.button("Dismiss", key="dismiss_prefill"):
                st.session_state["prefill_from_content"] = False
                st.rerun()

        provider_label, provider_id, api_key, quality_tier = render_credentials_panel()

        render_quick_copy_panel()

        # ── CONTENT ──
        with st.expander("CONTENT", expanded=True):
            sector = st.selectbox("Al-Nafi Sector *", list(igcfg.ALNAFI_SECTORS.keys()), key="gen_sector")

            # Accreditation logo selection (only logos valid for this sector are shown)
            available_accreds = igcfg.SECTOR_ACCREDITATIONS.get(sector, [])
            selected_accreds = []
            if available_accreds:
                st.markdown("**Accreditation Logos**")
                for accred in available_accreds:
                    if st.checkbox(accred, value=True, key=f"accred_{accred}"):
                        selected_accreds.append(accred)

            # Live logo preview
            st.markdown(
                f'<div class="logo-preview">'
                f'{get_sector_logo_html(sector)}'
                f'{get_accreditation_logos_html(selected_accreds)}'
                f'</div>',
                unsafe_allow_html=True,
            )

            post_type = st.selectbox("Post Type *", igcfg.POST_TYPES, key="gen_pt")
            badge = st.selectbox("Session Badge", igcfg.SESSION_BADGES, key="gen_badge")
            platforms = st.multiselect(
                "Target Platform(s) *", igcfg.PLATFORM_TARGETS,
                default=["Instagram", "Facebook"], key="gen_plat",
            )
            st.markdown("---")
            headline = st.text_input("Headline *", placeholder="e.g., Master Cloud Computing in 6 Months", key="gen_hl")
            hook = st.text_input("Hook Line", placeholder="e.g., Limited Time Offer!", key="gen_hook")
            title = st.text_input("Title", key="gen_title")
            subtitle = st.text_input("Subtitle", key="gen_sub")
            body = st.text_area("Body Text", height=70, key="gen_body")
            bullet_points = st.text_area("Bullet Points (one per line)", height=70, key="gen_bp")

        with st.expander("SPEAKER & EVENT", expanded=False):
            speaker_names = st.text_input("Speaker Name(s)", key="gen_spk")
            speaker_designation = st.text_input(
                "Speaker Title / Role",
                placeholder="e.g., AI & Digital Transformation Expert",
                key="gen_spk_desig",
            )
            speaker_photos = st.file_uploader(
                "Speaker Photo(s)", type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True, key="gen_spk_ph",
            )
            speaker_photo_described = st.text_input("Or describe speaker visual", key="gen_spk_desc")
            st.markdown("---")

            # Date picker with calendar
            event_date = st.date_input(
                "Event Date",
                value=None,
                min_value=date.today(),
                key="gen_event_date",
            )

            event_datetime = ""
            if event_date:
                is_physical = "Physical" in post_type

                if is_physical:
                    st.caption("Physical event -- set start and end time")
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        start_time = st.time_input("Start Time", value=dt_time(10, 0), key="gen_start_time")
                    with tc2:
                        end_time = st.time_input("End Time", value=dt_time(13, 0), key="gen_end_time")
                    event_datetime = format_event_datetime(event_date, start_time, end_time)
                else:
                    st.caption("Online event -- set start time (sessions may run overtime)")
                    start_time = st.time_input("Start Time", value=dt_time(19, 0), key="gen_start_time_online")
                    event_datetime = format_event_datetime(event_date, start_time)

                st.markdown(f"**Formatted:** {event_datetime}")

            venue = st.text_input("Venue / Address", key="gen_venue")
            include_url = st.checkbox("Include Website URL in footer", value=True, key="gen_include_url")
            if include_url:
                _sector_url = igcfg.SECTOR_WEBSITES.get(sector, "")
                _website_options = [_sector_url, "Custom…"] if _sector_url else ["Custom…"]
                _web_choice = st.selectbox("Website URL", _website_options, key="gen_web_sel")
                if _web_choice == "Custom…":
                    website = st.text_input("Enter custom URL", key="gen_web_custom")
                else:
                    website = _web_choice
            else:
                website = ""
            contact_info = st.text_input("Contact Info", value="+92 304-1110400", key="gen_contact")
            cta_text = st.text_input("CTA Button Text", placeholder="e.g., Enroll Now", key="gen_cta")

            streaming_platform = ""
            if "Online" in post_type:
                st.markdown("---")
                streaming_platform = st.text_input(
                    "Streaming Platform / Join Method",
                    placeholder="e.g., Zoom  |  zoom.us/j/123456  |  YouTube Live",
                    key="gen_streaming",
                )

        background_preset, background_custom, colors, font = render_visuals_panel(sector)
        canvas_size, content_split, blend_angle, left_margin = render_layout_panel()

    # ── Build prompts ──
    form_data = {
        "sector": sector, "post_type": post_type, "badge": badge,
        "platforms": platforms,
        "headline": headline, "hook": hook, "title": title, "subtitle": subtitle,
        "body": body, "bullet_points": bullet_points,
        "speaker_names": speaker_names, "speaker_designation": speaker_designation,
        "speaker_photo_described": speaker_photo_described, "streaming_platform": streaming_platform,
        "venue": venue, "event_datetime": event_datetime,
        "website": website, "contact_info": contact_info, "cta_text": cta_text,
        "background_preset": background_preset, "background_custom": background_custom,
        "colors": colors, "font": font, "canvas_size": canvas_size,
        "content_split": content_split, "blend_angle": blend_angle, "left_margin": left_margin,
        "selected_accreds": selected_accreds,
    }
    sector_info = igcfg.ALNAFI_SECTORS[sector]
    system_prompt = build_system_prompt(sector_info, form_data["colors"])
    image_prompt = build_image_prompt(form_data)

    # ── LEFT: Workspace ──
    with main_col:
        st.markdown(
            '<h2 style="margin:0 0 4px 0; color:#2D6FBC;">Generate New Post</h2>',
            unsafe_allow_html=True,
        )

        # Status bar
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            pill = "pill-ready" if headline else "pill-missing"
            label = "Headline" if headline else "No Headline"
            st.markdown(f'<span class="status-pill {pill}">{label}</span>', unsafe_allow_html=True)
        with s2:
            ok = api_key or provider_id == "prompt-only"
            pill = "pill-ready" if ok else "pill-missing"
            label = "API Ready" if ok else "No API Key"
            st.markdown(f'<span class="status-pill {pill}">{label}</span>', unsafe_allow_html=True)
        with s3:
            st.markdown(f'<span class="status-pill pill-ready">{canvas_size}</span>', unsafe_allow_html=True)
        with s4:
            st.markdown(
                f'<span class="status-pill pill-ready">{sector.split()[-1]}</span>',
                unsafe_allow_html=True,
            )

        # Generate button
        st.markdown("")
        can_gen = bool(headline) and (bool(api_key) or provider_id == "prompt-only")
        gen_btn = st.button(
            "Generate Image", type="primary",
            use_container_width=True, disabled=not can_gen, key="gen_btn",
        )

        if gen_btn and can_gen:
            _has_contact = bool(form_data.get("contact_info") or form_data.get("website"))
            run_image_generation(
                api_key, image_prompt, system_prompt, provider_id,
                provider_label, quality_tier, canvas_size, headline, post_type, sector, selected_accreds,
                has_contact=_has_contact,
                db_meta={
                    "timestamp": datetime.now().isoformat(),
                    "sector": sector,
                    "post_type": post_type,
                    "canvas_size": canvas_size,
                    "provider": provider_label,
                    "quality": quality_tier,
                    "headline": headline,
                    "platforms": platforms,
                    "generation_id": st.session_state.get("prefill_generation_id"),
                },
            )

        # Tabs: prompt preview and JSON export (no system prompt shown)
        st.markdown("---")
        tab_prompt, tab_json = st.tabs(["Prompt Preview", "JSON Export"])

        with tab_prompt:
            st.markdown("##### Image Generation Prompt")
            st.markdown(f'<div class="prompt-box">{image_prompt}</div>', unsafe_allow_html=True)

        with tab_json:
            export_data = {
                "meta": {
                    "sector": sector, "post_type": post_type,
                    "platforms": platforms, "canvas_size": canvas_size,
                    "provider": provider_label,
                    "quality": quality_tier if provider_id in ("gpt-image-2", "gpt-image-1") else "N/A",
                    "generated_at": datetime.now().isoformat(),
                },
                "image_prompt": image_prompt,
                "form_data": {k: v for k, v in form_data.items() if k != "colors"},
                "colors": colors,
            }
            json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
            st.code(json_str, language="json")
            st.download_button(
                "Download JSON", data=json_str,
                file_name=f"alnafi_gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json", use_container_width=True,
            )
