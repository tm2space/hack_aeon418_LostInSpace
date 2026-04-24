#!/usr/bin/env python3
"""
run_evaluation.py
=================

CLI for the Basilisk hackathon harness.

    # Score one case
    python run_evaluation.py --submission path/to/submission.py --case case1

    # Score all three
    python run_evaluation.py --submission path/to/submission.py --all

    # Mock simulation (no Basilisk required) -- good for local dev
    python run_evaluation.py --submission path/to/submission.py --all --mock

    # Dump JSON for the leaderboard pipeline
    python run_evaluation.py --submission ... --all --json results.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from basilisk_harness.harness import run_one_case, run_all, PLAN_BUDGET_S


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", required=True,
                    help="path to team's submission.py")
    ap.add_argument("--case", choices=["case1", "case2", "case3"],
                    help="run a single case")
    ap.add_argument("--all", action="store_true",
                    help="run all three cases and report S_total")
    ap.add_argument("--mock", action="store_true",
                    help="use mock_sim instead of Basilisk (dev only)")
    ap.add_argument("--step", type=float, default=0.050,
                    help="sim step size in seconds (default 0.050)")
    ap.add_argument("--plan-timeout", type=float, default=PLAN_BUDGET_S,
                    help=f"plan_imaging() wall-clock budget in seconds (default {PLAN_BUDGET_S:.0f})")
    ap.add_argument("--json", type=Path,
                    help="write full results JSON to this path")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args()

    level = logging.WARNING if args.verbose == 0 else \
            logging.INFO    if args.verbose == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not args.all and not args.case:
        ap.error("one of --all or --case is required")

    sub_path = str(Path(args.submission).resolve())
    use_bsk = not args.mock

    if args.all:
        results = run_all(sub_path,
                          use_basilisk=use_bsk,
                          plan_timeout_s=args.plan_timeout,
                          sim_step_s=args.step)
        _print_summary(results)
        if args.json:
            args.json.write_text(json.dumps(results, indent=2))
    else:
        score = run_one_case(args.case, sub_path,
                             use_basilisk=use_bsk,
                             plan_timeout_s=args.plan_timeout,
                             sim_step_s=args.step)
        d = score.as_dict()
        _print_single(d)
        if args.json:
            args.json.write_text(json.dumps(d, indent=2))

    return 0


def _print_single(d: dict) -> None:
    print(f"\n  === {d['case_id']} ===")
    print(f"  S_orbit  = {d['S_orbit']:.4f}")
    print(f"  C        = {d['C']:.4f}")
    print(f"  eta_E    = {d['eta_E']:.4f}")
    print(f"  eta_T    = {d['eta_T']:.4f}")
    print(f"  Q_smear  = {d['Q_smear']:.4f}")
    print(f"  frames   = {d['frames_kept']} kept / {d['frames_total']} attempted")
    if d.get("frames_rejected_reason"):
        print(f"  rejects  = {d['frames_rejected_reason']}")
    print()


def _print_summary(results: dict) -> None:
    print(f"\n  === SUMMARY ===")
    print(f"  S_total = {results['S_total']:.4f}")
    print(f"    weights = {results['weights']}")
    for case_id, d in results["per_case"].items():
        _print_single(d)


if __name__ == "__main__":
    sys.exit(main())
