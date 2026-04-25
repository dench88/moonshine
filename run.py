"""
Main entry point for the overnight research loop.

Usage:
    python run.py                # run all topics in topic.txt
    python run.py --resume       # resume the most recent incomplete run
    python run.py --resume --run-id 3   # resume a specific run
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime

import db
import researcher
import synthesiser
from config import (
    MAX_CYCLES, OUTPUT_DIR, REPORTS_DIR, LOGS_DIR, TOPIC_FILE,
    MODEL_ALIASES, resolve_model, RESEARCHER_MODEL, SYNTHESISER_MODEL,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(run_id: int) -> logging.Logger:
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, f"run_{run_id}.log")

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    # Swap out any file handler from a previous run
    root.handlers = [h for h in root.handlers if not isinstance(h, logging.FileHandler)]

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
               for h in root.handlers):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(fmt)
        root.addHandler(stream_handler)

    root.setLevel(logging.INFO)
    return logging.getLogger("loop")


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def write_notes_file(run_id: int, topic: str):
    summaries = db.get_all_summaries(run_id)
    lines = [f"# Research Notes\n\n**Topic:** {topic}\n\n**Generated:** {datetime.utcnow().isoformat()}Z\n\n---\n"]
    for s in summaries:
        lines.append(
            f"## [{s['title']}]({s['url']})\n"
            f"*Cycle {s['cycle_number']} | Relevance {s['relevance_score']}/10 | Quality {s['quality_score']}/10*\n\n"
            f"**Summary:** {s['summary']}\n\n"
            f"**Why relevant:** {s['why_relevant']}\n\n"
            f"**Key points:**\n{s['key_points']}\n\n---\n"
        )
    path = os.path.join(OUTPUT_DIR, f"run_{run_id}_notes.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def write_draft_file(run_id: int, draft: str, label: str = "draft") -> str:
    path = os.path.join(OUTPUT_DIR, f"run_{run_id}_{label}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(draft)
    return path


# ---------------------------------------------------------------------------
# Topic file
# ---------------------------------------------------------------------------

def read_topics() -> list[str]:
    if not os.path.exists(TOPIC_FILE):
        print(f"ERROR: topic file not found at {TOPIC_FILE}")
        print("Create it with one research question per line, e.g.:")
        print('  echo "What are the main mechanisms of CRISPR off-target effects?" > topic.txt')
        sys.exit(1)
    with open(TOPIC_FILE, encoding="utf-8") as f:
        topics = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    if not topics:
        print("ERROR: topic.txt has no topics (add one question per line).")
        sys.exit(1)
    return topics


# ---------------------------------------------------------------------------
# Single-run loop
# ---------------------------------------------------------------------------

def run_single(topic: str, run_id: int, start_cycle: int, max_cycles: int,
               researcher_model: str | None = None, synthesiser_model: str | None = None):
    logger = setup_logging(run_id)
    logger.info("Run %d — topic: %s", run_id, topic)
    logger.info("Max cycles: %d", max_cycles)
    logger.info("Researcher model: %s", resolve_model(researcher_model or RESEARCHER_MODEL))
    logger.info("Synthesiser model: %s", resolve_model(synthesiser_model or SYNTHESISER_MODEL))

    latest_draft = db.get_latest_draft(run_id)
    next_angles = latest_draft["next_search_angles"] if latest_draft else ""

    for cycle in range(start_cycle, max_cycles + 1):
        cycle_start = time.time()
        logger.info("=" * 60)
        logger.info("CYCLE %d / %d", cycle, max_cycles)
        logger.info("=" * 60)

        # --- Researcher ---
        try:
            accepted = researcher.run_researcher(
                run_id=run_id,
                cycle=cycle,
                topic=topic,
                next_angles=next_angles,
                model=researcher_model,
            )
        except Exception as exc:
            logger.error("Researcher pass crashed in cycle %d: %s", cycle, exc)
            db.log_failure(run_id, cycle, "researcher_crash", "", str(exc))
            accepted = 0

        notes_path = write_notes_file(run_id, topic)
        logger.info("Notes file updated: %s", notes_path)

        if accepted == 0:
            logger.warning("No sources accepted in cycle %d — continuing anyway", cycle)

        # --- Synthesiser ---
        try:
            synth_result = synthesiser.run_synthesiser(
                run_id=run_id,
                cycle=cycle,
                topic=topic,
                model=synthesiser_model,
            )
            next_angles = synth_result.get("next_angles", "")
        except Exception as exc:
            logger.error("Synthesiser pass crashed in cycle %d: %s", cycle, exc)
            db.log_failure(run_id, cycle, "synthesiser_crash", "", str(exc))
            synth_result = {"draft": "", "gaps": "", "next_angles": next_angles}

        if synth_result.get("draft"):
            draft_path = write_draft_file(run_id, synth_result["draft"], label="draft")
            logger.info("Draft file updated: %s", draft_path)

        db.update_run_status(run_id, "running", cycle_count=cycle)
        logger.info("Cycle %d complete in %.1fs", cycle, time.time() - cycle_start)

    # --- Finalise ---
    logger.info("All %d cycles complete.", max_cycles)
    db.update_run_status(run_id, "completed", cycle_count=max_cycles)

    final_draft_row = db.get_latest_draft(run_id)
    if final_draft_row and final_draft_row["draft_markdown"]:
        final_path = os.path.join(REPORTS_DIR, f"run_{run_id}_final_report.md")
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(final_draft_row["draft_markdown"])
        logger.info("Final report saved: %s", final_path)
    else:
        logger.warning("No draft available for final report.")

    notes_path = write_notes_file(run_id, topic)
    logger.info("Final notes saved: %s", notes_path)
    logger.info("Run %d completed successfully.", run_id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    alias_list = ", ".join(sorted(MODEL_ALIASES))
    parser = argparse.ArgumentParser(description="Overnight research loop")
    parser.add_argument("--resume", action="store_true", help="Resume the most recent incomplete run")
    parser.add_argument("--run-id", type=int, help="Resume a specific run by ID")
    parser.add_argument("--max-cycles", type=int, default=None,
                        help="Override max cycles (default: config value)")
    parser.add_argument("--researcher", metavar="MODEL", default=None,
                        help=f"Model for the Researcher role. Aliases: {alias_list}")
    parser.add_argument("--synthesiser", metavar="MODEL", default=None,
                        help=f"Model for the Synthesiser role. Aliases: {alias_list}")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    # --- Resume a specific run ---
    if args.resume or args.run_id:
        if args.run_id:
            run = db.get_run(args.run_id)
            if not run:
                print(f"ERROR: run {args.run_id} not found in database.")
                sys.exit(1)
        else:
            run = db.get_latest_run()
            if not run:
                print("No previous run found — starting fresh.")
                run = None

        if run:
            if run["status"] == "completed":
                print(f"WARNING: run {run['id']} is already completed.")
                print("Use --run-id <N> to resume a specific incomplete run, or start fresh without --resume.")
                sys.exit(1)
            run_id = run["id"]
            topic = run["topic"]
            start_cycle = run["cycle_count"] + 1
            max_cycles = args.max_cycles if args.max_cycles is not None else run["max_cycles"]
            db.update_run_status(run_id, "running")
            run_single(topic, run_id, start_cycle, max_cycles,
                       researcher_model=args.researcher,
                       synthesiser_model=args.synthesiser)
            return

    # --- Run all topics in topic.txt sequentially ---
    topics = read_topics()
    effective_max = args.max_cycles if args.max_cycles is not None else MAX_CYCLES

    print(f"Found {len(topics)} topic(s) to research.")
    for i, topic in enumerate(topics, 1):
        print(f"\n{'=' * 60}")
        print(f"Topic {i}/{len(topics)}: {topic}")
        print(f"{'=' * 60}\n")
        run_id = db.create_run(topic, effective_max)
        run_single(topic, run_id, 1, effective_max,
                   researcher_model=args.researcher,
                   synthesiser_model=args.synthesiser)


if __name__ == "__main__":
    main()
