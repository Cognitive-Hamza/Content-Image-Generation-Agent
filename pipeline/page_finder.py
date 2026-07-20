from dataclasses import dataclass

from rapidfuzz import fuzz

from . import config

HIGH_CONFIDENCE_THRESHOLD = 85


@dataclass
class PageMatch:
    platform: str
    plat_domain: str
    page_name: str
    url: str
    description: str
    score: float


def _all_pages():
    for _, (plat_name, plat_domain, pages, _default) in config.PLATFORMS.items():
        for _, (name, url, desc) in pages.items():
            yield plat_name, plat_domain, name, url, desc


def find_best_page(query: str, platform: str | None = None, top_n: int = 5) -> list[PageMatch]:
    """Fuzzy-search the Al Nafi page catalogues by free-text subject (e.g. "AIOps")
    instead of requiring the caller to browse a nested platform -> page dropdown.

    Scores the query against each page's name + description across all platforms
    (or just one platform if `platform` is given), returning candidates sorted
    best-first. Callers should auto-select when the top result's score clears
    HIGH_CONFIDENCE_THRESHOLD; otherwise present the top_n candidates for the
    user to confirm with one click.
    """
    query = query.strip()
    if not query:
        return []

    candidates = []
    for plat_name, plat_domain, name, url, desc in _all_pages():
        if platform and plat_name != platform:
            continue
        # Score against the page name and description separately rather than
        # a single concatenated haystack — concatenating let common words in
        # long descriptions (e.g. "Computing") outscore a much more relevant
        # page whose actual name matches the query, producing bad rankings.
        # A description hit is kept as a discounted fallback signal only.
        name_score = fuzz.WRatio(query, name)
        desc_score = fuzz.WRatio(query, desc)
        score = max(name_score, desc_score * 0.7)
        candidates.append(PageMatch(
            platform=plat_name, plat_domain=plat_domain,
            page_name=name, url=url, description=desc, score=score,
        ))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:top_n]
