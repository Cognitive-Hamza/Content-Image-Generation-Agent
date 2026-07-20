from .config import ALNAFI_SECTORS


def build_system_prompt(sector_info, colors):
    """Build the base system prompt for the image generation model."""
    return f"""You are a professional social media graphic designer for {sector_info['description']}.
Brand: Al-Nafi Group -- Sector: the one described below.
Tagline: "{sector_info['tagline']}"

BRAND GUIDELINES:
- Primary Color: {colors['primary']}
- Secondary Color: {colors['secondary']}
- Accent Color: {colors['accent']}
- Style: Modern, professional, education-focused, globally appealing
- Text must be crisp, readable, and correctly spelled
- Designs should feel premium, accredited, and trustworthy
- Photography style: aspirational, diverse, professional
- Avoid clutter; use clean layouts with clear visual hierarchy

LOGO & TOP BAR RULES:
1. The full-width top 12% of the image is a QUIET ZONE — keep it as a plain, low-contrast background only (color/gradient, no content). Brand logo (top-left) and accreditation badges (top-right) are pasted here after generation and must be clearly visible.
2. Do NOT place any text, heading, icon cluster, or detailed visual in the top 12%. All main content starts below this zone.
3. Do NOT draw, write, or render: any logo graphic, brand icon, "Al-Nafi", "Al Nafi", "alnafi", "International College", "Islamic College", "Academy", "Cloud", or any brand name variant anywhere on the image — drawing it creates a duplicate over the real logo.
4. Do NOT add a dark strip, colored band, white box, or separator line at the top — background flows naturally from edge to edge.
5. Do NOT write any website URL or domain name unless explicitly told to in the image prompt below.

DESIGN RULES:
1. Headline text must be the LARGEST element and perfectly legible
2. Use brand colors as dominant palette unless user overrides
3. CTA buttons should use the accent color for contrast
4. Maintain consistent padding and margins
5. Text over images must have contrast overlay or text shadow
6. Do NOT insert white boxes, white cards, or light-colored panels as background containers — use the actual background color/image directly
6. Session badges (LIVE, FREE, etc.) should be pill-shaped with bold contrast
"""


def build_image_prompt(data):
    """Compose the full image generation prompt from all user inputs."""
    sector = ALNAFI_SECTORS[data["sector"]]
    colors = data["colors"]

    parts = []

    parts.append(f"Create a {data['canvas_size']} social media graphic.")
    parts.append(f"Post type: {data['post_type']}.")
    parts.append(f"Target platform(s): {', '.join(data['platforms'])}.")
    parts.append(f"Brand: {data['sector']} -- {sector['tagline']}.")
    parts.append(
        f"Color scheme: primary {colors['primary']}, secondary {colors['secondary']}, accent {colors['accent']}."
    )

    if data["post_type"] == "Blog Thumbnail":
        parts.append(
            "BLOG THUMBNAIL LAYOUT: Use a wide horizontal format. "
            "Left half: solid brand-colored background with the blog title in large, bold, high-contrast text "
            "(use accent color for key words). "
            "Right half: a relevant high-quality visual, icon, or 3D illustration related to the topic. "
            "Top area (left or center): accreditation/brand strip with logos. "
            "Bottom: optional thin accent-color bar. "
            "Style: clean, modern, professional — similar to Microsoft/tech blog thumbnails."
        )

    # Top bar (sector logo + optional accreditation logos) is composited via PIL AFTER generation.
    # Tell the AI to leave the entire top strip clear — PIL will fill it.
    accreds = data.get("selected_accreds", [])
    has_contact = bool(data.get("contact_info") or data.get("website"))

    _sector_name = data["sector"]
    parts.append(
        f"LOGO PLACEMENT — CRITICAL: Brand logo and accreditation badges are composited onto the image AFTER generation. "
        f"You MUST keep the entire TOP strip of the image (full width, top 12% of height) as a LOW-CONTRAST, "
        f"VISUALLY QUIET zone — use the background color/gradient only, no text blocks, no busy visuals, no overlapping elements. "
        f"This ensures the logos pasted on top remain clearly readable. "
        f"Do NOT place any text, heading, sub-heading, icon cluster, or detailed visual element in this top strip. "
        f"The main design content (headlines, body, visuals) must start BELOW the top 12%. "
        f"Do NOT draw, write, or render: '{_sector_name}', 'Al-Nafi', 'Al Nafi', 'alnafi', "
        f"any brand name variant, any logo graphic, or any brand placeholder anywhere on the image. "
        f"Do NOT add a dark strip, colored bar, white box, or separator line at the top — the background flows naturally edge to edge."
    )

    if accreds:
        # Accreditation logos are always composited into the top bar via PIL — never at the bottom.
        parts.append(
            "ACCREDITATION: Do NOT draw any accreditation logos, badges, or strips anywhere on the image — "
            "not at the top, not at the bottom, not anywhere. "
            "They are composited onto the top-right area programmatically after generation."
        )
    if has_contact:
        parts.append("Contact info and website go in the BOTTOM footer area of the image.")

    if data.get("badge") and data["badge"] != "None":
        parts.append(
            f"Include a '{data['badge']}' badge/pill just below the top bar on the right side, "
            f"with high-contrast styling."
        )

    if data.get("headline"):
        parts.append(f'HEADLINE (largest, boldest text): "{data["headline"]}"')
    if data.get("hook"):
        parts.append(f'HOOK LINE (above headline, smaller): "{data["hook"]}"')
    if data.get("title"):
        parts.append(f'TITLE: "{data["title"]}"')
    if data.get("subtitle"):
        parts.append(f'SUBTITLE (below title): "{data["subtitle"]}"')
    if data.get("body"):
        parts.append(f'BODY TEXT (readable paragraph): "{data["body"]}"')
    if data.get("bullet_points"):
        bullets = [b.strip() for b in data["bullet_points"].split("\n") if b.strip()]
        if bullets:
            parts.append(f"BULLET POINTS in a styled box: {' | '.join(bullets)}")

    if data.get("speaker_names"):
        designation = f" | {data['speaker_designation']}" if data.get("speaker_designation") else ""
        parts.append(
            f"SPEAKER(S): {data['speaker_names']}{designation} -- show in a professional name tag element."
        )
        if data.get("speaker_photo_described"):
            parts.append(f"Speaker visual: {data['speaker_photo_described']}")
        else:
            parts.append(
                "CRITICAL: Do NOT add any photo, face, portrait, or image of a person. "
                "Show the speaker's name (and role if given) as styled text only. No human figures whatsoever."
            )
    else:
        parts.append(
            "IMPORTANT: Do NOT add any person, face, or human figure to the image."
        )

    if data.get("streaming_platform"):
        parts.append(
            f'JOIN / STREAMING: "{data["streaming_platform"]}" -- display clearly how attendees can join the event.'
        )

    if data.get("venue"):
        parts.append(f'VENUE / LOCATION: "{data["venue"]}"')
    if data.get("event_datetime"):
        parts.append(f'DATE & TIME: "{data["event_datetime"]}"')
    if data.get("website") or data.get("contact_info"):
        footer_items = []
        if data.get("contact_info"):
            footer_items.append(data["contact_info"])
        if data.get("website"):
            footer_items.append(data["website"])
        footer_line = "   |   ".join(footer_items)
        parts.append(
            f'FOOTER STRIP — LOCKED STYLE (do not deviate from this in any post): '
            f'At the very bottom of the image, draw a full-width solid dark strip (dark navy or brand primary color). '
            f'Inside this strip, display the following in ONE line, horizontally centered: "{footer_line}". '
            f'FONT LOCK: Montserrat or Inter, weight 800 (Extra Bold), size 54–60pt, pure white text. '
            f'The text must span most of the strip width and be the most dominant element in the footer. '
            f'Do NOT put the URL anywhere else in the image — only in this footer strip. '
            f'Do NOT use small text, buttons, pills, green boxes, or decorative arrows around the URL. '
            f'This footer strip style must be identical in every single post regardless of the domain or phone number.'
        )

    if data.get("cta_text"):
        parts.append(
            f'CTA BUTTON: "{data["cta_text"]}" -- styled as a pill/rounded button in accent color {colors["accent"]}.'
        )

    if data.get("background_preset") and data["background_preset"] != "None / Custom":
        parts.append(f"BACKGROUND VISUAL: {data['background_preset']}.")
    if data.get("background_custom"):
        parts.append(f"BACKGROUND DESCRIPTION: {data['background_custom']}.")

    if data.get("font"):
        parts.append(f"PRIMARY FONT STYLE: {data['font']}.")

    if data.get("content_split"):
        parts.append(f"LAYOUT SPLIT: {data['content_split']}% text zone on the left, rest is visual/photo zone.")
    if data.get("blend_angle"):
        parts.append(f"Use a diagonal blend/mask at approximately {data['blend_angle']} degrees between text and visual zones.")
    if data.get("left_margin"):
        parts.append(f"Left margin spacing: {data['left_margin']}px equivalent.")

    # Language instruction
    if data.get("target_language") and data["target_language"] != "English":
        parts.append(
            f"CRITICAL: ALL text on the image must be written in **{data['target_language']}**. "
            f"Use proper {data['target_language']} script, right-to-left if applicable. "
            f"Ensure every word, label, and button text is in {data['target_language']}."
        )

    parts.append(
        "QUALITY: Professional marketing quality. All text must be perfectly spelled and crisp. "
        "Clean layout with proper visual hierarchy. No AI artifacts or distorted text."
    )

    return "\n".join(parts)


def make_translation_prompt(target_language, sector_info, colors):
    return (
        f"Look at this social media post image carefully. "
        f"Recreate the EXACT same design -- same layout, colors, typography style, "
        f"visual elements, photos, icons, logo placement, and overall composition. "
        f"The ONLY change: translate ALL visible text on the image into {target_language}. "
        f"Use proper {target_language} script and natural phrasing. "
        f"Keep brand names as-is (Al-Nafi, Pearson, EduQual, ISACA, EADL). "
        f"Keep URLs and email addresses unchanged. "
        f"FONT CONSISTENCY: Use the exact same font family, weight, size, and spacing as in the original image. "
        f"Every translated text element must match the font style of its original counterpart. "
        f"Brand: {sector_info['description']} -- {sector_info['tagline']}. "
        f"Brand colors: primary {colors['primary']}, secondary {colors['secondary']}, accent {colors['accent']}. "
        f"Professional marketing quality. Perfectly spelled {target_language} text."
    )
