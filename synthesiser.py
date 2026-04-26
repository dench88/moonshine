"""
Synthesiser role.
Reads all accumulated source summaries + current draft,
produces an improved draft report and research gap list.
"""
from __future__ import annotations

import logging
import re

import llm_client as llm
import db
from config import SYNTHESISER_MODEL, resolve_model
from prompts import synthesiser_prompt

logger = logging.getLogger(__name__)


def _build_all_summaries_text(summaries: list[dict]) -> str:
    if not summaries:
        return "No sources collected yet."
    parts = []
    for s in summaries:
        parts.append(
            f"### Source (Cycle {s['cycle_number']}): {s['title']}\n"
            f"URL: {s['url']}\n"
            f"Relevance: {s['relevance_score']}/10  Quality: {s['quality_score']}/10\n\n"
            f"**Summary:** {s['summary']}\n\n"
            f"**Why relevant:** {s['why_relevant']}\n\n"
            f"**Key points:**\n{s['key_points']}\n"
        )
    return "\n---\n".join(parts)


def _parse_synthesiser_response(text: str) -> dict:
    def extract(label: str) -> str:
        pattern = rf"^{label}:\s*(.*?)(?=\n[A-Z_]+:|\Z)"
        m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
        return m.group(1).strip() if m else ""

    return {
        "draft": extract("DRAFT_REPORT"),
        "gaps": extract("GAPS"),
        "next_angles": extract("NEXT_SEARCH_ANGLES"),
    }


def run_synthesiser(run_id: int, cycle: int, topic: str,
                    model: str | None = None, keep_alive: int | None = None) -> dict:
    """
    Returns dict with keys: draft, gaps, next_angles.
    May return empty strings if synthesis fails.
    """
    model = resolve_model(model or SYNTHESISER_MODEL)
    logger.info("Synthesiser starting — run=%d cycle=%d model=%s", run_id, cycle, model)

    summaries = db.get_all_summaries(run_id)
    all_summaries_text = _build_all_summaries_text(summaries)

    latest_draft_row = db.get_latest_draft(run_id)
    current_draft = latest_draft_row["draft_markdown"] if latest_draft_row else ""

    prompt = synthesiser_prompt(
        topic=topic,
        all_summaries=all_summaries_text,
        current_draft=current_draft,
        cycle=cycle,
    )

    try:
        resp = llm.chat(prompt, system=llm.SYNTHESISER_SYSTEM, model=model, keep_alive=keep_alive)
        db.log_token_usage(run_id, cycle, "synthesiser", model,
                           resp.input_tokens, resp.output_tokens)
    except Exception as exc:
        logger.error("LLM synthesis failed: %s", exc)
        return {"draft": current_draft, "gaps": "", "next_angles": ""}

    parsed = _parse_synthesiser_response(resp.text)

    if not parsed["draft"]:
        logger.warning("Synthesiser returned empty draft — keeping previous draft")
        parsed["draft"] = current_draft

    db.save_draft(
        run_id=run_id,
        cycle=cycle,
        draft_md=parsed["draft"],
        gaps=parsed["gaps"],
        next_angles=parsed["next_angles"],
    )

    logger.info("Synthesiser done — draft saved (%d chars)", len(parsed["draft"]))
    return parsed
