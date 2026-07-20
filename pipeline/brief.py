import re
from dataclasses import dataclass

BRIEF_FIELD_PATTERN = re.compile(
    r"\*\*(Headline|Hook Line|Title|Visual Recommendation):\*\*\s*(.+)"
)


@dataclass
class ContentDesignBrief:
    headline: str = ""
    hook_line: str = ""
    title: str = ""
    visual_recommendation: str = ""

    @property
    def is_empty(self) -> bool:
        return not any([
            self.headline, self.hook_line, self.title, self.visual_recommendation,
        ])


def parse_content_design_brief(markdown: str) -> ContentDesignBrief:
    """Extract the '## Content Design Brief' section's fields from a generated
    article. Tolerant of the section being anywhere in the doc, of missing
    fields, or of extra whitespace/markdown drift around the bold field
    labels. Never raises — a field that can't be found comes back as "",
    and callers should treat an all-empty result as 'no brief found'."""
    match = re.search(r"## Content Design Brief(.*?)(?=\n## |\Z)", markdown, re.DOTALL)
    section = match.group(1) if match else markdown

    fields = {}
    for label, value in BRIEF_FIELD_PATTERN.findall(section):
        key = label.lower().replace(" ", "_")
        fields[key] = value.strip().rstrip("-").strip()

    return ContentDesignBrief(
        headline=fields.get("headline", ""),
        hook_line=fields.get("hook_line", ""),
        title=fields.get("title", ""),
        visual_recommendation=fields.get("visual_recommendation", ""),
    )
