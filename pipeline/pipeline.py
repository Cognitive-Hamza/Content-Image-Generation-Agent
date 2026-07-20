import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import SOCIAL_PLATFORM_RULES
from .research import run_research
from .writer import (
    writer_prompt, writer_chain,
    refinement_chain,
    social_caption_prompt, social_caption_chain,
    quick_copy_chain,
)

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:50]


def save_output(topic: str, content: str) -> str:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = OUTPUTS_DIR / f"{slugify(topic)}_{timestamp}.md"
    filepath.write_text(content, encoding="utf-8")
    return str(filepath)


@dataclass
class LongFormResult:
    research_text: str
    final_content: str
    writer_system_text: str
    writer_human_text: str
    filepath: str
    db_id: int


def generate_long_form_content(
    *, topic: str, keywords: str, audience: str, content_type: str, word_count: str,
    tone: str, plat_name: str, plat_domain: str, alnafi_promo: str,
    on_stage: Callable[[str], None] | None = None,
) -> LongFormResult:
    """Run the research -> write -> refine pipeline and persist the result.
    `on_stage` is an optional progress callback (e.g. for a Streamlit spinner);
    this module never imports streamlit itself so it stays usable standalone."""
    from db import content_repo

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
    write_result = writer_chain.invoke({
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
        refined_result = refinement_chain.invoke({
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

    filepath = save_output(topic, content)
    db_id = content_repo.save_generation(
        topic=topic, platform=plat_name, page_promoted=alnafi_promo,
        content_type=content_type, audience=audience, tone=tone,
        keywords=keywords, research_brief=research_text,
        writer_system=writer_system_text, writer_human=writer_human_text,
        final_content=content, filepath=filepath,
    )

    if on_stage:
        on_stage("done")

    return LongFormResult(
        research_text=research_text,
        final_content=content,
        writer_system_text=writer_system_text,
        writer_human_text=writer_human_text,
        filepath=filepath,
        db_id=db_id,
    )


@dataclass
class SocialCaptionResult:
    content: str
    filepath: str
    db_id: int


def generate_social_captions(
    *, topic: str, keywords: str, audience: str, plat_name: str, plat_domain: str,
    alnafi_promo: str, chosen_platforms: list[str], post_type: str, caption_goal: str,
) -> SocialCaptionResult:
    from db import content_repo

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

    result = social_caption_chain.invoke({
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

    filepath = save_output(topic, content)
    social_meta = {"platforms": chosen_platforms, "post_type": post_type, "goal": caption_goal}
    db_id = content_repo.save_generation(
        topic=topic, platform=plat_name, page_promoted=alnafi_promo,
        content_type="Social Media Captions", audience=audience, tone="N/A",
        keywords=keywords, research_brief="N/A (social captions — no research stage)",
        writer_system=writer_system_text, writer_human=writer_human_text,
        final_content=content, filepath=filepath, social_meta=social_meta,
    )
    return SocialCaptionResult(content=content, filepath=filepath, db_id=db_id)


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
    result = quick_copy_chain.invoke({
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
