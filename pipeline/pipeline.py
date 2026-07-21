import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.storage.base import StorageBackend

from .config import SOCIAL_PLATFORM_RULES
from .research import run_research
from .writer import (
    writer_prompt, get_writer_chain,
    get_refinement_chain,
    social_caption_prompt, get_social_caption_chain,
    get_quick_copy_chain,
)

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:50]


def save_output(topic: str, content: str, *, storage: "StorageBackend | None" = None) -> tuple[str, str | None]:
    """Writes the markdown locally (unchanged behavior) and, if a StorageBackend
    is supplied, also pushes it through storage — returns (filepath, storage_key).
    `storage` is optional so existing callers (the Streamlit app) are unaffected;
    only the new FastAPI routes pass one."""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{slugify(topic)}_{timestamp}.md"
    filepath = OUTPUTS_DIR / filename
    filepath.write_text(content, encoding="utf-8")

    storage_key = None
    if storage is not None:
        storage_key = storage.save(
            f"outputs/generations/{filename}", content.encode("utf-8"), content_type="text/markdown"
        )

    return str(filepath), storage_key


@dataclass
class LongFormResult:
    research_text: str
    final_content: str
    writer_system_text: str
    writer_human_text: str
    filepath: str
    db_id: int
    output_storage_key: str | None = None


def generate_long_form_content(
    *, topic: str, keywords: str, audience: str, content_type: str, word_count: str,
    tone: str, plat_name: str, plat_domain: str, alnafi_promo: str,
    on_stage: Callable[[str], None] | None = None,
    storage: "StorageBackend | None" = None,
    db: "Session",
    created_by_user_id: int | None = None,
) -> LongFormResult:
    """Run the research -> write -> refine pipeline and persist the result.
    `on_stage` is an optional progress callback for a caller-side status
    widget (e.g. an SSE stage update)."""
    from app.db import repo_content

    if on_stage:
        on_stage("researching")
    research_query = (
        f"Research this topic thoroughly for a {content_type} "
        f"targeting the keywords '{keywords}' "
        f"for this audience: {audience}. Topic: {topic}. "
        f"This content is for {plat_name} ({plat_domain}). "
        f"All solution/learning links must point to {plat_domain}. "
        f"Do NOT reference any competing platforms."
    )
    try:
        research_text = run_research(research_query)
    except Exception:
        research_text = f"Topic: {topic}. Keywords: {keywords}."

    if on_stage:
        on_stage("writing")
    writer_system_text = writer_prompt.messages[0].prompt.template
    writer_human_text = (
        f"TOPIC: {topic} | PLATFORM: {plat_name} | TYPE: {content_type} | "
        f"AUDIENCE: {audience} | KEYWORDS: {keywords} | PAGE: {alnafi_promo}"
    )
    write_result = get_writer_chain().invoke({
        "research": research_text,
        "topic": topic,
        "plat_name": plat_name,
        "plat_domain": plat_domain,
        "content_type": content_type,
        "keywords": keywords,
        "audience": audience,
        "tone": tone,
        "word_count": word_count,
        "alnafi_promo": alnafi_promo,
    })
    draft = write_result.content if hasattr(write_result, "content") else str(write_result)

    if on_stage:
        on_stage("refining")
    try:
        refined_result = get_refinement_chain().invoke({
            "draft": draft,
            "audience": audience,
            "plat_name": plat_name,
            "plat_domain": plat_domain,
            "content_type": content_type,
            "keywords": keywords,
            "alnafi_promo": alnafi_promo,
        })
        content = refined_result.content if hasattr(refined_result, "content") else str(refined_result)
    except Exception:
        content = draft

    filepath, output_storage_key = save_output(topic, content, storage=storage)
    generation = repo_content.save_generation(
        db, created_by_user_id=created_by_user_id,
        topic=topic, platform=plat_name, page_promoted=alnafi_promo,
        content_type=content_type, audience=audience, tone=tone,
        keywords=keywords, research_brief=research_text,
        writer_system=writer_system_text, writer_human=writer_human_text,
        final_content=content, output_storage_key=output_storage_key,
    )
    db_id = generation.id

    if on_stage:
        on_stage("done")

    return LongFormResult(
        research_text=research_text,
        final_content=content,
        writer_system_text=writer_system_text,
        writer_human_text=writer_human_text,
        filepath=filepath,
        db_id=db_id,
        output_storage_key=output_storage_key,
    )


@dataclass
class SocialCaptionResult:
    content: str
    filepath: str
    db_id: int
    output_storage_key: str | None = None


def generate_social_captions(
    *, topic: str, keywords: str, audience: str, plat_name: str, plat_domain: str,
    alnafi_promo: str, chosen_platforms: list[str], post_type: str, caption_goal: str,
    storage: "StorageBackend | None" = None,
    db: "Session",
    created_by_user_id: int | None = None,
) -> SocialCaptionResult:
    from app.db import repo_content

    platforms_list = "\n".join(f"- {p}" for p in chosen_platforms)
    platform_rules = "\n\n".join(
        f"{p}:\n{SOCIAL_PLATFORM_RULES[p]}"
        for p in chosen_platforms
        if p in SOCIAL_PLATFORM_RULES
    )

    writer_system_text = social_caption_prompt.messages[0].prompt.template
    writer_human_text = (
        f"TOPIC: {topic}\nPLATFORM: {plat_name}\nPOST TYPE: {post_type}\n"
        f"AUDIENCE: {audience}\nKEYWORDS: {keywords}\nPAGE: {alnafi_promo}\n"
        f"PLATFORMS: {platforms_list}"
    )

    result = get_social_caption_chain().invoke({
        "topic": topic,
        "plat_name": plat_name,
        "plat_domain": plat_domain,
        "post_type": post_type,
        "audience": audience,
        "keywords": keywords,
        "alnafi_promo": alnafi_promo,
        "platforms_list": platforms_list,
        "platform_rules": platform_rules,
    })
    content = result.content if hasattr(result, "content") else str(result)

    filepath, output_storage_key = save_output(topic, content, storage=storage)
    social_meta = {"platforms": chosen_platforms, "post_type": post_type, "goal": caption_goal}
    generation = repo_content.save_generation(
        db, created_by_user_id=created_by_user_id,
        topic=topic, platform=plat_name, page_promoted=alnafi_promo,
        content_type="Social Media Captions", audience=audience, tone="N/A",
        keywords=keywords, research_brief="N/A (social captions — no research stage)",
        writer_system=writer_system_text, writer_human=writer_human_text,
        final_content=content, output_storage_key=output_storage_key, social_meta=social_meta,
    )
    return SocialCaptionResult(content=content, filepath=filepath, db_id=generation.id, output_storage_key=output_storage_key)


@dataclass
class QuickCopy:
    headline: str = ""
    hook_line: str = ""
    short_caption: str = ""


_QUICK_COPY_PATTERN = re.compile(r"(Headline|Hook Line|Short Caption):\s*(.+)")


def generate_quick_copy(
    *, topic: str, plat_name: str, plat_domain: str, alnafi_promo: str,
    tone: str = "Professional",
) -> QuickCopy:
    """Single-call, no research/refine stage — fast copy for images-only
    scenarios where a user just wants a headline/hook for an image and
    doesn't need (or want to wait for) the full content pipeline. Deliberately
    NOT persisted to the generations table: this is throwaway copy, not a
    tracked content asset."""
    result = get_quick_copy_chain().invoke({
        "topic": topic,
        "plat_name": plat_name,
        "plat_domain": plat_domain,
        "alnafi_promo": alnafi_promo,
        "tone": tone,
    })
    text = result.content if hasattr(result, "content") else str(result)

    fields = {}
    for label, value in _QUICK_COPY_PATTERN.findall(text):
        fields[label.lower().replace(" ", "_")] = value.strip()

    return QuickCopy(
        headline=fields.get("headline", ""),
        hook_line=fields.get("hook_line", ""),
        short_caption=fields.get("short_caption", ""),
    )
