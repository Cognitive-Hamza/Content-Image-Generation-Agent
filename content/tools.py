import requests
from datetime import datetime
from langchain_tavily import TavilySearch
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.tools import StructuredTool


# ── TAVILY SEARCH (primary search tool) ───────────────────────────────────────

tavily_search = TavilySearch(
    max_results=5,
    search_depth="advanced",
    include_answer=True,
    include_images=False,
)


# ── WIKIPEDIA (free, zero API key required) ────────────────────────────────────
wiki_wrapper = WikipediaAPIWrapper(top_k_results=2, doc_content_chars_max=2000)
wiki_tool = WikipediaQueryRun(api_wrapper=wiki_wrapper)


# ── JINA READER (free web fetcher, no API key required) ───────────────────────
def fetch_webpage(url: str) -> str:
    """Fetch the full readable text of a webpage by URL."""
    try:
        jina_url = f"https://r.jina.ai/{url.strip()}"
        headers = {"Accept": "text/plain", "X-No-Cache": "true"}
        response = requests.get(jina_url, headers=headers, timeout=20)
        if response.status_code == 200:
            return response.text[:4000]
        return f"Fetch failed: HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        return "Error: Request timed out."
    except Exception as e:
        return f"Error fetching page: {str(e)}"

# StructuredTool gives Claude a clean 'url' parameter name in the schema
jina_tool = StructuredTool.from_function(
    func=fetch_webpage,
    name="fetch_webpage",
    description=(
        "Fetch the full readable content of a webpage. "
        "Use this on URLs from Tavily search results to get the full article text. "
        "Input: a valid URL starting with http:// or https://"
    ),
)


# ── DATE TOOL (free, no API key) ───────────────────────────────────────────────
def get_current_date(query: str = "") -> str:
    """Returns today's date."""
    return f"Today's date is: {datetime.now().strftime('%B %d, %Y')}"

date_tool = StructuredTool.from_function(
    func=get_current_date,
    name="get_current_date",
    description="Returns today's date. Use when content needs to reference recency or time-sensitive facts.",
)