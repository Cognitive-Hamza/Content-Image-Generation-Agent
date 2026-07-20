import base64
import io
import os
from pathlib import Path

try:
    from PIL import Image as PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

_ASSETS_DIR = Path(__file__).parent.parent / "assets"
_SECTOR_LOGO_DIR = _ASSETS_DIR / "al_nafi_logos"
_ACCRED_LOGO_DIR = _ASSETS_DIR / "accreditation_logos"

# Default (color) logos
SECTOR_LOGOS = {
    "Al Nafi International College": str(_SECTOR_LOGO_DIR / "alnafi-int-college.png"),
    "Al Nafi Islamic College":       str(_SECTOR_LOGO_DIR / "alnafi-islamic-college.png"),
    "Al Nafi Academy":               str(_SECTOR_LOGO_DIR / "alnafi-academy.png"),
    "Alnafi Cloud":                  str(_SECTOR_LOGO_DIR / "alnafi-cloud-logo.png"),
    "Annaafi PAY":                   str(_SECTOR_LOGO_DIR / "alnafi-epay-logo.png"),
}

# White versions — for dark strip backgrounds
SECTOR_LOGOS_WHITE = {
    "Al Nafi International College": str(_SECTOR_LOGO_DIR / "alnafi-int-college-white.png"),
    "Alnafi Cloud":                  str(_SECTOR_LOGO_DIR / "alnafi-cloud-white-logo.png"),
}

# Dark/color logos used on light backgrounds (no black-specific files for most brands)
SECTOR_LOGOS_DARK = {
    "Al Nafi International College": str(_SECTOR_LOGO_DIR / "alnafi-int-college.png"),
    "Al Nafi Islamic College":       str(_SECTOR_LOGO_DIR / "alnafi-islamic-college.png"),
    "Al Nafi Academy":               str(_SECTOR_LOGO_DIR / "alnafi-academy.png"),
    "Alnafi Cloud":                  str(_SECTOR_LOGO_DIR / "alnafi-cloud-logo.png"),
    "Annaafi PAY":                   str(_SECTOR_LOGO_DIR / "alnafi-epay-logo.png"),
}

# Default (color) — same as DARK for now; kept separate so callers stay readable
ACCREDITATION_LOGOS = {
    "Pearson BTEC": str(_ACCRED_LOGO_DIR / "pearson-black-logo.png"),
    "EduQual UK":   str(_ACCRED_LOGO_DIR / "eduqual-logo.png"),
    "ISACA":        str(_ACCRED_LOGO_DIR / "isaca-logo.png"),
    "EADL":         str(_ACCRED_LOGO_DIR / "eadl-logo.jpg"),
}

# White variants — for dark strip backgrounds
ACCREDITATION_LOGOS_WHITE = {
    "Pearson BTEC": str(_ACCRED_LOGO_DIR / "pearson-white-logo.png"),
    "EduQual UK":   str(_ACCRED_LOGO_DIR / "eduqual-logo-white.png"),
    "ISACA":        str(_ACCRED_LOGO_DIR / "isaca-logo-white.png"),
    "EADL":         str(_ACCRED_LOGO_DIR / "eadl-logo-white.png"),
}


def _logo_to_img_tag(path, alt, style):
    """Load a logo file from disk and return an HTML img tag, or a placeholder div if missing."""
    if not path or not os.path.exists(path):
        return (
            f'<div style="padding:4px 8px;background:#F5F9FF;border:1px dashed #A9C6E8;'
            f'border-radius:4px;color:#5A6B7A;font-size:10px;font-family:monospace;">'
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


# Kept as aliases so any other references don't break — logo placement now
# lives entirely inside overlay_top_bar / overlay_accreditation_logos_bottom.
def overlay_sector_logo(image_bytes, sector):
    return image_bytes


def overlay_accreditation_logos(image_bytes, selected_accreds, placement="bottom"):
    return image_bytes
