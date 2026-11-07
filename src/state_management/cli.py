"""Command-line entry point for the memory ablation harness."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run controlled ablations of raw, summarized, and structured agent memory."
    )
    parser.add_argument("--version", action="version", version="state-management 0.1.0")
    parser.parse_args()
    parser.print_help()
