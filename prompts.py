"""Prompt templates for Researcher and Synthesiser roles."""


RESEARCHER_SYSTEM = """\
You are a meticulous research assistant. Your job is to evaluate a web source, \
summarise it accurately, and extract the information most relevant to a given \
research topic. Be concise but thorough. Never fabricate facts or invent citations.\
"""


def researcher_prompt(topic: str, source_text: str, source_url: str,
                      source_title: str, existing_notes_summary: str) -> str:
    return f"""\
RESEARCH TOPIC:
{topic}

WHAT HAS ALREADY BEEN COLLECTED (brief overview):
{existing_notes_summary or "Nothing yet — this is the first source."}

SOURCE URL: {source_url}
SOURCE TITLE: {source_title}

SOURCE TEXT (may be truncated):
---
{source_text}
---

Your tasks:
1. Write a concise SUMMARY of this source (3–6 sentences).
2. Write a DETAILED_SUMMARY covering the main arguments, data, or findings (up to 200 words).
3. Explain WHY_RELEVANT: how does this source contribute to the research topic?
4. List KEY_POINTS as a numbered list (up to 8 points).
5. Assign a QUALITY_SCORE from 1–10 (10 = authoritative, well-sourced, rich content).
6. Assign a RELEVANCE_SCORE from 1–10 (10 = directly and substantially about the topic).

Respond ONLY in this exact format (no extra text before or after):

SUMMARY:
<your summary>

DETAILED_SUMMARY:
<your detailed summary>

WHY_RELEVANT:
<explanation>

KEY_POINTS:
1. <point>
2. <point>
...

QUALITY_SCORE: <integer 1-10>
RELEVANCE_SCORE: <integer 1-10>
"""


SYNTHESISER_SYSTEM = """\
You are a senior research synthesiser. Your job is to read accumulated research \
notes and produce a clear, well-structured, progressively improving draft report. \
You integrate evidence, highlight tensions, identify what is still unknown, and \
propose the most valuable next research directions. Write in plain academic prose.\
"""


def synthesiser_prompt(topic: str, all_summaries: str, current_draft: str,
                       cycle: int) -> str:
    return f"""\
RESEARCH TOPIC:
{topic}

CYCLE: {cycle}

ALL RESEARCH NOTES COLLECTED SO FAR:
---
{all_summaries}
---

CURRENT DRAFT REPORT (may be empty on cycle 1):
---
{current_draft or "No draft yet."}
---

Your tasks:
1. Write an improved DRAFT_REPORT in Markdown. It should:
   - Have a clear title and introduction.
   - Organise findings under logical headings.
   - Integrate evidence from the notes.
   - Note any tensions, contradictions, or disagreements between sources.
   - Include an "Implications" section.
   - Include an "Open Questions" section.
   - Be better and more complete than the current draft.

2. Write GAPS: a short list (up to 6 items) of the most important knowledge gaps \
that remain after this cycle.

3. Write NEXT_SEARCH_ANGLES: a short list (up to 4 items) of specific search \
queries or sub-topics that would be most valuable to research next.

Respond ONLY in this exact format:

DRAFT_REPORT:
<full markdown report>

GAPS:
- <gap>
- <gap>
...

NEXT_SEARCH_ANGLES:
- <search query or angle>
- <search query or angle>
...
"""


def search_query_prompt(topic: str, cycle: int, previous_titles: list[str],
                        next_angles: str) -> str:
    prev = "\n".join(f"  - {t}" for t in previous_titles[-20:]) if previous_titles else "  (none yet)"
    angles_hint = f"\nSuggested angles from previous synthesis:\n{next_angles}" if next_angles else ""
    return f"""\
RESEARCH TOPIC:
{topic}

CYCLE: {cycle}

SOURCES ALREADY COLLECTED (titles — avoid repeating these):
{prev}
{angles_hint}

Generate 2 distinct web search queries that would find NEW, USEFUL sources \
not already covered. Each query should target a specific angle, sub-topic, \
or piece of evidence relevant to the research topic.

Respond ONLY in this exact format:

QUERY_1: <search query>
QUERY_2: <search query>
"""
