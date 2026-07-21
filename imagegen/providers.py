import base64
import io
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .config import OPENAI_SIZE_MAP
from .logos import overlay_top_bar

if TYPE_CHECKING:
    from app.storage.base import StorageBackend


@dataclass
class ImageGenResult:
    success: bool
    image_bytes: bytes | None
    usage: dict | None
    error: str | None
    elapsed_s: float
    post_id: int | None
    storage_key: str | None = None


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


def generate_with_nano_banana(api_key, prompt, system_prompt, size):
    """Placeholder for Nano Banana provider."""
    return (
        None,
        None,
        "Nano Banana integration is a placeholder. "
        "Replace the generate_with_nano_banana() function in imagegen/providers.py "
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


def generate_image(api_key, image_prompt, system_prompt, provider_id,
                    provider_label, quality_tier, canvas_size, headline, post_type, sector, selected_accreds,
                    has_contact=False, storage: "StorageBackend | None" = None):
    """Shared generation logic. Returns an ImageGenResult — pure, no UI side effects.

    If a StorageBackend is supplied, the generated bytes are pushed through it
    and the resulting key is returned on the result; the caller (a FastAPI
    route) then does its own Postgres repo write with that key.
    """
    start_time = time.time()

    if provider_id == "prompt-only":
        return ImageGenResult(True, None, None, None, time.time() - start_time, None)

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
        return ImageGenResult(False, None, None, error, time.time() - start_time, None)

    else:
        return ImageGenResult(False, None, None, "Unknown provider", time.time() - start_time, None)

    elapsed = time.time() - start_time

    if error:
        return ImageGenResult(False, None, None, error, elapsed, None)

    # Always: sector logo left + accreditation logos right in top bar — never at bottom
    image_bytes = overlay_top_bar(image_bytes, sector, selected_accreds)

    storage_key = None
    if storage is not None:
        storage_key = storage.save(
            f"images/generated_posts/{uuid.uuid4()}.png", image_bytes, content_type="image/png"
        )

    return ImageGenResult(True, image_bytes, usage, None, elapsed, None, storage_key)
