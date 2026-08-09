"""Entry point for running a research job locally (synchronous, in-memory).

This is Build Sequence Step 1 from ARCHITECTURE.md Section 11:
no API, no queue, no persistence — just the agent graph running end-to-end.

Usage:
    python -m src.main "I want to build a project management tool for solo developers"
    python -m src.main --depth deep "A note-taking app with AI organization"
"""

from __future__ import annotations

import argparse
import logging

from src.config.settings import get_settings
from src.graph.state import create_initial_state


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a product research job locally.",
    )
    parser.add_argument(
        "idea",
        help="Your product idea in plain language.",
    )
    parser.add_argument(
        "--depth",
        choices=["fast", "deep"],
        default=None,
        help="Research depth (default: from settings, or 'fast').",
    )
    args = parser.parse_args()

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    depth = args.depth or settings.default_depth
    state = create_initial_state(raw_idea=args.idea, depth=depth)

    print(f"\n{'=' * 60}")
    print("Research Agent — Local Runner")
    print(f"{'=' * 60}")
    print(f"Idea:  {state['raw_idea']}")
    print(f"Depth: {state['depth']}")
    print(f"Job:   {state['job_id']}")
    print(f"{'=' * 60}\n")

    from src.graph.build_graph import build_graph
    graph = build_graph()

    print("Running research agent... (this may take a while depending on depth)")
    final_state = graph.invoke(state)

    print(f"\n{'=' * 60}")
    print("FINAL REPORT")
    print(f"{'=' * 60}\n")
    print(final_state["report_markdown"])
    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
