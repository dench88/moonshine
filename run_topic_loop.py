"""
Main entry point for the overnight research loop.

Usage:
    python run_topic_loop.py                # start a new run
    python run_topic_loop.py --resume       # resume the most recent run
    python run_topic_loop.py --resume --run-id 3   # resume a specific run
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
    MAX_CYCLES, OUTPUT_DIR, LOGS_DIR, TOPIC_FILE,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(run_id: int) -> logging.Logger:
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, f"run_{run_id}.log")

    fmt = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
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
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Overnight research loop")
    parser.add_argument("--resume", action="store_true", help="Resume the most recent run")
    parser.add_argument("--run-id", type=int, help="Resume a specific run by ID")
    parser.add_argument("--max-cycles", type=int, default=MAX_CYCLES)
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    # --- Read topic ---
    if not os.path.exists(TOPIC_FILE):
        print(f"ERROR: topic file not found at {TOPIC_FILE}")
        print("Create it with a single research question, e.g.:")
        print('  echo "What are the main mechanisms of CRISPR off-target effects?" > topic.txt')
        sys.exit(1)

    with open(TOPIC_FILE, encoding="utf-8") as f:
        topic = f.read().strip()

    if not topic:
        print("ERROR: topic.txt is empty.")
        sys.exit(1)

    # --- Resolve run ---
    if args.resume or args.run_id:
        if args.run_id:
            run = db.get_run(args.run_id)
            if not run:
                print(f"ERROR: run {args.run_id} not found in database.")
                sys.exit(1)
        else:
            run = db.get_latest_run()
            if not run:
                print("No previous run found — starting a new one.")
                run = None

        if run:
            run_id = run["id"]
            start_cycle = run["cycle_count"] + 1
            max_cycles = args.max_cycles
            logger = setup_logging(run_id)
            logger.info("Resuming run %d from cycle %d (topic: %s)", run_id, start_cycle, topic)
            db.update_run_status(run_id, "running")
        else:
            run_id = db.create_run(topic, args.max_cycles)
            start_cycle = 1
            max_cycles = args.max_cycles
            logger = setup_logging(run_id)
            logger.info("New run %d started (topic: %s)", run_id, topic)
    else:
        run_id = db.create_run(topic, args.max_cycles)
        start_cycle = 1
        max_cycles = args.max_cycles
        logger = setup_logging(run_id)
        logger.info("New run %d started (topic: %s)", run_id, topic)

    logger.info("Max cycles: %d", max_cycles)

    # --- Retrieve any existing synthesis state ---
    latest_draft = db.get_latest_draft(run_id)
    next_angles = latest_draft["next_search_angles"] if latest_draft else ""

    # ===================================================================
    # MAIN LOOP
    # ===================================================================
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
            )
        except Exception as exc:
            logger.error("Researcher pass crashed in cycle %d: %s", cycle, exc)
            db.log_failure(run_id, cycle, "researcher_crash", "", str(exc))
            accepted = 0

        # Save notes file after researcher pass
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
            )
            next_angles = synth_result.get("next_angles", "")
        except Exception as exc:
            logger.error("Synthesiser pass crashed in cycle %d: %s", cycle, exc)
            db.log_failure(run_id, cycle, "synthesiser_crash", "", str(exc))
            synth_result = {"draft": "", "gaps": "", "next_angles": next_angles}

        # Save draft file
        if synth_result.get("draft"):
            draft_path = write_draft_file(run_id, synth_result["draft"], label="draft")
            logger.info("Draft file updated: %s", draft_path)

        # --- Update cycle count ---
        db.update_run_status(run_id, "running", cycle_count=cycle)

        elapsed = time.time() - cycle_start
        logger.info("Cycle %d complete in %.1fs", cycle, elapsed)

    # ===================================================================
    # DONE
    # ===================================================================
    logger.info("All %d cycles complete.", max_cycles)
    db.update_run_status(run_id, "completed", cycle_count=max_cycles)

    # Write final report
    final_draft_row = db.get_latest_draft(run_id)
    if final_draft_row and final_draft_row["draft_markdown"]:
        final_path = write_draft_file(run_id, final_draft_row["draft_markdown"], label="final_report")
        logger.info("Final report saved: %s", final_path)
    else:
        logger.warning("No draft available for final report.")

    notes_path = write_notes_file(run_id, topic)
    logger.info("Final notes saved: %s", notes_path)
    logger.info("Run %d completed successfully.", run_id)


if __name__ == "__main__":
    main()
