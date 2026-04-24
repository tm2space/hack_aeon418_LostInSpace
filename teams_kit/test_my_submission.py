#!/usr/bin/env python3
"""
test_my_submission.py
=====================

Score your Lost in Space submission locally using the mock physics simulator.

    python test_my_submission.py path/to/your_submission.py

    # one case only
    python test_my_submission.py your_submission.py --case case1

    # dump full JSON breakdown
    python test_my_submission.py your_submission.py --json out.json

The mock simulator treats your commanded attitude schedule as perfectly
tracked (i.e. no ACS dynamics or controller lag). The scorer, validator,
TLEs, AOI polygon, and gate logic are IDENTICAL to what the organizers run.
In practice this means:

  * If your submission scores > 0 here, it will score > 0 on the real grader.
  * Your numbers here will be optimistic relative to the real sim -- the
    organizers run Basilisk 6-DoF with a real RW cluster, so expect some
    frames the mock passes to get rejected by the real grader when the
    controller overshoots or the wheels saturate briefly.
  * Target smear and off-nadir margins of at least ~20% so you survive the
    gap between mock and real.

See README.md for details on the kit, and the problem statement for the
function contract.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from basilisk_harness.harness import run_one_case, run_all, PLAN_BUDGET_S


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", help="path to your submission .py file")
    ap.add_argument("--case", choices=["case1", "case2", "case3"],
                    help="run only this case (default: run all three)")
    ap.add_argument("--step", type=float, default=0.050,
                    help="mock sim step size in seconds (default 0.050)")
    ap.add_argument("--json", type=Path, help="write full JSON results here")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="suppress INFO logs")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    sub = str(Path(args.submission).resolve())
    if not Path(sub).exists():
        print(f"error: file not found: {sub}", file=sys.stderr)
        return 2

    if args.case:
        score = run_one_case(args.case, sub,
                             use_basilisk=False,         # force mock
                             plan_timeout_s=PLAN_BUDGET_S,
                             sim_step_s=args.step)
        d = score.as_dict()
        _print_single(d)
        if args.json:
            args.json.write_text(json.dumps(d, indent=2))
    else:
        results = run_all(sub,
                          use_basilisk=False,            # force mock
                          plan_timeout_s=PLAN_BUDGET_S,
                          sim_step_s=args.step)
        _print_summary(results)
        if args.json:
            args.json.write_text(json.dumps(results, indent=2))

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
        rej = {k: v for k, v in d['frames_rejected_reason'].items() if v > 0}
        if rej:
            print(f"  rejects  = {rej}")
    if d.get("debug", {}).get("failure_reason"):
        print(f"  FAILURE  = {d['debug']['failure_reason']}")
        for key in ("errors", "warnings"):
            if d["debug"].get(key):
                for m in d["debug"][key]:
                    print(f"     {key[:-1]}: {m}")
    print()


def _print_summary(results: dict) -> None:
    print(f"\n  === SUMMARY (mock sim) ===")
    print(f"  S_total = {results['S_total']:.4f}")
    print(f"    weights = {results['weights']}")
    for _case_id, d in results["per_case"].items():
        _print_single(d)


if __name__ == "__main__":
    sys.exit(main())
