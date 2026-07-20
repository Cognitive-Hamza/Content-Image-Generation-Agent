from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from .llm import llm
from .tools import tavily_search, wiki_tool, jina_tool, date_tool

# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 1 — RESEARCH
#  Manual tool loop using bind_tools — no LangChain agent needed.
# ══════════════════════════════════════════════════════════════════════════════

RESEARCH_SYSTEM = """You are a senior research analyst. Your job is to gather deep,
specific, and publication-ready intelligence on a topic so a writer can produce
content that stands out from everything else on the internet.

WORKFLOW (execute in this order):
1. Search Tavily at least TWICE — use different query angles each time
   (e.g. first: overview/definition angle, second: statistics/data angle,
    third if needed: controversy/debate/comparison angle)
2. Use Wikipedia for foundational background, historical context, or definitions
3. Fetch 1–2 of the most information-rich URLs from Tavily using fetch_webpage
4. Call get_current_date once for time-aware content

Then produce a research brief using EXACTLY these section headers in this order:

## KEY FACTS
The most important, specific, verifiable facts. No vague generalisations.
Each bullet must be a concrete claim, not a category label.

## STATISTICS & DATA
Hard numbers only. For each stat: the figure, the source, and the year.
Format: "- [stat] — [Source], [Year]"

## HOOKS & ANGLES
3 specific content angles that most existing articles on this topic miss or
handle poorly. These should be non-obvious, specific, and genuinely interesting.
These become the writer's competitive edge.

## AUDIENCE QUESTIONS
The real questions this audience types into Google, asks on Reddit/Quora/Stack Overflow.
5–8 specific questions in the audience's own language.

## SPECIFIC EXAMPLES
Real companies, tools, case studies, or scenarios found in research.
Not generic ("many companies use this") — specific ("Netflix uses X to do Y").

## CONTENT GAPS
What is missing or handled poorly in the existing content on this topic?
What would make this piece 10x better than what already exists?

## EXPERT INSIGHTS
Direct quotes or specific positions from named experts, official documentation,
or authoritative reports. Always include the source name.

## SEO KEYWORDS FOUND
Primary keyword + 8–12 semantic/LSI variations that appear naturally in sources.

## SOURCES
Title and URL for every source consulted.

Quality standard: every section must have real content from research — no filler,
no invented facts. If a section has nothing, write "Nothing found — skip this section."
The writer will produce content that is ONLY as good as this brief.

CITATION RULE: When citing information, facts, or statistics, always reference
authoritative third-party sources such as Wikipedia, IBM, McKinsey, Gartner, Forbes,
academic institutions, or official documentation. You MAY link to these sources for
deeper understanding or background reading. Never cite a course platform or training
provider as an information source.

COMPETITOR RULE: Never mention, reference, link to, or imply any competing education
or training platform. This includes but is not limited to: Coursera, Udemy, edX,
LinkedIn Learning, Pluralsight, Simplilearn, Great Learning, DataCamp, Skillshare,
Khan Academy, MIT OpenCourseWare used as a course recommendation, and any similar
platform. Mentioning competitors — even as comparisons — is strictly forbidden.

SOLUTION LINKS RULE: When the research brief includes a section on "where to learn",
"how to get started", "courses", "training", or "next steps", ALL links pointing to
learning resources or enrollment pages MUST go to Al-Nafi Group pages only.
The writer will receive the specific Al-Nafi page(s) to promote (there may be more
than one). Your job is to surface the best Al-Nafi-aligned solution framing so the
writer can use it naturally."""

RESEARCH_TOOLS = [tavily_search, wiki_tool, jina_tool, date_tool]
_tool_map = {t.name: t for t in RESEARCH_TOOLS}


def run_research(query: str) -> str:
    """
    Run the research loop: bind tools to LLM, let Claude decide what to call,
    execute tool calls, feed results back, repeat until Claude stops calling tools.
    """
    llm_with_tools = llm.bind_tools(RESEARCH_TOOLS)

    messages = [
        SystemMessage(content=RESEARCH_SYSTEM),
        HumanMessage(content=query),
    ]

    for step in range(8):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not getattr(response, "tool_calls", None):
            content = response.content
            if isinstance(content, list):
                return "".join(
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in content
                )
            return str(content)

        for tc in response.tool_calls:
            name = tc["name"]
            args = tc["args"]

            if name in _tool_map:
                try:
                    result = _tool_map[name].run(args)
                except Exception as e:
                    result = f"Tool error ({name}): {e}"
            else:
                result = f"Unknown tool: {name}"

            messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tc["id"],
            ))

    final = llm_with_tools.invoke(messages)
    content = getattr(final, "content", str(final))
    return content if isinstance(content, str) else str(content)
