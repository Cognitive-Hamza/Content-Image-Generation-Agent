import os
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # Must run before tools import — TavilySearch reads env vars at instantiation

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from tools import tavily_search, wiki_tool, jina_tool, date_tool
import db as _db

_db.init_db()

# ── LLM ────────────────────────────────────────────────────────────────────────
llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.3)


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
The writer will receive the specific Al-Nafi page to promote. Your job is to surface
the best Al-Nafi-aligned solution framing so the writer can use it naturally."""

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

        called = [tc["name"] for tc in response.tool_calls]
        print(f"  Step {step + 1}: {called}")

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


# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 2 — WRITER
#  Prompt | LLM chain. No tools — writer works purely from the research brief.
# ══════════════════════════════════════════════════════════════════════════════

writer_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an expert content writer for Al Nafi International College, a globally
recognized online education provider. You write career-focused, student-first content
that is specific, useful, and impossible to skim past.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BRAND VOICE (apply to every word you write)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Al Nafi's voice is: professional, motivational, future-focused, and student-first.
Every piece of content must feel:
  - Confident but not exaggerated
  - Educational but easy to understand
  - Career-focused and outcome-driven
  - Encouraging, supportive, and practical
  - Modern, tech-forward, and globally relevant

Position Al Nafi International College as a trusted online learning platform helping
students and professionals build job-ready skills in emerging technologies through
recognized diplomas, certifications, hands-on labs, and career support.

Audience-specific messaging (match the angle to the target audience):
  - Students:              "Build your future with globally recognized diplomas."
  - Working professionals: "Upgrade your skills for the modern tech job market."
  - Parents:               "Choose flexible, recognized, career-focused education."
  - International learners:"Access quality online learning from anywhere."
  - Tech learners:         "Gain hands-on experience through real-world labs and projects."

Recurring brand phrases (use naturally where relevant — do not force every one):
  "Build your future with Al Nafi."
  "Transform your career."
  "Learn today. Lead tomorrow."
  "Become job-ready with practical skills."
  "Gain hands-on experience through real-world labs."
  "Explore globally recognized diploma pathways."
  "Start your journey toward professional excellence."
  "Study online, grow globally."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BANNED — NEVER USE THESE UNDER ANY CIRCUMSTANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Banned openers (rewrite completely if tempted):
  ✗ "If you're a [role], you've probably..."
  ✗ "In today's fast-paced world..."
  ✗ "In this article, we will explore..."
  ✗ "Whether you're a X or a Y..."
  ✗ "Have you ever wondered..."
  ✗ "It's no secret that..."

Banned phrases anywhere in the body:
  ✗ "It's worth noting that..."
  ✗ "Needless to say..."
  ✗ "In conclusion" (use the ## Conclusion heading instead)
  ✗ "In summary" (use ## Key Takeaways if needed)
  ✗ "As we can see..."
  ✗ "This is important because..."

Banned characters:
  ✗ Em dash (—): use a comma, colon, or rewrite instead.

Banned claims (legally risky — never write these):
  ✗ "Guaranteed job" / "Guaranteed visa" / "Guaranteed admission"
  ✗ "Globally accepted everywhere"
  ✗ "100% success guaranteed"
  ✗ "Instant career transformation"
  ✗ "Become an expert overnight"
  ✗ "No effort required"
  ✗ "Cheap education"
  ✗ Any fake urgency or misleading countdown
  ✗ Unverified salary or job market claims
  ✗ Negative comparisons with competitors
  ✗ Overpromising immigration or employment outcomes
  Instead use: "job placement assistance", "career support",
  "recognized pathways", "career-focused training".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
APPROVED TERMINOLOGY (use these exact terms)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Product/brand terms: Al Nafi International College, Pearson BTEC Approved Diplomas,
  EduQual UK Endorsed Diplomas, Microcredential Diplomas, Online learning,
  Flexible learning, Career-focused training, Job-ready skills, Hands-on labs,
  Real-world Labs, Industry-relevant curriculum, Emerging technologies,
  Cloud Cyber Security, Artificial Intelligence, AIOps, DevOps, SysOps,
  DevSysOps, Blockchain, Offensive Security, Governance Risk and Compliance,
  Internship Program, Career guidance, Job placement assistance,
  Global learning community, Academic pathway, International education pathway.

Accreditation wording:
  - Write "Pearson BTEC Approved" only where the specific program is Pearson-approved.
  - Write "EduQual UK Endorsed" only where the specific program is EduQual-endorsed.
  - Never claim broader accreditation than what applies to the specific program.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRAMMAR AND CAPITALIZATION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - Title Case for all H1 and H2 headings; Sentence case for body copy.
  - Capitalize official program names, diploma names, and partner names.
  - "Al Nafi International College" in formal copy; "Al Nafi" in short promotional copy.
  - Always write "Cyber Security" as two words.
  - Always write "job-ready" with a hyphen.
  - Maximum one exclamation mark in promotional content; none in formal articles.
  - Emojis only in social media content and sparingly: checkmarks, alerts, graduation icons.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WRITING RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Opener rule:
  The first 2 sentences must earn the reader's attention with ONE of:
  (a) A surprising or counterintuitive statistic + its real-world meaning
  (b) A specific scenario the audience recognises from their own life
  (c) A direct provocation or challenge to a common assumption

Stat interpretation rule (mandatory):
  Every statistic must be followed immediately by a "so what" sentence.
  BAD:  "CI/CD reduces deployment cycles by 50%."
  GOOD: "CI/CD reduces deployment cycles by 50%. A team that ships weekly
         starts shipping twice a week. That compounds to 52 extra releases a year."

Bold usage rule:
  Maximum 2–3 bold terms per H2 section.
  Bold only: genuine technical terms, proper nouns of key tools/products.
  Never bold: adjectives, general nouns, mid-sentence emphasis, obvious words.

H2 title rule:
  Every H2 must pass this test: "Does this title tell the reader something
  specific they couldn't have assumed before reading?"
  BANNED H2 patterns: "Why X Matters", "The Importance of X",
  "Benefits of X", "Introduction to X", "What is X?" (move to intro instead)
  GOOD H2 pattern: specific outcome + how/why/when

Data and facts rule:
  Use only facts from the research brief. Never invent statistics.
  When citing data, always name the source inline: "According to Gartner (2024)..."
  For citations, use authoritative third-party sources only (Wikipedia, IBM, Forbes,
  McKinsey, academic papers, official documentation) — never a course platform.

Course promotion rule:
  If recommending where to learn or take a course on this topic, ONLY mention
  the Al Nafi page specified in the content specifications. Never recommend any
  other course platform (Coursera, Udemy, edX, LinkedIn Learning, Pluralsight, etc.).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
APPROVED CTAs (use only from this list)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Standard CTAs:
  Enroll Now, Register Today, Explore Programs, Start Learning Today,
  Join Al Nafi International College, Book Your Consultation, Apply Now,
  View All Programs, Start Your Career Journey, Secure Your Seat,
  Claim Your Scholarship, Learn More.

Urgency CTAs (only when the offer or deadline is real):
  Enroll before the deadline, Lock your current fee,
  Limited seats available, Scholarship closing soon, Start before the next intake.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEO RULES (apply to Blog Post, Article, Pillar Page, LinkedIn Article)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - Place the primary keyword in the H1 title.
  - Place the primary keyword in the first 100 words of the body.
  - Include related keywords naturally in at least 2 H2 headings.
  - Add at least one internal link to a relevant Al Nafi program page (use the
    promoted page URL from the content specifications).
  - End with a clear CTA from the approved list above.
  - Every piece must include student outcome or career relevance.
  - Never keyword-stuff. Keywords must flow naturally in context.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STORYTELLING STRUCTURE (mandatory for every piece)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Every article must be structured around three narrative pillars, in this order:

  a. THE PROBLEM STATEMENT
     Open by naming the specific pain, gap, or challenge the reader faces.
     Make it concrete — not "many people struggle with X" but the exact
     situation that brought them to this article. This is the hook.

  b. THE SOLUTION
     Walk through the answer clearly and specifically. Use headings, examples,
     and data from the research brief. The solution sections form the main body.

  c. WHERE TO GET THE SOLUTION
     End with a dedicated ## Where to Start section that tells the reader
     exactly where to go next. This section MUST promote ONLY the page
     specified under "Page to Promote" in the content specifications (name,
     URL, platform, and what the reader will find there). Write it as a
     natural recommendation, not an ad. Never link to competing platforms.

SOCIAL MEDIA RULE:
  At the very end of the article (after the CTA), add a ## Connect With Us
  section containing clickable social media logo links for Al-Nafi in this
  exact format (use real markdown image-links so the logos are clickable):

  [![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/company/al-nafi/)
  [![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@AlNafiOfficial)
  [![Facebook](https://img.shields.io/badge/Facebook-1877F2?style=for-the-badge&logo=facebook&logoColor=white)](https://www.facebook.com/AlNafiOfficial)
  [![Instagram](https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/alnafiofficial/)
  [![Twitter/X](https://img.shields.io/badge/X-000000?style=for-the-badge&logo=x&logoColor=white)](https://twitter.com/AlNafiOfficial)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTENT TYPE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blog Post (900–1500 words):
  - Keyword-focused title (primary keyword in H1)
  - Short introduction: primary keyword in first 100 words, hook in first 2 sentences
  - 5–6 H2 sections with related keywords in headings
  - Practical examples in every section
  - Career relevance woven throughout
  - Program recommendation linking to the promoted Al Nafi page
  - End with an approved CTA from the list above
  - Conversational but credible — benefit-led, student-first

Article (1200–2000 words):
  - Every major claim cites a source from the research brief
  - Add ## Key Takeaways section (5–7 bullets) before ## Conclusion
  - Use > blockquote for the single most important statistic or quote
  - More formal tone — closer to journalism than blogging
  - Strong headline focused on transformation or career growth
  - Brief problem/opportunity statement, Al Nafi's solution, key benefits in bullets,
    proof points (recognized diplomas, hands-on labs, career support), clear CTA

Pillar Page (2500–3500 words):
  - ## Table of Contents is mandatory, placed after the intro paragraph
  - Each H2 section must be self-contained — a reader should understand it
    without reading the rest
  - Add ## Quick Reference or ## Cheat Sheet section near the end
  - Add ## Frequently Asked Questions with 4–6 questions from the research brief
  - Most comprehensive treatment of the topic possible
  - Multiple internal links to Al Nafi program pages throughout

LinkedIn Article (1000–1800 words):
  - Opening paragraph: 2–3 short sentences max — LinkedIn shows a preview, make every word count
  - Line break after every 2–3 sentences throughout the article — no dense walls of text
  - Use H2 headings (##) for each section — LinkedIn renders them as bold section breaks
  - Include 1 personal or professional anecdote or real-world scenario to build credibility
  - Every H2 section ends with a one-sentence takeaway the reader can act on immediately
  - Closing section: "What This Means for You" — 3–5 bullet points, direct and actionable
  - End with 1 specific question to drive comments (not "What do you think?" — make it specific)
  - Add 5–8 relevant hashtags on the final line, mix broad and niche (e.g. #ArtificialIntelligence #AIOps)
  - Tone: professional but human — first person ("I", "we") is acceptable and preferred
  - No em dashes anywhere — use commas, colons, or rewrite
  - CTA: direct the reader to the promoted page with a specific reason to click

Technical topics (any type):
  If the topic involves code, configuration, or CLI commands:
  - Include at least one working code/config example (10–20 lines)
  - Use correct language identifier in code blocks: ```yaml, ```python, ```bash
  - Follow every code block with 2–3 sentences explaining what it does

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Return clean Markdown only — no preamble, no meta-commentary
- First line: <!-- meta: [compelling 150–160 char meta description] -->
- Then the H1 title, then the content
- Heading hierarchy: H1 (title only) → H2 (main sections) → H3 (subsections)
- Paragraphs: 2–4 sentences max, never longer
- Vary sentence length deliberately for rhythm""",
    ),
    (
        "human",
        """RESEARCH BRIEF:
{research}

---

CONTENT SPECIFICATIONS:
- Topic:              {topic}
- Platform:           {plat_name} ({plat_domain})
- Content Type:       {content_type}
- Target Keywords:    {keywords}
- Target Audience:    {audience}
- Tone:               {tone}
- Word Count:         {word_count}
- Page to Promote:    {alnafi_promo}

Use the HOOKS & ANGLES and CONTENT GAPS from the research brief to make this
piece distinctly better than what already exists on this topic.

Follow the STORYTELLING STRUCTURE: problem statement → solution → where to get
the solution (promote the Al-Nafi page above). Add the ## Connect With Us social
media section at the very end.

After ## Connect With Us, add a final section called ## Content Design Brief
with EXACTLY this format — fill every field based on the article you just wrote:

---
## Content Design Brief

**Headline:** [One punchy headline for the blog post, max 10 words]

**Hook Line:** [Max 10 words. One punchy half-sentence or phrase — the single most arresting idea, nothing more]

**Title:** [SEO-optimized full title of the article]

**Subtitle:** [One supporting sentence that expands on the title and gives the reader a reason to continue]

**Body Text Summary:** [1 sentence only — the core argument in plain language, max 20 words]

**Visual Recommendation:** [Describe exactly what type of visual should accompany this article: e.g. "Infographic showing 5-step process", "Split comparison table", "Hero image of a person working on a laptop in a cloud environment", "Data visualization of X statistic". Be specific — not generic like "relevant image".]
---

Write the complete content in Markdown now.""",
    ),
])

writer_chain = writer_prompt | llm


# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 2b — SOCIAL MEDIA CAPTIONS WRITER
#  Separate prompt for social posts — no research stage needed, runs directly.
# ══════════════════════════════════════════════════════════════════════════════

SOCIAL_PLATFORM_RULES = {
    "LinkedIn": (
        "150–250 words. "
        "Line break after every 1–2 sentences — no dense paragraphs. "
        "Strong standalone first line (no opener banned phrases). "
        "Use 3–5 relevant hashtags at the end on a new line. "
        "End with a question or direct CTA that drives comments or profile visits."
    ),
    "Instagram": (
        "80–150 words caption + 10–15 hashtags on a separate line. "
        "First sentence must be the hook — Instagram shows only the first line before 'more'. "
        "Conversational and visual — write as if describing what's in the image. "
        "Include 1 clear CTA (e.g. 'Link in bio', 'DM us', 'Save this post'). "
        "Hashtags: mix high-volume and niche-specific tags."
    ),
    "Twitter/X": (
        "Maximum 260 characters per tweet. "
        "If thread, write 4–6 connected tweets numbered 1/, 2/, etc. "
        "Punchy, no filler words. "
        "1–2 hashtags max — only if they add reach, not for decoration."
    ),
    "Facebook": (
        "100–200 words. "
        "More conversational than LinkedIn — write like talking to a community. "
        "Ask a question to drive comments. "
        "Include 1 link CTA naturally within the text, not just at the end. "
        "2–3 hashtags max."
    ),
}

SOCIAL_POST_TYPES = {
    "1": "Educational / How-To",
    "2": "Promotional / Enrollment CTA",
    "3": "Engagement / Question Post",
    "4": "Announcement / News",
    "5": "Testimonial / Social Proof",
    "6": "Behind the Scenes",
}

social_caption_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a professional social media copywriter for Al Nafi International College.
You write platform-native content that feels organic, student-first, and career-focused.

BRAND VOICE: Professional, motivational, future-focused, encouraging, and student-first.
Position Al Nafi as a trusted online learning platform for job-ready skills in emerging tech.

CAPTION LENGTH (from official guidelines):
  Social media captions: 80–180 words per platform caption.

APPROVED CTAs (use only these):
  Standard: Enroll Now, Register Today, Explore Programs, Start Learning Today,
  Join Al Nafi International College, Book Your Consultation, Apply Now,
  View All Programs, Start Your Career Journey, Secure Your Seat,
  Claim Your Scholarship, Learn More.
  Urgency (only when real): Enroll before the deadline, Lock your current fee,
  Limited seats available, Scholarship closing soon, Start before the next intake.

SOCIAL STRUCTURE (for every caption):
  1. Short hook (first line — must stand alone before "see more")
  2. Benefit-driven body copy
  3. Checkmark-style highlights where applicable (use checkmark emoji sparingly)
  4. Urgency or limited-time offer only if real
  5. One approved CTA

BANNED — NEVER USE:
  - Em dash (—): use comma or colon instead
  - "In today's world...", "Have you ever wondered...", "It's no secret..."
  - Generic CTAs without specifics ("Click the link", "Learn more" alone)
  - Hashtags too broad to be useful (#life, #good, #tech)
  - "Guaranteed job", "Guaranteed visa", "Guaranteed admission"
  - "100% success guaranteed", "Instant career transformation"
  - "Cheap education", fake urgency or misleading countdowns
  - Unverified salary claims, overpromising immigration outcomes
  - Negative comparisons with competitors
  - Excessive exclamation marks (maximum one per caption)

GRAMMAR RULES:
  - "Cyber Security" (two words), "job-ready" (hyphenated)
  - Capitalize official program names and diploma names
  - "Al Nafi International College" in formal content; "Al Nafi" in short copy
  - Emojis sparingly: checkmarks (✅), alerts (🔔), graduation (🎓) only
  - Never mention competing platforms (Coursera, Udemy, edX, LinkedIn Learning, etc.)
  - Always use the exact promoted page URL — never generic alnafi.com""",
    ),
    (
        "human",
        """Write social media captions for the following brief.

TOPIC: {topic}
PLATFORM: {plat_name} ({plat_domain})
POST TYPE: {post_type}
TARGET AUDIENCE: {audience}
KEYWORDS: {keywords}
PAGE TO PROMOTE: {alnafi_promo}

PLATFORMS TO WRITE FOR:
{platforms_list}

For EACH platform listed above, write a separate caption following its specific
rules. Label each section clearly with the platform name as a heading (e.g. ## LinkedIn).

Platform-specific rules:
{platform_rules}

Write all captions now.""",
    ),
])

social_caption_chain = social_caption_prompt | llm


# ══════════════════════════════════════════════════════════════════════════════
#  STAGE 3 — REFINEMENT
#  Senior editor pass. Audits the draft against an 12-point checklist and
#  rewrites the full article. This is what pushes 8.5/10 to 9.5/10.
# ══════════════════════════════════════════════════════════════════════════════

refinement_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are the senior editor at a top digital publication.
A writer has submitted a draft. Your job is to audit it against the quality criteria
below and rewrite the COMPLETE article fixing every issue found.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
16-POINT EDITORIAL CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. OPENER QUALITY
   Does the opening line hook the reader within 2 sentences?
   If it uses any of these patterns — rewrite it completely:
   "If you're a [role]..." / "In today's world..." / "Have you ever wondered..."
   / "Whether you're X or Y..." / "It's no secret..."
   Replace with: surprising stat + interpretation, specific scenario,
   or direct challenge to a common assumption.

2. STAT INTERPRETATION
   Find every bare statistic in the draft.
   Each one must be followed immediately by a practical "so what" sentence.
   If any stat stands alone without interpretation — add it.

3. BOLD OVERUSE
   Count bold usage per H2 section. If more than 3 bolded terms exist in any
   section, strip the least essential ones. Bold is for key technical terms only —
   never for adjectives, general nouns, or mid-sentence emphasis.

4. H2 TITLE QUALITY
   Read every H2. Replace any that matches these banned patterns:
   "Why X Matters", "The Importance of X", "Benefits of X", "Introduction to X"
   Rewrite to be specific and benefit-led — tell the reader an outcome, not a topic.

5. CODE / CONCRETE EXAMPLES (applies to technical topics)
   If the topic involves tools, code, or configuration AND no code block exists —
   add one working example (10–20 lines, correct language identifier).
   Add 2–3 explanatory sentences after it.

6. COMPARISON CALLOUT (add if missing and relevant)
   If the topic has widely-known alternatives, add a brief comparison section.
   Keep it tight: a small table or 3–4 bullet points, under 150 words total.

7. LEARNING PATH (applies when audience is students or learners)
   If the audience is learning-oriented and no "where to start" section exists,
   add: ## Your First 30 Days: A Learning Path
   4–6 concrete steps with specific free resources (not generic "read the docs").

8. CTA SPECIFICITY
   The call-to-action must name ONE specific first action.
   Replace generic CTAs ("get started", "learn more", "explore today") with
   something concrete: "Run your first Azure Pipeline in 20 minutes using
   Microsoft Learn's free sandbox — search 'Azure Pipelines quickstart'."

9. LINKEDIN ARTICLE FORMAT (applies only when content type is "LinkedIn Article")
   - Verify no paragraph exceeds 3 sentences before a line break
   - Verify the article ends with a specific question (not generic) + 5–8 hashtags
   - Verify a "What This Means for You" section exists with 3–5 bullet points
   - Verify the CTA links to the exact promoted page URL, not a generic homepage

10. EM DASH REMOVAL
   Scan the entire article for the em dash character (—). Replace every instance:
   - Use a comma, colon, or semicolon where the em dash separates clauses.
   - Rewrite the sentence if no punctuation substitute fits naturally.
   Zero em dashes allowed in the final output.

10. STORYTELLING STRUCTURE
    Verify the article follows the three-pillar narrative:
    a. Problem statement — opens with a concrete, specific reader pain or gap.
    b. Solution — the main body solves it with data, examples, and headings.
    c. Where to get the solution — a ## Where to Start section at the end that
       promotes ONLY the page specified under "PAGE TO PROMOTE" in the content specs
       (name + URL from the given platform). If this section is missing or promotes
       any other platform or competitor, rewrite it.

11. SOCIAL MEDIA SECTION
    The article must end with ## Connect With Us containing these five clickable
    badge links (add them if missing, do not alter the URLs):
    [![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/company/al-nafi/)
    [![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@AlNafiOfficial)
    [![Facebook](https://img.shields.io/badge/Facebook-1877F2?style=for-the-badge&logo=facebook&logoColor=white)](https://www.facebook.com/AlNafiOfficial)
    [![Instagram](https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/alnafiofficial/)
    [![Twitter/X](https://img.shields.io/badge/X-000000?style=for-the-badge&logo=x&logoColor=white)](https://twitter.com/AlNafiOfficial)

12. CITATION & COURSE PROMOTION RULES (enforce in every rewrite)
   - Citations: use only authoritative third-party sources (Wikipedia, IBM, Forbes,
     McKinsey, Gartner, academic institutions, official docs). Never cite a course
     platform as an information source.
   - Promotion: any learning resource, CTA, or "where to go" recommendation must
     ONLY reference the page and platform specified in the content specs.
     Remove or replace any mention of Coursera, Udemy, edX, LinkedIn Learning,
     Pluralsight, Simplilearn, or any competing platform.

14. BRAND VOICE COMPLIANCE
    The tone must be professional, motivational, future-focused, and student-first.
    - Confident but not exaggerated.
    - Career-focused and outcome-driven.
    - Encouraging and practical — never condescending.
    - If the draft sounds generic or corporate, rewrite with Al Nafi brand phrases
      where they fit naturally: "Build your future with Al Nafi", "Learn today. Lead
      tomorrow.", "Become job-ready with practical skills.", etc.

15. LEGAL AND CLAIMS COMPLIANCE
    Scan for and remove any of these banned claims:
    "Guaranteed job", "Guaranteed visa", "Guaranteed admission",
    "Globally accepted everywhere", "100% success guaranteed",
    "Instant career transformation", "Become an expert overnight",
    "No effort required", "Cheap education", fake urgency, unverified salary claims,
    overpromising immigration outcomes, negative competitor comparisons.
    Replace with: "job placement assistance", "career support",
    "recognized pathways", "career-focused training".

16. GRAMMAR AND TERMINOLOGY COMPLIANCE
    - "Cyber Security" must be two words (not Cybersecurity).
    - "job-ready" must be hyphenated.
    - Capitalize all official program names, diploma names, and partner names.
    - "Al Nafi International College" in formal sections; "Al Nafi" in promotional copy.
    - Maximum one exclamation mark in the whole article.
    - "Pearson BTEC Approved" only if the specific promoted program is Pearson-approved.
    - "EduQual UK Endorsed" only if the specific promoted program is EduQual-endorsed.
    - All CTAs must come from the approved list: Enroll Now, Register Today,
      Explore Programs, Start Learning Today, Apply Now, View All Programs,
      Start Your Career Journey, Secure Your Seat, Claim Your Scholarship, Learn More.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Return ONLY the complete rewritten article in Markdown
- Keep the <!-- meta: ... --> line at the top, improve it if weak
- No commentary before or after — just the article
- Do not summarise what you changed
- The rewrite must be complete — not a partial edit with placeholders
- The final section MUST always be ## Content Design Brief in this exact format:

---
## Content Design Brief

**Headline:** [One punchy headline, max 10 words]

**Hook Line:** [Max 10 words. One punchy half-sentence or phrase — the single most arresting idea, nothing more]

**Title:** [SEO-optimized full title]

**Subtitle:** [One sentence expanding on the title, giving the reader a reason to continue]

**Body Text Summary:** [1 sentence only — the core argument in plain language, max 20 words]

**Visual Recommendation:** [Specific visual type: e.g. "Infographic showing 5-step process", "Split comparison table", "Hero image of a developer working in a cloud lab", "Data visualization of X statistic". Never generic.]
---

If the draft already has a ## Content Design Brief, review and improve every field. If it is missing, write it from scratch.""",
    ),
    (
        "human",
        """DRAFT TO ELEVATE:
{draft}

---
TARGET AUDIENCE:   {audience}
PLATFORM:          {plat_name} ({plat_domain})
CONTENT TYPE:      {content_type}
KEYWORDS:          {keywords}
PAGE TO PROMOTE:   {alnafi_promo}

Audit against all 16 criteria. Rewrite the complete article now.""",
    ),
])

refinement_chain = refinement_prompt | llm


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

ALNAFI_PAGES = {
    # ── General ────────────────────────────────────────────────────────────────
    "1":  ("Al Nafi Home",                           "https://alnafi.com/",                                                                       "Main landing: 140+ programs, 50,000+ graduates, Pearson BTEC & EduQual accreditation, G20-recognized, 95% job placement rate."),
    "2":  ("All Courses",                            "https://alnafi.com/courses",                                                                "Full catalogue: EduQual Diplomas, Short Courses, ISACA Exam Prep, Micro Credentials, Learning Paths."),
    "3":  ("Pathways Overview",                      "https://alnafi.com/pathways",                                                               "7+1 Dual Diploma Learning Path: study at Al Nafi, then progress to 270+ international universities."),
    "4":  ("EduQual Pathways",                       "https://alnafi.com/eduqual-pathways",                                                       "EduQual-accredited diploma progression pathways in tech and business."),
    "5":  ("Pearson Pathway",                        "https://alnafi.com/pearson-pathway",                                                        "Pearson BTEC-accredited pathway leading to international universities."),
    "6":  ("Micro Credentials",                      "https://alnafi.com/micro-credentials",                                                      "33+ frontier-tech micro credentials with hands-on Cloud Labs across 9 verticals."),
    "7":  ("SEI Program",                            "https://alnafi.com/sei",                                                                    "Studies + Employment + Immigration: 100% job placement guarantee, zero-fee visa support for Canada/UK/Australia."),
    "8":  ("SEI Application Form",                   "https://alnafi.com/sei-form/",                                                              "Direct enrollment form for the SEI (Studies, Employment, Immigration) program."),
    "9":  ("Pit Stop Program",                       "https://alnafi.com/pitstop-program",                                                        "Structured portfolio-building: labs and projects auto-published to LinkedIn, YouTube, GitHub."),
    "10": ("Al Nafi Cloud Labs",                     "https://alnafi.cloud/",                                                                     "Hands-on cloud lab environment with 35+ micro credentials across 9 industry verticals."),
    "11": ("FAQs",                                   "https://alnafi.com/faqs",                                                                   "Frequently asked questions about programs, fees, accreditation, and enrollment."),
    "12": ("Contact",                                "https://alnafi.com/contact",                                                                "Contact Al Nafi: Karachi office, WhatsApp, support Mon-Sat 9AM-11PM PKT."),
    "13": ("Al Nafi Group",                          "https://alnafi.com/group",                                                                  "5-platform group: Al Nafi International College, Al Nafi Cloud, Annaafi Epay, Al Nafi Islamic College, Al Nafi Academy."),
    "14": ("Invest",                                 "https://alnafi.com/invest",                                                                 "Series A investment: open campuses in 18 countries, Al Nafi manages operations."),
    "15": ("Pakistan Page",                          "https://alnafi.com/country/pk",                                                             "Pakistan-specific: compares Al Nafi vs traditional Pakistani education on cost and time."),
    "16": ("Q&A / Ask a Question",                   "https://alnafi.com/qa",                                                                     "Submit questions for live expert sessions and industry events hosted by Al Nafi."),
    "17": ("Student Portal",                         "https://portal.alnafi.com/",                                                                "Student learning portal: access courses, track progress, download certificates."),
    "18": ("Pit Stop Platform",                      "https://pitstop.alnafi.com/",                                                               "Digital identity platform: auto-publishes student achievements to professional networks."),
    # ── EduQual Diplomas ───────────────────────────────────────────────────────
    "19": ("Diploma: Cloud Cyber Security",          "https://alnafi.com/courses/diploma-in-cloud-cyber-security",                                "EduQual diploma: cloud security architecture, threat detection, and incident response."),
    "20": ("Diploma: SysOps and Cloud",              "https://alnafi.com/courses/diploma-in-sysops-and-cloud",                                    "EduQual diploma in systems operations and cloud infrastructure management."),
    "21": ("Diploma: DevOps and Cloud",              "https://alnafi.com/courses/diploma-in-devops-and-cloud",                                    "EduQual diploma: CI/CD, Jenkins, Docker, Kubernetes, and cloud deployment pipelines."),
    "22": ("Diploma: AI Operations (AIOps)",         "https://alnafi.com/courses/diploma-in-artificial-intelligence-ops",                         "EduQual Level 6 AIOps: TensorFlow, PyTorch, automation, cloud security, 2000+ projects, 3-6 months."),
    "23": ("Diploma: DevSysOps Engineering",         "https://alnafi.com/courses/diploma-in-devsysops-engineering",                               "EduQual diploma combining DevOps and SysOps for full-stack operations engineering."),
    "24": ("Diploma: Artificial Intelligence",       "https://alnafi.com/courses/diploma-in-artificial-intelligence",                             "EduQual diploma in AI: machine learning, deep learning, neural networks, real-world AI applications."),
    "25": ("Additional Labs: DevSysOps",             "https://alnafi.com/courses/additional-labs-for-devsysops-engineering",                      "Extra hands-on lab sessions for DevSysOps Engineering diploma students."),
    "26": ("Additional Labs: AIOps",                 "https://alnafi.com/courses/additional-labs-for-diploma-in-artificial-intelligence-operations","Extra hands-on lab sessions for AIOps diploma students."),
    # ── Pearson Diplomas ───────────────────────────────────────────────────────
    "27": ("Pearson: Information Technology",        "https://alnafi.com/pearson/pearson-diploma-in-information-technology",                      "Pearson BTEC diploma in Information Technology: globally recognized qualification."),
    "28": ("Pearson: Business",                      "https://alnafi.com/pearson/pearson-diploma-in-business",                                    "Pearson BTEC diploma in Business: pathways to international universities."),
    "29": ("Pearson: Computing General",             "https://alnafi.com/pearson/pearson-diploma-in-computing-general",                           "Pearson BTEC diploma in Computing (General): foundational computing and software skills."),
    "30": ("Pearson: Digital Technologies",          "https://alnafi.com/pearson/pearson-diploma-in-digital-technologies",                        "Pearson BTEC diploma in Digital Technologies: modern tech skills for the digital economy."),
    "31": ("Pearson: Business Management",           "https://alnafi.com/pearson/pearson-diploma-in-business-management",                         "Pearson BTEC diploma in Business Management: leadership, strategy, organizational management."),
    # ── Dual Diplomas ──────────────────────────────────────────────────────────
    "32": ("Dual Diploma: HND Computing + AIOps",    "https://alnafi.com/dual-diploma/higher-national-in-computing-and-ai-operations",            "Two globally recognized qualifications: HND Computing combined with AI Operations."),
    "33": ("Dual Diploma: HND Digital Tech + AIOps", "https://alnafi.com/dual-diploma/higher-national-in-digital-technologies-and-ai-operations",  "Dual diploma: HND Digital Technologies combined with AI Operations."),
    "34": ("Dual Diploma: HND Business + AIOps",     "https://alnafi.com/dual-diploma/higher-national-in-business-and-ai-operations",             "Dual diploma: HND Business combined with AI Operations."),
    "35": ("Dual Diploma: IT + Cloud + HND Comp + AIOps",   "https://alnafi.com/dual-diploma/information-technology-cloud-cyber-security-hnd-computing-and-ai-operations",            "Comprehensive quad diploma: IT, Cloud Cyber Security, HND Computing, and AIOps."),
    "36": ("Dual Diploma: IT + Cloud + HND Digital + AIOps", "https://alnafi.com/dual-diploma/information-technology-cloud-cyber-security-hnd-digital-technologies-and-ai-operations", "Comprehensive quad diploma: IT, Cloud Cyber Security, HND Digital Technologies, and AIOps."),
    "37": ("Dual Diploma: Business + Cloud + AIOps", "https://alnafi.com/dual-diploma/business-cloud-cyber-security-and-ai-operations",           "Dual diploma: Business, Cloud Cyber Security, and AI Operations combined."),
    # ── AIOps Specializations ──────────────────────────────────────────────────
    "38": ("AIOps + Quantum Computing",              "https://alnafi.com/aiops/diploma-in-aiops-with-quantum-computing",                          "AIOps diploma with Quantum Computing specialization."),
    "39": ("AIOps + Software Specialization",        "https://alnafi.com/aiops/diploma-in-aiops-with-software-specialization",                    "AIOps diploma with Software Intelligence specialization."),
    "40": ("AIOps + Robotics",                       "https://alnafi.com/aiops/diploma-in-aiops-with-robotics",                                   "AIOps diploma with Robotics and Automation Systems specialization."),
    "41": ("AIOps + Cybersecurity",                  "https://alnafi.com/aiops/diploma-in-aiops-with-cybersecurity-specialization",               "AIOps diploma with Cybersecurity specialization."),
    "42": ("AIOps + Blockchain",                     "https://alnafi.com/aiops/diploma-in-aiops-with-blockchain-specialization",                  "AIOps diploma with Blockchain specialization."),
    "43": ("AIOps + Bioengineering",                 "https://alnafi.com/aiops/diploma-in-aiops-with-bioengineering",                             "AIOps diploma with Bioengineering specialization."),
    "44": ("AIOps + Brain-Computer Interfaces",      "https://alnafi.com/aiops/diploma-in-aiops-with-brain-computer-interfaces",                  "AIOps diploma with Brain-Computer Interfaces specialization."),
    "45": ("AIOps + Space Tech",                     "https://alnafi.com/aiops/diploma-in-aiops-with-Space-tech",                                 "AIOps diploma with Space Technology specialization."),
    "46": ("AIOps + Pharmaceuticals & Genomics",     "https://alnafi.com/aiops/diploma-in-aiops-with-pharmaceuticals-genomics",                   "AIOps diploma with Pharmaceuticals and Genomics specialization."),
    "47": ("AIOps + Supply Chain Tech",              "https://alnafi.com/aiops/diploma-in-aiops-with-supply-chain-tech",                          "AIOps diploma with Supply Chain Technology specialization."),
    "48": ("AIOps + Drone & Autonomous Systems",     "https://alnafi.com/aiops/diploma-in-aiops-with-drone-and-autonomous-systems",               "AIOps diploma with Drone and Autonomous Systems specialization."),
    "49": ("AIOps + Agricultural Biotech",           "https://alnafi.com/aiops/diploma-in-aiops-with-agricultural-biotech",                       "AIOps diploma with Agricultural Biotechnology specialization."),
    "50": ("AIOps + Nanotechnology",                 "https://alnafi.com/aiops/diploma-in-aiops-with-nanotechnology",                             "AIOps diploma with Nanotechnology specialization."),
    "51": ("AIOps + Nuclear Technologies",           "https://alnafi.com/aiops/diploma-in-aiops-with-nuclear-technologies",                       "AIOps diploma with Nuclear Technologies specialization."),
    "52": ("AIOps + Synthetic Media",                "https://alnafi.com/aiops/diploma-in-aiops-with-synthetic-media",                            "AIOps diploma with Synthetic Media specialization."),
    # ── Short Courses ──────────────────────────────────────────────────────────
    "53": ("Course: Entrepreneurship & Freelancing", "https://alnafi.com/courses/course/intro-to-entrepreneurship-and-freelancing",                "Short course on entrepreneurship fundamentals and freelancing strategies."),
    "54": ("Course: Communication Skills",           "https://alnafi.com/courses/course/communication-skills",                                    "Short course on professional communication skills for the workplace."),
    "55": ("Course: LinkedIn Masterclass",           "https://alnafi.com/courses/course/linkedin-masterclass",                                    "Short course on building a strong LinkedIn presence and personal brand."),
    "56": ("Course: Real Statistics (Gold)",         "https://alnafi.com/courses/course/real-statistics-gold",                                    "Advanced statistics course: Gold level."),
    "57": ("Course: Real Statistics (Silver)",       "https://alnafi.com/courses/course/real-statistics-silver",                                  "Statistics course: Silver level, foundational to intermediate."),
    "58": ("Course: IELTS Preparation",              "https://alnafi.com/courses/course/ielts-preparation-course",                                "IELTS exam preparation for students targeting international university admission."),
    # ── ISACA Certification Prep ───────────────────────────────────────────────
    "59": ("ISACA: CISA Exam Prep",                  "https://alnafi.com/isaca/details/CISA",                                                     "Certified Information Systems Auditor (CISA) exam preparation bundle."),
    "60": ("ISACA: CISM Exam Prep",                  "https://alnafi.com/isaca/details/CISM",                                                     "Certified Information Security Manager (CISM) exam preparation bundle."),
    "61": ("ISACA: CRISC Exam Prep",                 "https://alnafi.com/isaca/details/CRISC",                                                    "Certified in Risk and Information Systems Control (CRISC) exam preparation bundle."),
    "62": ("ISACA: CDPSE Exam Prep",                 "https://alnafi.com/isaca/details/CDPSE",                                                    "Certified Data Privacy Solutions Engineer (CDPSE) exam preparation bundle."),
    "63": ("ISACA: CGEIT Exam Prep",                 "https://alnafi.com/isaca/details/CGEIT",                                                    "Certified in the Governance of Enterprise IT (CGEIT) exam preparation bundle."),
    # ── Micro Credentials ──────────────────────────────────────────────────────
    "64": ("Micro: Cyber Security",                  "https://alnafi.com/micro-credentials/cyber-security",                                       "Micro credential in Cybersecurity: threat detection, defense, security operations."),
    "65": ("Micro: Blockchain",                      "https://alnafi.com/micro-credentials/blockchain-specialization",                            "Micro credential in Blockchain technology and decentralized applications."),
    "66": ("Micro: Brain-Computer Interfaces",       "https://alnafi.com/micro-credentials/brain-computer-interfaces",                            "Micro credential in Brain-Computer Interface technology."),
    "67": ("Micro: Robotics & Automation",           "https://alnafi.com/micro-credentials/major-specialization-in-robotics-and-automation-systems","Micro credential in Robotics and Automation Systems."),
    "68": ("Micro: Drone & Autonomous Systems",      "https://alnafi.com/micro-credentials/major-specialization-in-drone-and-autonomous-systems",  "Micro credential in Drone and Autonomous Systems."),
    "69": ("Micro: Quantum Computing",               "https://alnafi.com/micro-credentials/quantum-computing-specialization",                     "Micro credential in Quantum Computing."),
    "70": ("Micro: Pharmaceuticals & Genomics",      "https://alnafi.com/micro-credentials/pharmaceuticals-and-genomics",                         "Micro credential in Pharmaceuticals and Genomics."),
    "71": ("Micro: Nanotechnology",                  "https://alnafi.com/micro-credentials/nanotechnology-specialization",                        "Micro credential in Nanotechnology."),
    "72": ("Micro: Agricultural Biotech",            "https://alnafi.com/micro-credentials/agricultural-biotech",                                 "Micro credential in Agricultural Biotechnology."),
    "73": ("Micro: Supply Chain Tech",               "https://alnafi.com/micro-credentials/supply-chain-tech",                                    "Micro credential in Supply Chain Technology."),
    "74": ("Micro: Bioengineering",                  "https://alnafi.com/micro-credentials/bioengineering",                                       "Micro credential in Bioengineering."),
    "75": ("Micro: Nuclear Technologies",            "https://alnafi.com/micro-credentials/nuclear-technologies",                                 "Micro credential in Nuclear Technologies."),
    "76": ("Micro: Software Intelligence",           "https://alnafi.com/micro-credentials/software-intelligence-specialization",                  "Micro credential in Software Intelligence."),
    "77": ("Micro: Synthetic Media",                 "https://alnafi.com/micro-credentials/synthetic-media",                                      "Micro credential in Synthetic Media: AI-generated content and creative AI."),
    "78": ("Micro: Space Tech",                      "https://alnafi.com/micro-credentials/space-tech",                                           "Micro credential in Space Technology."),
    "79": ("Micro: AI & Machine Learning",           "https://alnafi.com/micro-credentials/artificial-intelligence-and-machine-learning-specialization","Micro credential in Artificial Intelligence and Machine Learning."),
    "80": ("Micro: Cloud & Big Data",                "https://alnafi.com/micro-credentials/cloud-big-data",                                       "Micro credential in Cloud Computing and Big Data."),
    "81": ("Micro: 5G/6G Communication",             "https://alnafi.com/micro-credentials/5g6g-communication",                                   "Micro credential in 5G and 6G Communication Technologies."),
    "82": ("Micro: Desalination & Water Tech",       "https://alnafi.com/micro-credentials/desalination-and-water-technology",                    "Micro credential in Desalination and Water Technology."),
    "83": ("Micro: Data Science",                    "https://alnafi.com/micro-credentials/data-science",                                         "Micro credential in Data Science."),
    "84": ("Micro: Digital Infrastructure",          "https://alnafi.com/micro-credentials/digital-infrastructure-platforms",                     "Micro credential in Digital Infrastructure Platforms."),
    "85": ("Micro: Green Jobs & Sustainability",     "https://alnafi.com/micro-credentials/green-jobs-and-sustainability-tech",                   "Micro credential in Green Jobs and Sustainability Technology."),
    "86": ("Micro: Synthetic Biology",               "https://alnafi.com/micro-credentials/synthetic-biology",                                    "Micro credential in Synthetic Biology."),
    "87": ("Micro: Healthcare & Remote Health Tech", "https://alnafi.com/micro-credentials/healthcare-and-remote-health-tech",                    "Micro credential in Healthcare and Remote Health Technology."),
    "88": ("Micro: E-Commerce & Digital Trade",      "https://alnafi.com/micro-credentials/e-commerce-and-digital-trade",                         "Micro credential in E-Commerce and Digital Trade."),
    "89": ("Micro: Financial Technologies",          "https://alnafi.com/micro-credentials/financial-technologies",                               "Micro credential in Financial Technologies (FinTech)."),
    "90": ("Micro: High Frequency Finance",          "https://alnafi.com/micro-credentials/high-frequency-finance",                               "Micro credential in High Frequency Finance."),
    "91": ("Micro: Creative & Digital Content",      "https://alnafi.com/micro-credentials/creative-and-digital-content-industries",              "Micro credential in Creative and Digital Content Industries."),
    "92": ("Micro: Transportation & Smart Mobility", "https://alnafi.com/micro-credentials/transportation-and-smart-mobility",                    "Micro credential in Transportation and Smart Mobility."),
}

EPAY_PAGES = {
    "1": ("ePay Home",        "https://epay.com.pk/",                  "Annaafi ePay: digital payment platform for organizations — invoicing, transactions, and financial management."),
    "2": ("Invoicing",        "http://epay.com.pk/invoicing",          "ePay invoicing solution: create, send, and track invoices digitally for businesses and institutions."),
    "3": ("Solutions",        "https://epay.com.pk/solutions",         "ePay product suite: full range of digital payment and financial management solutions."),
    "4": ("Our Leadership",   "https://epay.com.pk/our-leadership",    "Meet the leadership team behind ePay's fintech platform."),
    "5": ("About Us",         "https://epay.com.pk/about-us",          "About Annaafi ePay: mission, vision, and background of the fintech platform."),
    "6": ("Contact",          "https://epay.com.pk/contact",           "Contact ePay for sales, support, or partnership inquiries."),
}

ACADEMY_PAGES = {
    "1":  ("Academy Home",         "https://alnafi.academy/",                           "Al Nafi Academy: online academic support for school students — O Level, IGCSE, AKU, and foundation studies."),
    "2":  ("About Us",             "https://alnafi.academy/about-us",                   "About Al Nafi Academy: mission and approach to school-level online education."),
    "3":  ("O Level",              "https://alnafi.academy/o-level",                    "O Level program at Al Nafi Academy: subjects, syllabus, and online learning support."),
    "4":  ("O Levels Coaching",    "https://alnafi.academy/olevels-coaching",           "Live coaching sessions and tutoring for O Level students."),
    "5":  ("Foundation Course",    "https://alnafi.academy/foundation-course",          "Foundation course for students preparing to enter O Level or secondary education."),
    "6":  ("AKU Program",          "https://alnafi.academy/landing-pages/aku",          "AKU (Aga Khan University) board preparation program at Al Nafi Academy."),
    "7":  ("Faculty",              "https://alnafi.academy/faculty",                    "Meet the teachers and academic staff at Al Nafi Academy."),
    "8":  ("Student Schedule",     "https://alnafi.academy/student-schedule",           "Class timetable and session schedule for Al Nafi Academy students."),
    "9":  ("Math Block",           "https://alnafi.academy/math-block",                 "Dedicated mathematics support program for students struggling with maths."),
    "10": ("Student Resources",    "https://alnafi.academy/student-resources",          "Study materials, past papers, and learning resources for Al Nafi Academy students."),
    "11": ("Fees",                 "https://alnafi.academy/fees",                       "Fee structure and payment plans for Al Nafi Academy programs."),
}

ISLAMIC_PAGES = {
    "1": ("Islamic College Home",  "https://islamic.alnafi.com/",                       "Al Nafi Islamic College: values-based Islamic education combined with modern academic and professional development."),
    "2": ("About Us",              "https://islamic.alnafi.com/about-us",               "About Al Nafi Islamic College: mission, values, and educational philosophy."),
    "3": ("Next Gen Scholar",      "https://islamic.alnafi.com/next-gen-scholar",       "Next Gen Scholar program: developing the next generation of Islamic scholars with modern knowledge."),
    "4": ("Al Razzaq Program",     "https://islamic.alnafi.com/al-razzaq",              "Al Razzaq employment and career support program for Islamic College students."),
    "5": ("Learning Path",         "https://islamic.alnafi.com/learning-path",          "Structured learning path through Islamic studies programs at Al Nafi Islamic College."),
    "6": ("Support",               "https://islamic.alnafi.com/support",                "Student support and contact for Al Nafi Islamic College."),
}

CLOUD_PAGES = {
    "1": ("Cloud Labs Home",       "https://alnafi.cloud/",                                                             "Al Nafi Cloud: hands-on lab environment with 35+ micro credentials across 9 industry verticals."),
    "2": ("Learning Paths",        "https://alnafi.cloud/learning-paths",                                               "Structured learning paths through Al Nafi Cloud micro credentials and lab programs."),
    "3": ("Micro: Quantum Computing","https://alnafi.cloud/micro-credentials/quantum-computing-specialization",         "Hands-on Quantum Computing micro credential with live cloud lab access."),
    "4": ("Micro: Robotics & Automation","https://alnafi.cloud/micro-credentials/major-specialization-in-robotics-and-automation-systems","Hands-on Robotics and Automation Systems micro credential with live cloud labs."),
    "5": ("Micro: Cloud & Big Data","https://alnafi.cloud/micro-credentials/cloud-big-data",                            "Hands-on Cloud Computing and Big Data micro credential with live lab environment."),
    "6": ("Micro: Cyber Security",  "https://alnafi.cloud/micro-credentials/cyber-security",                           "Hands-on Cybersecurity micro credential with live cloud lab environment."),
}

PLATFORMS = {
    "1": ("Al Nafi International College", "alnafi.com",     ALNAFI_PAGES,  "22"),
    "2": ("Annaafi ePay",                  "epay.com.pk",    EPAY_PAGES,    "1"),
    "3": ("Al Nafi Academy",               "alnafi.academy", ACADEMY_PAGES, "1"),
    "4": ("Al Nafi Islamic College",       "islamic.alnafi.com", ISLAMIC_PAGES, "1"),
    "5": ("Al Nafi Cloud",                 "alnafi.cloud",   CLOUD_PAGES,   "1"),
}

CONTENT_TYPES = {
    "1": ("Blog Post",             "900–1500 words"),
    "2": ("Article",               "1200–2000 words"),
    "3": ("Pillar Page",           "2500–3500 words"),
    "4": ("Social Media Captions", "platform-specific"),
    "5": ("LinkedIn Article",      "1000–1800 words"),
}

TONES = {
    "1": "Professional",
    "2": "Conversational",
    "3": "Educational",
    "4": "Persuasive",
}

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:50]

def save_output(topic: str, content: str) -> str:
    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"outputs/{slugify(topic)}_{timestamp}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return filename


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def _pick(prompt, options, default):
    """Print a numbered menu and return the chosen value."""
    for k, v in options.items():
        marker = " (default)" if k == default else ""
        print(f"    {k}.  {v}{marker}")
    choice = input(f"  {prompt} [{default}]: ").strip() or default
    return options.get(choice, options[default])


def _show_history():
    rows = _db.list_recent(15)
    if not rows:
        print("  (no previous generations)")
        return
    print(f"\n  {'ID':<5} {'Date':<20} {'Type':<22} {'Platform':<30} Topic")
    print("  " + "-" * 100)
    for r in rows:
        print(f"  {r['id']:<5} {r['created_at']:<20} {r['content_type']:<22} {r['platform']:<30} {r['topic']}")


def main():
    print("\n" + "=" * 60)
    print("         CONTENT GENERATION AGENT  v4")
    print("=" * 60)

    # ── History / DB lookup ────────────────────────────
    print("\n  Options:")
    print("    N  →  Generate new content")
    print("    H  →  Browse history")
    print("    R  →  Retrieve by ID")
    mode = input("  Choose [N]: ").strip().upper() or "N"

    if mode == "H":
        _show_history()
        return

    if mode == "R":
        row_id = input("  Enter ID to retrieve: ").strip()
        row = _db.get_generation(int(row_id)) if row_id.isdigit() else None
        if row:
            print(f"\n  Topic:    {row['topic']}")
            print(f"  Platform: {row['platform']}")
            print(f"  Type:     {row['content_type']}")
            print(f"  Created:  {row['created_at']}")
            print(f"  File:     {row['filepath']}\n")
            print(row['final_content'][:800])
            print("\n  ... [full content in DB field 'final_content'] ...\n")
        else:
            print("  ✗  Record not found.")
        return

    # ── Collect inputs ─────────────────────────────────
    topic    = input("\n  Topic: ").strip()
    keywords = input("  Target keywords (comma-separated): ").strip()
    audience = input("  Target audience [general readers]: ").strip() or "general readers"

    # ── Check DB for existing content on same topic ────
    existing = _db.search_generations(topic=topic, limit=5)
    if existing:
        print(f"\n  Found {len(existing)} existing generation(s) for this topic:")
        for r in existing:
            print(f"    [{r['id']}] {r['created_at']}  {r['content_type']}  ({r['platform']})")
        reuse = input("  Load one? Enter ID or press Enter to generate fresh: ").strip()
        if reuse.isdigit():
            row = _db.get_generation(int(reuse))
            if row:
                print(f"\n  Loaded from DB (ID {row['id']}, {row['created_at']})")
                print(f"  File: {row['filepath']}\n")
                print(row['final_content'][:800])
                print("\n  ... [full content in file above] ...\n")
                return

    print("\n  Content Type:")
    for k, (name, wc) in CONTENT_TYPES.items():
        print(f"    {k}.  {name:<22} ({wc})")
    ct_choice = input("  Choose (1–4) [1]: ").strip() or "1"
    content_type, word_count = CONTENT_TYPES.get(ct_choice, CONTENT_TYPES["1"])

    # ── Social Media Captions: extra questions ─────────
    social_meta = None
    chosen_platforms = []
    post_type = ""
    if content_type == "Social Media Captions":
        print("\n  Which platforms? (comma-separated numbers)")
        plat_opts = {"1": "LinkedIn", "2": "Instagram", "3": "Twitter/X", "4": "Facebook"}
        for k, v in plat_opts.items():
            print(f"    {k}.  {v}")
        plat_sel = input("  Choose (e.g. 1,2,3) [1,2,3,4]: ").strip() or "1,2,3,4"
        chosen_platforms = [plat_opts[p.strip()] for p in plat_sel.split(",") if p.strip() in plat_opts]

        print("\n  Post Type:")
        post_type = _pick("Choose", SOCIAL_POST_TYPES, "1")

        print("\n  Caption Goal:")
        goal_opts = {
            "1": "Drive enrollment / link clicks",
            "2": "Build brand awareness",
            "3": "Get comments and engagement",
            "4": "Share knowledge / educate",
        }
        caption_goal = _pick("Choose", goal_opts, "1")

        social_meta = {
            "platforms": chosen_platforms,
            "post_type": post_type,
            "goal": caption_goal,
        }

    tone = "Professional"
    if content_type != "Social Media Captions":
        print("\n  Tone:")
        for k, name in TONES.items():
            print(f"    {k}.  {name}")
        tone_choice = input("  Choose (1–4) [1]: ").strip() or "1"
        tone = TONES.get(tone_choice, "Professional")

    print("\n  Platform:")
    for k, (pname, pdomain, _, _default) in PLATFORMS.items():
        print(f"    {k}.  {pname:<38} ({pdomain})")
    plat_choice = input("  Choose (1–5) [1]: ").strip() or "1"
    plat_name, plat_domain, plat_pages, plat_default = PLATFORMS.get(plat_choice, PLATFORMS["1"])

    print(f"\n  Page to Promote  [{plat_name}]:")
    for k, (name, url, _) in plat_pages.items():
        print(f"    {k:>2}.  {name:<45} {url}")
    ap_choice = input(f"  Choose [default={plat_default}]: ").strip() or plat_default
    ap_name, ap_url, ap_desc = plat_pages.get(ap_choice, list(plat_pages.values())[0])
    alnafi_promo = f"{ap_name} ({plat_name}): {ap_url}\n    {ap_desc}"

    # ── Social Media Captions path ─────────────────────
    if content_type == "Social Media Captions":
        print(f"\n{'─' * 60}")
        print(f"  Writing captions for: {', '.join(chosen_platforms)}")
        print(f"{'─' * 60}\n")

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

        try:
            result = social_caption_chain.invoke({
                "topic":          topic,
                "plat_name":      plat_name,
                "plat_domain":    plat_domain,
                "post_type":      post_type,
                "audience":       audience,
                "keywords":       keywords,
                "alnafi_promo":   alnafi_promo,
                "platforms_list": platforms_list,
                "platform_rules": platform_rules,
            })
            content = result.content if hasattr(result, "content") else str(result)
        except Exception as e:
            print(f"\n  ✗  Caption generation failed: {e}")
            raise

        filepath = save_output(topic, content)
        _db.save_generation(
            topic=topic, platform=plat_name, page_promoted=alnafi_promo,
            content_type=content_type, audience=audience, tone="N/A",
            keywords=keywords, research_brief="N/A (social captions — no research stage)",
            writer_system=writer_system_text, writer_human=writer_human_text,
            final_content=content, filepath=filepath, social_meta=social_meta,
        )

        print("=" * 60)
        print("  ✓  Done!")
        print(f"  →  Saved to: {filepath}")
        print("=" * 60)
        print("\n  ── PREVIEW ───────────────────────────────────────\n")
        print(content[:800])
        print("\n  ... [full content in file above] ...\n")
        return

    # ── Stage 1: Research ──────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  [1/3]  Researching → {topic}")
    print(f"{'─' * 60}\n")

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
    except Exception as e:
        print(f"\n  ⚠  Research error: {e}")
        print("  Proceeding with minimal context...\n")
        research_text = f"Topic: {topic}. Keywords: {keywords}."

    # ── Stage 2: Write ─────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  [2/3]  Writing {content_type}...")
    print(f"{'─' * 60}\n")

    writer_system_text = writer_prompt.messages[0].prompt.template
    writer_human_text = (
        f"TOPIC: {topic} | PLATFORM: {plat_name} | TYPE: {content_type} | "
        f"AUDIENCE: {audience} | KEYWORDS: {keywords} | PAGE: {alnafi_promo}"
    )

    try:
        write_result = writer_chain.invoke({
            "research":     research_text,
            "topic":        topic,
            "plat_name":    plat_name,
            "plat_domain":  plat_domain,
            "content_type": content_type,
            "keywords":     keywords,
            "audience":     audience,
            "tone":         tone,
            "word_count":   word_count,
            "alnafi_promo": alnafi_promo,
        })
        draft = write_result.content if hasattr(write_result, "content") else str(write_result)
    except Exception as e:
        print(f"\n  ✗  Writing failed: {e}")
        raise

    # ── Stage 3: Refine ────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  [3/3]  Refining and elevating...")
    print(f"{'─' * 60}\n")

    try:
        refined_result = refinement_chain.invoke({
            "draft":        draft,
            "audience":     audience,
            "plat_name":    plat_name,
            "plat_domain":  plat_domain,
            "content_type": content_type,
            "keywords":     keywords,
            "alnafi_promo": alnafi_promo,
        })
        content = refined_result.content if hasattr(refined_result, "content") else str(refined_result)
    except Exception as e:
        print(f"\n  ⚠  Refinement failed — saving draft instead: {e}")
        content = draft

    filepath = save_output(topic, content)

    _db.save_generation(
        topic=topic, platform=plat_name, page_promoted=alnafi_promo,
        content_type=content_type, audience=audience, tone=tone,
        keywords=keywords, research_brief=research_text,
        writer_system=writer_system_text, writer_human=writer_human_text,
        final_content=content, filepath=filepath,
    )

    print("=" * 60)
    print("  ✓  Done!")
    print(f"  →  Saved to: {filepath}")
    print("=" * 60)
    print("\n  ── PREVIEW ───────────────────────────────────────\n")
    print(content[:600])
    print("\n  ... [full content in file above] ...\n")


if __name__ == "__main__":
    main()