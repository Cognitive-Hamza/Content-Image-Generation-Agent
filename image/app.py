"""
Al-Nafi Image Generation Agent v3.0

Social media post generator & translator for Al-Nafi International College
and its sub-brands. Streamlit app with AI-powered image generation.

Changes from v2:
- Database system removed
- System prompt hidden from UI
- Quality tier as buttons (radio)
- All emojis removed
- Sector and accreditation logos loaded from logos/ folder on disk
- Accreditations mapped per sector
- Date/time picker with calendar + conditional time range
- Default accent color: light green
- Background presets with one-liner descriptions
- Translation options panel removed
"""

import streamlit as st
import json
import base64
import io
import os
import time
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, time as dt_time

try:
    from PIL import Image as PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ──────────────────────────────────────────────────────────────
# LOGO FILE PATHS
# ──────────────────────────────────────────────────────────────
# Logos are loaded from the logos/ folder sitting next to app.py.
# Drop your PNG/JPG/WEBP files into the correct subfolder and the
# app picks them up automatically. No code changes needed.
#
# Expected structure:
#   logos/
#     sectors/
#       al-nafi-international-college.png
#       al-nafi-islamic-college.png
#       al-nafi-academy.png
#       al-nafi-islamic-academy.png
#       al-nafi-institute.png
#     accreditations/
#       pearson-btec.png
#       eduqual-uk.png
#       isaca.png
#       eadl.png
#       cambridge-assessment.png

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_SECTOR_LOGO_DIR = os.path.join(_APP_DIR, "Al-Nafi Logos")
_ACCRED_LOGO_DIR = os.path.join(_APP_DIR, "Accredations Logos")
DB_PATH = os.path.join(_APP_DIR, "alnafi_posts.db")

# Default (color) logos
SECTOR_LOGOS = {
    "Al Nafi International College": os.path.join(_SECTOR_LOGO_DIR, "alnafi-int-college.png"),
    "Al Nafi Islamic College":       os.path.join(_SECTOR_LOGO_DIR, "alnafi-islamic-college.png"),
    "Al Nafi Academy":               os.path.join(_SECTOR_LOGO_DIR, "alnafi-academy.png"),
    "Alnafi Cloud":                  os.path.join(_SECTOR_LOGO_DIR, "alnafi-cloud-logo.png"),
    "Annaafi PAY":                   os.path.join(_SECTOR_LOGO_DIR, "alnafi-epay-logo.png"),
}

# White versions — for dark strip backgrounds
SECTOR_LOGOS_WHITE = {
    "Al Nafi International College": os.path.join(_SECTOR_LOGO_DIR, "alnafi-int-college-white.png"),
    "Alnafi Cloud":                  os.path.join(_SECTOR_LOGO_DIR, "alnafi-cloud-white-logo.png"),
}

# Dark/color logos used on light backgrounds (no black-specific files for most brands)
SECTOR_LOGOS_DARK = {
    "Al Nafi International College": os.path.join(_SECTOR_LOGO_DIR, "alnafi-int-college.png"),
    "Al Nafi Islamic College":       os.path.join(_SECTOR_LOGO_DIR, "alnafi-islamic-college.png"),
    "Al Nafi Academy":               os.path.join(_SECTOR_LOGO_DIR, "alnafi-academy.png"),
    "Alnafi Cloud":                  os.path.join(_SECTOR_LOGO_DIR, "alnafi-cloud-logo.png"),
    "Annaafi PAY":                   os.path.join(_SECTOR_LOGO_DIR, "alnafi-epay-logo.png"),
}

# Default (color) — same as DARK for now; kept separate so callers stay readable
ACCREDITATION_LOGOS = {
    "Pearson BTEC": os.path.join(_ACCRED_LOGO_DIR, "pearson-black-logo.png"),
    "EduQual UK":   os.path.join(_ACCRED_LOGO_DIR, "eduqual-logo.png"),
    "ISACA":        os.path.join(_ACCRED_LOGO_DIR, "isaca-logo.png"),
    "EADL":         os.path.join(_ACCRED_LOGO_DIR, "eadl-logo.jpg"),
}

# White variants — for dark strip backgrounds
ACCREDITATION_LOGOS_WHITE = {
    "Pearson BTEC": os.path.join(_ACCRED_LOGO_DIR, "pearson-white-logo.png"),
    "EduQual UK":   os.path.join(_ACCRED_LOGO_DIR, "eduqual-logo-white.png"),
    "ISACA":        os.path.join(_ACCRED_LOGO_DIR, "isaca-logo-white.png"),
    "EADL":         os.path.join(_ACCRED_LOGO_DIR, "eadl-logo-white.png"),
}

# Which accreditation logos are available per sector (controls the checkboxes shown to user)
SECTOR_ACCREDITATIONS = {
    "Al Nafi International College": ["EduQual UK", "ISACA", "EADL"],
    "Al Nafi Islamic College":       ["EduQual UK"],
    "Al Nafi Academy":               ["Pearson BTEC"],
    "Alnafi Cloud":                  [],
    "Annaafi PAY":                   [],
}
# ──────────────────────────────────────────────────────────────
# CONSTANTS & CONFIG
# ──────────────────────────────────────────────────────────────

SECTOR_WEBSITES = {
    "Al Nafi International College": "https://www.alnafi.com/",
    "Al Nafi Islamic College":       "https://islamic.alnafi.com/",
    "Al Nafi Academy":               "https://alnafi.academy/",
    "Alnafi Cloud":                  "https://alnafi.cloud/",
    "Annaafi PAY":                   "https://epay.com.pk/",
}

ALNAFI_SECTORS = {
    "Al Nafi International College": {
        "domain": "alnafi.com",
        "tagline": "Globally Recognized Pearson BTEC & EduQual Diplomas",
        "color_primary": "#2D6FBC",
        "color_secondary": "#1A4A8A",
        "color_accent": "#66BB6A",
        "description": "IT, Cloud, DevOps, AI, Cybersecurity Diplomas & Courses",
    },
    "Al Nafi Islamic College": {
        "domain": "islamic.alnafi.com",
        "tagline": "Next Generation Islamic Scholars",
        "color_primary": "#1B5E20",
        "color_secondary": "#2E7D32",
        "color_accent": "#66BB6A",
        "description": "Islamic Studies with Modern Tech Education",
    },
    "Al Nafi Academy": {
        "domain": "alnafi.academy",
        "tagline": "O-Levels & IGCSE Excellence",
        "color_primary": "#4A148C",
        "color_secondary": "#6A1B9A",
        "color_accent": "#66BB6A",
        "description": "Foundation, O-Levels, IGCSE Preparation",
    },
    "Alnafi Cloud": {
        "domain": "cloud.alnafi.com",
        "tagline": "Cloud for All",
        "color_primary": "#1976D2",
        "color_secondary": "#0D47A1",
        "color_accent": "#29B6F6",
        "description": "Cloud Computing & Infrastructure Solutions",
    },
    "Annaafi PAY": {
        "domain": "pay.alnafi.com",
        "tagline": "Smart & Secure Digital Payments",
        "color_primary": "#5C6BC0",
        "color_secondary": "#3949AB",
        "color_accent": "#7C4DFF",
        "description": "Digital Payment Platform by Al-Nafi Group",
    },
}

POST_TYPES = [
    "General Post",
    "Course Promotion",
    "Online Event Invitation",
    "Physical Event Invitation",
    "Online Webinar Invitation",
    "Physical Webinar Invitation",
    "Video Thumbnail",
    "Blog Thumbnail",
    "Announcement",
    "Testimonial / Success Story",
    "Admission Open",
    "Workshop Promotion",
    "Certificate Showcase",
]

SESSION_BADGES = [
    "None",
    "LIVE",
    "FREE",
    "RECORDED",
    "PREMIUM",
    "UPCOMING",
    "NEW",
    "LIMITED SEATS",
    "EARLY BIRD",
    "CERTIFIED",
    "HANDS-ON",
    "WORKSHOP",
    "MASTERCLASS",
    "BOOTCAMP",
    "OPEN HOUSE",
]

PLATFORM_TARGETS = [
    "Instagram",
    "Facebook",
    "Twitter / X",
    "WhatsApp",
    "LinkedIn",
    "YouTube",
]

CANVAS_PRESETS = {
    "Instagram / Facebook Square": "1080x1080",
    "Instagram Portrait": "1080x1350",
    "Stories (IG / FB / WA)": "1080x1920",
    "LinkedIn Post": "1200x627",
    "YouTube Thumbnail": "1280x720",
    "Twitter / X Post": "1200x675",
    "Facebook Post": "1200x630",
    "Event Banner / OG Image": "1200x630",
    "Custom": "custom",
}

OPENAI_SIZE_MAP = {
    "1080x1080": "1024x1024",
    "1080x1350": "1024x1536",
    "1080x1920": "1024x1536",
    "1200x627": "1536x1024",
    "1280x720": "1536x1024",
    "1200x675": "1536x1024",
    "1200x630": "1536x1024",
}

# Background presets: key = one-liner description (shown to user), used as prompt
BACKGROUND_PRESETS = {
    "Tech Visuals": [
        "Dark data center with rows of glowing blue server racks",
        "Abstract neon circuit board with flowing data streams",
        "Floating cloud computing icons over a gradient sky",
        "Neural network nodes and connections in deep blue tones",
        "Green digital shield with matrix-style falling code",
        "DevOps pipeline gears and container icons on dark canvas",
        "Minimalist desk setup with code glowing on a laptop screen",
        "Holographic binary digits swirling around a dark sphere",
        "Interconnected blockchain nodes with gold pulse lines",
        "Quantum particle trails on a deep violet background",
    ],
    "Educational Visuals": [
        "Warm-lit university hallway with arched ceilings",
        "Graduation cap on a stack of textbooks on a wooden desk",
        "Soft-focused library shelves stretching into the distance",
        "Clean whiteboard covered in knowledge diagrams and notes",
        "Confetti and caps in the air at a graduation ceremony",
        "Framed diploma beside a neat row of academic books",
        "Speaker at a polished podium addressing a seated audience",
        "Study desk with open notebook, laptop, and a cup of coffee",
        "Grand academic building exterior with columns and steps",
        "Globe wearing a graduation cap with light trails around it",
    ],
    "Blog Thumbnail -- Tech & Cloud": [
        "3D Microsoft Azure logo floating on a gradient blue background",
        "Glowing AWS cloud icon with rays on a dark navy background",
        "3D Google Cloud logo with colourful gradient on white",
        "3D Docker container stack with neon outlines on dark background",
        "Kubernetes wheel icon with glowing blue nodes on deep navy",
        "DevOps infinity loop with gears and code on dark canvas",
        "Python logo with floating code snippets on dark gradient",
        "Cybersecurity lock and shield glowing on deep blue circuit background",
        "Ethical hacking terminal screen with green text on black",
        "AI brain made of neural connections on purple-dark gradient",
        "Machine learning graph and data points floating in blue void",
        "Linux penguin mascot with terminal window on dark background",
        "JavaScript code glowing on a dark modern IDE screenshot",
        "React component tree with blue nodes on dark background",
        "Microservices architecture diagram with colour-coded blocks",
        "API gateway diagram with arrows and endpoints on dark blue",
        "Database server stack with glowing query lines on dark canvas",
        "Blockchain ledger blocks chained in 3D on dark gradient",
        "Cloud migration arrows lifting servers to the sky",
        "Laptop screen showing a live dashboard with charts",
        "Network topology map with blinking nodes on dark background",
        "Penetration testing toolkit on a dark hacker-style terminal",
        "Red and blue team cybersecurity shield clash on dark canvas",
        "Zero-trust architecture diagram on clean white background",
        "5G network tower with glowing signal waves at night",
    ],
    "Blog Thumbnail -- Business & Career": [
        "Professional shaking hands in a modern glass office",
        "Upward growth chart with arrow breaking through the top",
        "Roadmap of career milestones on a clean minimalist background",
        "LinkedIn profile on a laptop with a coffee cup beside it",
        "Resume document with a pen on a clean white desk",
        "Job interview scene in a bright modern office",
        "Salary negotiation concept with rising coins on a desk",
        "Remote work setup with laptop, headset, and home office",
        "Leadership silhouette standing on a podium with spotlight",
        "Team brainstorming around a whiteboard in a startup office",
        "Clock and calendar with productivity icons on white background",
        "Freelancer working at a coffee shop with laptop",
        "Entrepreneur writing a business plan in a modern workspace",
        "SWOT analysis chart on a clean presentation slide style",
        "People networking at a professional conference event",
    ],
    "Blog Thumbnail -- Education & Courses": [
        "Open textbook with glowing lightbulb above it on dark blue",
        "Student holding a diploma with bright sunlight behind",
        "Online course interface on a tablet with headphones beside",
        "Chalkboard with formulas and a graduation cap on corner",
        "Stack of colourful academic books with an apple on top",
        "E-learning concept with laptop and knowledge icons floating",
        "Study roadmap with numbered steps on a clean infographic background",
        "Certificate document with gold seal on a wooden desk",
        "Brain with gears and books around it on gradient background",
        "Classroom scene with interactive digital whiteboard",
        "Student coding on a laptop in a modern university library",
        "Scholarship coins and a graduation cap on blue background",
        "Teacher pointing at a large world map in a bright room",
        "Knowledge transfer concept with arrows between two heads",
        "Puzzle pieces forming a complete skill set on white background",
    ],
    "Regional / Audience Visuals": [
        "Diverse group of professionals in a modern office setting",
        "Toronto skyline glowing at golden hour",
        "World map with glowing connected nodes and light trails",
        "Dubai skyline silhouette with Burj Khalifa at sunset",
        "Attentive audience in a well-lit conference hall",
        "Confident speaker on stage with dramatic spotlight",
        "Proud graduate holding a diploma against a bright backdrop",
        "Graduate in cap and gown walking toward the horizon",
        "Focused student working on a laptop in a modern space",
        "Professor explaining concepts on a large digital display",
        "Row of colorful world flags representing global reach",
        "Professional climbing illuminated steps symbolizing growth",
        "Parent and child studying together at a home desk",
        "Teacher and students in an interactive classroom discussion",
        "Student standing confidently with a book in hand",
        "Sleek modern academy building exterior at dusk",
        "Welcoming open-house registration desk with a banner",
        "Career counsellor meeting with a student one-on-one",
        "Professional in a modern office typing on a laptop",
        "Graduate looking toward a bright, aspirational horizon",
        "Student in an online learning session on a glowing screen",
        "Diverse study group collaborating around a shared table",
    ],
}

FONT_OPTIONS = [
    "Montserrat (Modern, Clean)",
    "Poppins (Friendly, Rounded)",
    "Playfair Display (Elegant, Serif)",
    "Roboto (Neutral, Professional)",
    "Inter (Clean, Technical)",
    "Raleway (Thin, Sophisticated)",
    "Oswald (Bold, Condensed)",
    "Lato (Warm, Corporate)",
    "Nunito (Soft, Approachable)",
    "Cairo (Arabic-Latin Bilingual)",
]

PROVIDERS = {
    "gpt-image-2 (OpenAI) -- Default": "gpt-image-2",
    "gpt-image-1 (OpenAI)": "gpt-image-1",
    "Gemini Imagen 3 (Google)": "imagen-3",
    "Nano Banana": "nano-banana",
    "Prompt Only (JSON Output)": "prompt-only",
}

TRANSLATION_LANGUAGES = [
    # Most-used first
    "Urdu", "Arabic", "Hindi", "English", "French", "Spanish", "German",
    "Turkish", "Malay / Bahasa Malaysia", "Bengali", "Pashto", "Persian / Farsi",
    "Chinese (Simplified)", "Chinese (Traditional)", "Portuguese", "Indonesian",
    "Somali", "Swahili", "Russian", "Japanese", "Korean",
    # Full OpenAI-supported set (alphabetical after the above)
    "Afrikaans", "Albanian", "Amharic", "Armenian", "Azerbaijani",
    "Basque", "Belarusian", "Bosnian", "Bulgarian", "Catalan",
    "Cebuano", "Corsican", "Croatian", "Czech", "Danish", "Dutch",
    "Esperanto", "Estonian", "Filipino / Tagalog", "Finnish",
    "Frisian", "Galician", "Georgian", "Greek", "Gujarati",
    "Haitian Creole", "Hausa", "Hawaiian", "Hebrew", "Hmong",
    "Hungarian", "Icelandic", "Igbo", "Irish", "Italian",
    "Javanese", "Kannada", "Kazakh", "Khmer", "Kurdish (Kurmanji)",
    "Kyrgyz", "Lao", "Latin", "Latvian", "Lithuanian",
    "Luxembourgish", "Macedonian", "Malagasy", "Malayalam", "Maltese",
    "Maori", "Marathi", "Mongolian", "Myanmar (Burmese)", "Nepali",
    "Norwegian", "Nyanja (Chichewa)", "Odia (Oriya)", "Polish",
    "Punjabi", "Romanian", "Samoan", "Scottish Gaelic", "Serbian",
    "Sesotho", "Shona", "Sindhi", "Sinhala", "Slovak",
    "Slovenian", "Sundanese", "Swedish", "Tajik", "Tamil",
    "Tatar", "Telugu", "Thai", "Turkmen", "Ukrainian",
    "Uyghur", "Uzbek", "Vietnamese", "Welsh", "Xhosa",
    "Yiddish", "Yoruba", "Zulu",
]


# ──────────────────────────────────────────────────────────────
# LOCAL DATABASE
# ──────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generated_posts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT    NOT NULL,
            sector        TEXT,
            post_type     TEXT,
            canvas_size   TEXT,
            provider      TEXT,
            quality       TEXT,
            headline      TEXT,
            platforms     TEXT,
            image_prompt  TEXT,
            system_prompt TEXT,
            image_data    BLOB    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_post_to_db(image_bytes, image_prompt, system_prompt, meta):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO generated_posts
            (timestamp, sector, post_type, canvas_size, provider, quality,
             headline, platforms, image_prompt, system_prompt, image_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        meta.get("timestamp", datetime.now().isoformat()),
        meta.get("sector", ""),
        meta.get("post_type", ""),
        meta.get("canvas_size", ""),
        meta.get("provider", ""),
        meta.get("quality", ""),
        meta.get("headline", ""),
        json.dumps(meta.get("platforms", [])),
        image_prompt,
        system_prompt,
        image_bytes,
    ))
    conn.commit()
    conn.close()


def load_all_posts(limit=200):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM generated_posts ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_post_from_db(post_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM generated_posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()


init_db()


# ──────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────

def _logo_to_img_tag(path, alt, style):
    """Load a logo file from disk and return an HTML img tag, or a placeholder div if missing."""
    if not path or not os.path.exists(path):
        return (
            f'<div style="padding:4px 8px;background:#1e1e2e;border:1px dashed #444;'
            f'border-radius:4px;color:#555;font-size:10px;font-family:monospace;">'
            f'{alt} — logo file not found</div>'
        )
    ext = os.path.splitext(path)[1].lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<img src="data:{mime};base64,{b64}" alt="{alt}" style="{style}" />'


def get_sector_logo_html(sector, width=160):
    """Return an HTML img tag for the given sector logo, loaded from disk."""
    path = SECTOR_LOGOS.get(sector)
    return _logo_to_img_tag(path, sector, f"width:{width}px;border-radius:6px;")


def get_accreditation_logos_html(accreds):
    """Return HTML for the given list of accreditation names, loaded from disk."""
    if not accreds:
        return ""
    parts = []
    for name in accreds:
        path = ACCREDITATION_LOGOS.get(name)
        parts.append(
            _logo_to_img_tag(path, name, "height:36px;border-radius:4px;margin:0 6px 6px 0;")
        )
    return '<div style="display:flex;flex-wrap:wrap;align-items:center;margin-top:8px;">' + "".join(parts) + "</div>"


def _bg_brightness(img_rgba, x, y, w, h):
    """Average luminance (0-255) of a rectangular region."""
    region = img_rgba.crop((x, y, x + w, y + h)).convert("L")
    px = list(region.getdata())
    return sum(px) / len(px) if px else 128


def _load_accred_logos(selected_accreds, logo_target_h, use_white=False):
    """Load and resize accreditation logo images. Returns list of RGBA PIL images."""
    logos = []
    for name in selected_accreds:
        if use_white:
            path = ACCREDITATION_LOGOS_WHITE.get(name) or ACCREDITATION_LOGOS.get(name)
        else:
            path = ACCREDITATION_LOGOS.get(name)
        if path and os.path.exists(path):
            try:
                lg = PILImage.open(path).convert("RGBA")
                ratio = logo_target_h / lg.height
                logos.append(lg.resize((int(lg.width * ratio), logo_target_h), PILImage.LANCZOS))
            except Exception:
                pass
    return logos


def overlay_top_bar(image_bytes, sector, selected_accreds):
    """Overlay logos directly on the visual — no background strip.
    Sector logo top-left, accreditation logos top-right.
    White or dark logo variant chosen by sampling background brightness.
    """
    if not _PIL_AVAILABLE:
        return image_bytes
    try:
        main = PILImage.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = main.size

        pad = 16
        sector_logo_h = max(62, int(h * 0.10))   # prominent but not oversized
        accred_logo_h = max(20, int(sector_logo_h * 0.45))  # secondary, smaller

        # ── Sector logo (top-left) ──
        # Sample brightness behind where the logo will sit
        sample_w = min(w // 3, 260)
        brightness_left = _bg_brightness(main, pad, pad, sample_w, sector_logo_h)
        use_white_sector = brightness_left < 140
        if use_white_sector:
            logo_path = SECTOR_LOGOS_WHITE.get(sector) or SECTOR_LOGOS.get(sector)
        else:
            logo_path = SECTOR_LOGOS_DARK.get(sector) or SECTOR_LOGOS.get(sector)

        if logo_path and os.path.exists(logo_path):
            try:
                logo = PILImage.open(logo_path).convert("RGBA")
                ratio = sector_logo_h / logo.height
                lw = int(logo.width * ratio)
                logo = logo.resize((lw, sector_logo_h), PILImage.LANCZOS)
                main.paste(logo, (pad, pad), logo)
            except Exception:
                pass

        # ── Accreditation logos (top-right) ──
        if selected_accreds:
            # Sample brightness on the right side where accred logos will sit
            brightness_right = _bg_brightness(main, w - w // 3, pad, w // 3, accred_logo_h + pad)
            use_white_accred = brightness_right < 140
            accred_logos = _load_accred_logos(selected_accreds, accred_logo_h, use_white=use_white_accred)
            if accred_logos:
                gap = 14
                total_w = sum(lg.width for lg in accred_logos) + gap * (len(accred_logos) - 1)
                x = w - pad - total_w
                y = pad + (sector_logo_h - accred_logo_h) // 2  # vertically align with sector logo
                for lg in accred_logos:
                    main.paste(lg, (x, y), lg)
                    x += lg.width + gap

        out = io.BytesIO()
        main.convert("RGB").save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return image_bytes


def overlay_accreditation_logos_bottom(image_bytes, selected_accreds):
    """Accreditation-only strip at the very bottom (used when no contact info)."""
    if not _PIL_AVAILABLE or not selected_accreds:
        return image_bytes
    try:
        main = PILImage.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = main.size

        strip_h = max(70, int(h * 0.10))
        pad = 12
        logo_target_h = strip_h - pad * 2

        brightness = _bg_brightness(main, 0, h - strip_h, w, strip_h)
        # Dark bottom bg → white strip + white logos; light bg → dark strip + dark logos
        if brightness < 140:
            strip_color = (255, 255, 255, 230)
            use_white = False
        else:
            strip_color = (20, 30, 50, 210)
            use_white = True

        logos = _load_accred_logos(selected_accreds, logo_target_h, use_white=use_white)
        if not logos:
            return image_bytes

        gap = 30
        total_w = sum(lg.width for lg in logos) + gap * (len(logos) - 1)

        strip = PILImage.new("RGBA", (w, strip_h), strip_color)
        x = (w - total_w) // 2
        y = (strip_h - logo_target_h) // 2
        for lg in logos:
            strip.paste(lg, (x, y), lg)
            x += lg.width + gap

        main.paste(strip, (0, h - strip_h), strip)
        out = io.BytesIO()
        main.convert("RGB").save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return image_bytes


# Keep old name as alias so any other references don't break
def overlay_sector_logo(image_bytes, sector):
    return image_bytes  # now handled inside overlay_top_bar


def overlay_accreditation_logos(image_bytes, selected_accreds, placement="bottom"):
    return image_bytes  # now handled by overlay_top_bar / overlay_accreditation_logos_bottom


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


def generate_with_openai(api_key, prompt, system_prompt, model, quality, size):
    """Generate image using OpenAI's Images API."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        full_prompt = f"{system_prompt}\n\n---\n\nUSER REQUEST:\n{prompt}"

        if model == "gpt-image-2":
            try:
                w, h = map(int, size.split("x"))
                w = max(256, (w // 16) * 16)
                h = max(256, (h // 16) * 16)
                w = min(w, 3840)
                h = min(h, 2160)
                openai_size = f"{w}x{h}"
            except ValueError:
                openai_size = "1024x1024"
        else:
            openai_size = OPENAI_SIZE_MAP.get(size, "1024x1024")

        result = client.images.generate(
            model=model,
            prompt=full_prompt,
            n=1,
            quality=quality,
            size=openai_size,
            output_format="png",
        )

        image_b64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_b64)

        usage_info = None
        if hasattr(result, "usage") and result.usage:
            usage_info = {
                "input_tokens": getattr(result.usage, "input_tokens", "N/A"),
                "output_tokens": getattr(result.usage, "output_tokens", "N/A"),
                "total_tokens": getattr(result.usage, "total_tokens", "N/A"),
            }

        return image_bytes, usage_info, None

    except ImportError:
        return None, None, "openai package not installed. Run: pip install openai"
    except Exception as e:
        return None, None, f"OpenAI API Error: {str(e)}"


def generate_with_gemini(api_key, prompt, system_prompt, size):
    """Generate image using Google Gemini Imagen 3."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        full_prompt = f"{system_prompt}\n\n---\n\nUSER REQUEST:\n{prompt}"

        w, h = map(int, size.split("x"))
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=full_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=_get_aspect_ratio(w, h),
            ),
        )

        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            return image_bytes, None, None

        return None, None, "Gemini returned no images. The prompt may have been filtered."

    except ImportError:
        return None, None, "google-genai package not installed. Run: pip install google-genai"
    except Exception as e:
        return None, None, f"Gemini API Error: {str(e)}"


def _get_aspect_ratio(w, h):
    ratio = w / h
    if ratio > 1.4:
        return "16:9"
    elif ratio > 1.1:
        return "4:3"
    elif ratio < 0.65:
        return "9:16"
    elif ratio < 0.85:
        return "3:4"
    else:
        return "1:1"


def generate_with_nano_banana(api_key, prompt, system_prompt, size):
    """Placeholder for Nano Banana provider."""
    return (
        None,
        None,
        "Nano Banana integration is a placeholder. "
        "Replace the generate_with_nano_banana() function in app.py "
        "with the actual API call when their SDK/API docs are available.",
    )


def generate_translation_image(api_key, ref_image_file, target_language,
                               model, quality, size, sector_info, colors):
    """Send reference image to OpenAI images.edit -- recreate with translated text."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        prompt = (
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
            f"The translated text must be perfectly spelled and crisp. "
            f"Professional marketing quality. No AI artifacts or garbled text."
        )

        if model == "gpt-image-2":
            try:
                w, h = map(int, size.split("x"))
                w = max(256, (w // 16) * 16)
                h = max(256, (h // 16) * 16)
                w, h = min(w, 3840), min(h, 2160)
                openai_size = f"{w}x{h}"
            except ValueError:
                openai_size = "1024x1024"
        else:
            openai_size = OPENAI_SIZE_MAP.get(size, "1024x1024")

        ref_image_file.seek(0)

        result = client.images.edit(
            model=model,
            image=ref_image_file,
            prompt=prompt,
            size=openai_size,
            quality=quality,
        )

        image_b64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_b64)

        usage_info = None
        if hasattr(result, "usage") and result.usage:
            usage_info = {
                "input_tokens": getattr(result.usage, "input_tokens", "N/A"),
                "output_tokens": getattr(result.usage, "output_tokens", "N/A"),
                "total_tokens": getattr(result.usage, "total_tokens", "N/A"),
            }

        return image_bytes, usage_info, None

    except ImportError:
        return None, None, "openai package not installed. Run: pip install openai"
    except Exception as e:
        return None, None, f"OpenAI API Error: {str(e)}"


def run_image_generation(api_key, image_prompt, system_prompt, provider_id,
                         provider_label, quality_tier, canvas_size, headline, post_type, sector, selected_accreds, has_contact=False, db_meta=None):
    """Shared generation logic. Returns True on success, False on failure."""
    with st.spinner(f"Generating with {provider_label}... This may take up to 2 minutes."):
        start_time = time.time()

        if provider_id == "prompt-only":
            st.success("Prompt generated. Check the JSON Export tab.")
            return True

        elif provider_id in ("gpt-image-2", "gpt-image-1"):
            image_bytes, usage, error = generate_with_openai(
                api_key, image_prompt, system_prompt,
                provider_id, quality_tier, canvas_size,
            )

        elif provider_id == "imagen-3":
            image_bytes, usage, error = generate_with_gemini(
                api_key, image_prompt, system_prompt, canvas_size,
            )
            usage = None

        elif provider_id == "nano-banana":
            _, _, error = generate_with_nano_banana(
                api_key, image_prompt, system_prompt, canvas_size,
            )
            st.warning(error)
            return False

        else:
            st.error("Unknown provider")
            return False

        elapsed = time.time() - start_time

        if error:
            st.error(error)
            return False
        else:
            # Always: sector logo left + accreditation logos right in top bar — never at bottom
            image_bytes = overlay_top_bar(image_bytes, sector, selected_accreds)

            # Save to local DB
            if db_meta:
                try:
                    save_post_to_db(image_bytes, image_prompt, system_prompt, db_meta)
                except Exception:
                    pass  # DB failure should never block the user

            st.success(f"Image generated in {elapsed:.1f}s")
            st.image(image_bytes, caption=headline, use_container_width=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_type = post_type.lower().replace(" ", "_")
            filename = f"alnafi_{safe_type}_{timestamp}.png"
            st.download_button(
                "Download Image",
                data=image_bytes,
                file_name=filename,
                mime="image/png",
                use_container_width=True,
            )

            if usage:
                with st.expander("Token Usage"):
                    st.json(usage)

            return True


def render_credentials_panel():
    """Render credentials controls. Returns (provider_label, provider_id, api_key, quality_tier)."""
    with st.expander("CREDENTIALS", expanded=True):
        provider_label = st.selectbox(
            "Provider",
            list(PROVIDERS.keys()),
            index=0,
            key="prov_sel",
        )
        provider_id = PROVIDERS[provider_label]

        api_key = ""
        quality_tier = "medium"

        if provider_id == "prompt-only":
            st.info("Prompt Only -- no API key needed.")
        else:
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


def render_visuals_panel(sector):
    """Render visuals controls. Returns (background_preset, background_custom, colors, font)."""
    with st.expander("VISUALS", expanded=False):
        bg_category = st.selectbox(
            "Background Category",
            ["None", "Custom Visual"] + list(BACKGROUND_PRESETS.keys()),
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
                BACKGROUND_PRESETS[bg_category],
                key="bg_preset",
            )

        st.markdown("**Color System**")
        sc = ALNAFI_SECTORS[sector]
        c1, c2, c3 = st.columns(3)
        with c1:
            color_primary = st.color_picker("Primary", sc["color_primary"], key="cp1")
        with c2:
            color_secondary = st.color_picker("Secondary", sc["color_secondary"], key="cp2")
        with c3:
            color_accent = st.color_picker("Accent", "#66BB6A", key="cp3")

        font = st.selectbox("Font Style", FONT_OPTIONS, index=0, key="font_sel")

    colors = {"primary": color_primary, "secondary": color_secondary, "accent": color_accent}
    return background_preset, background_custom, colors, font


def render_layout_panel():
    """Render layout controls. Returns (canvas_size, content_split, blend_angle, left_margin)."""
    with st.expander("LAYOUTS", expanded=False):
        canvas_preset = st.selectbox(
            "Canvas Size Preset", list(CANVAS_PRESETS.keys()), key="canvas_sel"
        )

        if canvas_preset == "Custom":
            cw, ch = st.columns(2)
            with cw:
                custom_w = st.number_input("Width", value=1080, min_value=256, max_value=3840, step=16, key="cw")
            with ch:
                custom_h = st.number_input("Height", value=1080, min_value=256, max_value=3840, step=16, key="ch")
            canvas_size = f"{custom_w}x{custom_h}"
        else:
            canvas_size = CANVAS_PRESETS[canvas_preset]

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


# ──────────────────────────────────────────────────────────────
# PAGE CONFIG & SHARED CSS
# ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Al-Nafi Image Generator",
    page_icon="AN",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    [data-testid="collapsedControl"] { display: none; }
    .stApp { background-color: #0E1117; }

    .panel-header {
        background: linear-gradient(135deg, #2D6FBC 0%, #1A4A8A 100%);
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
        background: #1a1a2e;
        border: 1px solid #2D6FBC;
        border-radius: 10px;
        padding: 16px;
        font-family: monospace;
        font-size: 13px;
        color: #e0e0e0;
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
    .pill-ready { background: #1B5E20; color: #A5D6A7; }
    .pill-missing { background: #4A1010; color: #EF9A9A; }

    .landing-card {
        background: linear-gradient(145deg, #151922 0%, #1a1f2e 100%);
        border: 1px solid #2a2f3e;
        border-radius: 16px;
        padding: 40px 30px;
        text-align: center;
        transition: border-color 0.2s;
    }
    .landing-card:hover { border-color: #2D6FBC; }
    .landing-card h2 { color: #fff; margin: 16px 0 8px 0; font-size: 24px; }
    .landing-card p { color: #888; font-size: 14px; line-height: 1.5; }
    .landing-icon { font-size: 42px; color: #2D6FBC; font-weight: 700; }

    .ref-image-frame {
        border: 2px solid #2a2f3e;
        border-radius: 12px;
        padding: 8px;
        background: #151922;
    }

    .logo-preview {
        background: #151922;
        border: 1px solid #2a2f3e;
        border-radius: 10px;
        padding: 12px;
        margin: 8px 0;
        text-align: center;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────────────────────

if "page" not in st.session_state:
    st.session_state.page = "landing"


# ──────────────────────────────────────────────────────────────
# LANDING PAGE
# ──────────────────────────────────────────────────────────────

def render_landing():
    st.markdown(
        """
        <div style="text-align:center; padding: 30px 0 10px 0;">
            <h1 style="margin:0; color:#2D6FBC; font-size:36px;">Al-Nafi Image Generation Agent</h1>
            <p style="color:#666; margin:6px 0 0 0; font-size:16px;">
                Create &amp; translate social media posts for Al-Nafi Group
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")

    _, card_left, spacer, card_right, _ = st.columns([1, 4, 0.5, 4, 1])

    with card_left:
        st.markdown(
            """
            <div class="landing-card">
                <div class="landing-icon">+</div>
                <h2>Generate New Post</h2>
                <p>
                    Create fresh social media graphics from scratch.
                    Pick your sector, fill in content, choose visuals,
                    and generate with AI.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Start Generating", type="primary", use_container_width=True, key="go_gen"):
            st.session_state.page = "generation"
            st.rerun()

    with card_right:
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

    st.markdown("")
    _, hist_col, _ = st.columns([2, 6, 2])
    with hist_col:
        total = len(load_all_posts(limit=9999))
        st.markdown(
            f"""
            <div class="landing-card">
                <div class="landing-icon">H</div>
                <h2>Post History</h2>
                <p>
                    Browse every image previously generated.<br>
                    Re-download or review prompts without spending API credits.<br>
                    <strong>{total} post{"s" if total != 1 else ""} saved</strong>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Open History", type="secondary", use_container_width=True, key="go_hist"):
            st.session_state.page = "history"
            st.rerun()


# ──────────────────────────────────────────────────────────────
# HISTORY PAGE
# ──────────────────────────────────────────────────────────────

def render_history():
    st.markdown(
        '<h2 style="margin:0 0 8px 0; color:#2D6FBC;">Post History</h2>',
        unsafe_allow_html=True,
    )

    if st.button("Back to Home", key="hist_back"):
        st.session_state.page = "landing"
        st.rerun()

    posts = load_all_posts()
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
                with st.expander("Prompts", expanded=False):
                    st.markdown("**Image Prompt**")
                    st.code(p["image_prompt"] or "", language="text")
                    if p.get("system_prompt"):
                        st.markdown("**System Prompt**")
                        st.code(p["system_prompt"], language="text")
                if st.button("Delete", key=f"del_{p['id']}", type="secondary"):
                    delete_post_from_db(p["id"])
                    st.rerun()
                st.markdown("---")


# ──────────────────────────────────────────────────────────────
# GENERATION PAGE
# ──────────────────────────────────────────────────────────────

def render_generation():
    main_col, controls_col = st.columns([65, 35], gap="medium")

    # ── RIGHT: Controls ──
    with controls_col:
        if st.button("Back to Home", key="gen_back"):
            st.session_state.page = "landing"
            st.rerun()

        st.markdown('<div class="panel-header">Generate New Post</div>', unsafe_allow_html=True)

        provider_label, provider_id, api_key, quality_tier = render_credentials_panel()

        # ── CONTENT ──
        with st.expander("CONTENT", expanded=True):
            sector = st.selectbox("Al-Nafi Sector *", list(ALNAFI_SECTORS.keys()), key="gen_sector")

            # Accreditation logo selection (only logos valid for this sector are shown)
            available_accreds = SECTOR_ACCREDITATIONS.get(sector, [])
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

            post_type = st.selectbox("Post Type *", POST_TYPES, key="gen_pt")
            badge = st.selectbox("Session Badge", SESSION_BADGES, key="gen_badge")
            platforms = st.multiselect(
                "Target Platform(s) *", PLATFORM_TARGETS,
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
                _sector_url = SECTOR_WEBSITES.get(sector, "")
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
    sector_info = ALNAFI_SECTORS[sector]
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


# ──────────────────────────────────────────────────────────────
# TRANSLATION PAGE
# ──────────────────────────────────────────────────────────────

def _make_translation_prompt(target_language, sector_info, colors):
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


def _translate_one(api_key, img_bytes, img_name, target_language,
                   provider_id, quality_tier, canvas_size, sector_info, colors):
    """Worker function: translate a single image to a single language. Returns dict."""
    import io as _io
    file_like = _io.BytesIO(img_bytes)
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
                TRANSLATION_LANGUAGES,
                default=["Urdu"],
                key="trans_langs",
            )

    # ── Derived values ──
    sector = "Al Nafi International College"
    sector_info = ALNAFI_SECTORS[sector]
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


# ──────────────────────────────────────────────────────────────
# ROUTER
# ──────────────────────────────────────────────────────────────

page = st.session_state.page

if page == "landing":
    render_landing()
elif page == "generation":
    render_generation()
elif page == "translation":
    render_translation()
elif page == "history":
    render_history()
else:
    st.session_state.page = "landing"
    st.rerun()