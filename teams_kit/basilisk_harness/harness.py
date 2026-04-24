"""
harness
=======

Top-level orchestration:

    run_one_case(case_id, submission_path, use_basilisk=True) -> OrbitScore
    run_all(submission_path, use_basilisk=True)               -> dict

Responsibilities:
  1. Dynamically import the team's submission.py (sandboxed namespace).
  2. Call plan_imaging(...) under a 120-second wall-clock timeout.
  3. Structural validation of the returned schedule. Fail -> S_orbit = 0.
  4. Simulate (Basilisk if available, else mock).
  5. Score via AoiScorer.

Timeout is implemented with a subprocess so team code cannot steal the main
interpreter's SIGALRM or hang on non-Python threads (numpy BLAS calls, etc).
"""
from __future__ import annotations

import importlib.util
import json
import logging
import multiprocessing as mp
import os
import pickle
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from .config import PassConfig, load_pass_config, CASE_WEIGHTS
from .schedule_validator import StructuralValidator
from .scorer import AoiScorer, OrbitScore, Telemetry
from . import sgp4_utils as s4u

log = logging.getLogger("basilisk_harness")

PLAN_BUDGET_S = 120.0   # per spec


# --------------------------------------------------------------------- runner
def run_one_case(case_id: str,
                 submission_path: str,
                 use_basilisk: bool = True,
                 plan_timeout_s: float = PLAN_BUDGET_S,
                 sim_step_s: float = 0.050,
                 ) -> OrbitScore:
    cfg = load_pass_config(case_id)
    log.info("Running case %s (%s)", case_id, cfg.description or "no description")

    # ---- 1. Plan (with timeout) ------------------------------------------------
    try:
        schedule = _plan_with_timeout(submission_path, cfg, plan_timeout_s)
    except TimeoutError:
        log.warning("case=%s: plan_imaging exceeded %.1fs budget", case_id, plan_timeout_s)
        return _zero_score(cfg.case_id, reason="plan_timeout")
    except Exception as e:
        log.warning("case=%s: plan_imaging raised %s: %s", case_id, type(e).__name__, e)
        return _zero_score(cfg.case_id, reason=f"plan_exception:{type(e).__name__}")

    # ---- 2. Structural validate -----------------------------------------------
    T_pass = s4u.pass_duration_s(cfg.pass_start, cfg.pass_end)
    v = StructuralValidator(pass_duration_s=T_pass)
    report = v.validate(schedule)
    if not report.ok:
        log.warning("case=%s: schedule failed validation: %s", case_id, report.errors)
        return _zero_score(cfg.case_id, reason="validation_failed",
                           extra={"errors": report.errors, "warnings": report.warnings})
    for w in report.warnings:
        log.info("case=%s: validator warning: %s", case_id, w)

    # ---- 3. Simulate ----------------------------------------------------------
    try:
        telemetry = _simulate(cfg, schedule, use_basilisk=use_basilisk, step_s=sim_step_s)
    except Exception as e:
        log.error("case=%s: simulation failed: %s\n%s", case_id, e, traceback.format_exc())
        return _zero_score(cfg.case_id, reason=f"sim_exception:{type(e).__name__}")

    # ---- 4. Score -------------------------------------------------------------
    scorer = AoiScorer(cfg)
    score = scorer.evaluate(schedule, telemetry)
    log.info("case=%s: S_orbit=%.4f  C=%.3f eta_E=%.3f eta_T=%.3f Q_smear=%.3f",
             case_id, score.S_orbit, score.C, score.eta_E, score.eta_T, score.Q_smear)
    return score


def run_all(submission_path: str,
            cases=("case1", "case2", "case3"),
            use_basilisk: bool = True,
            plan_timeout_s: float = PLAN_BUDGET_S,
            sim_step_s: float = 0.050,
            ) -> Dict[str, Any]:
    per_case: Dict[str, Dict[str, Any]] = {}
    S_total = 0.0
    for case_id in cases:
        score = run_one_case(case_id, submission_path,
                             use_basilisk=use_basilisk,
                             plan_timeout_s=plan_timeout_s,
                             sim_step_s=sim_step_s)
        w = CASE_WEIGHTS.get(case_id, 0.0)
        per_case[case_id] = score.as_dict()
        S_total += w * score.S_orbit
    return {
        "S_total": float(S_total),
        "weights": CASE_WEIGHTS,
        "per_case": per_case,
    }


# --------------------------------------------------------------------- helpers
def _simulate(cfg: PassConfig, schedule: Dict[str, Any],
              use_basilisk: bool, step_s: float) -> Telemetry:
    if use_basilisk:
        try:
            from . import basilisk_sim
            if basilisk_sim.basilisk_available():
                return basilisk_sim.BasiliskSim(cfg, step_s=step_s).run(schedule)
            log.warning("Basilisk requested but not importable -- falling back to mock_sim. "
                        "Leaderboard runs MUST use the Basilisk path.")
        except ImportError:
            log.warning("basilisk_sim module not present (teams-kit build?) -- using mock_sim.")
    from . import mock_sim
    return mock_sim.run_mock(cfg, schedule, dt_s=step_s)


def _zero_score(case_id: str, reason: str, extra: Optional[Dict[str, Any]] = None) -> OrbitScore:
    debug = {"failure_reason": reason}
    if extra:
        debug.update(extra)
    return OrbitScore(
        case_id=case_id, S_orbit=0.0, C=0.0, eta_E=0.0, eta_T=0.0, Q_smear=0.0,
        frames_total=0, frames_kept=0, frames_rejected_reason={}, debug=debug,
    )


# -------------------------------------------------------- sandboxed invocation
def _plan_worker(submission_path: str, cfg_bytes: bytes, out_path: str) -> None:
    """Runs in a subprocess. Imports submission.py and calls plan_imaging."""
    try:
        cfg: PassConfig = pickle.loads(cfg_bytes)
        spec = importlib.util.spec_from_file_location("team_submission", submission_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"could not import {submission_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["team_submission"] = module
        spec.loader.exec_module(module)
        if not hasattr(module, "plan_imaging"):
            raise AttributeError("submission.py does not export plan_imaging(...)")

        schedule = module.plan_imaging(
            tle_line1       = cfg.tle1,
            tle_line2       = cfg.tle2,
            aoi_polygon_llh = cfg.aoi_polygon,
            pass_start_utc  = cfg.pass_start,
            pass_end_utc    = cfg.pass_end,
            sc_params       = cfg.sc_params,
        )
        with open(out_path, "wb") as f:
            pickle.dump({"ok": True, "schedule": schedule}, f)
    except BaseException as e:
        with open(out_path, "wb") as f:
            pickle.dump({
                "ok": False,
                "error_type": type(e).__name__,
                "error_msg": str(e),
                "traceback": traceback.format_exc(),
            }, f)


def _plan_with_timeout(submission_path: str, cfg: PassConfig,
                       timeout_s: float) -> Dict[str, Any]:
    submission_path = str(Path(submission_path).resolve())
    if not os.path.exists(submission_path):
        raise FileNotFoundError(submission_path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as out_f:
        out_path = out_f.name

    ctx = mp.get_context("spawn")   # clean interpreter, no fork-inherited state
    p = ctx.Process(
        target=_plan_worker,
        args=(submission_path, pickle.dumps(cfg), out_path),
        daemon=False,
    )
    t_start = time.time()
    p.start()
    p.join(timeout_s)
    elapsed = time.time() - t_start

    if p.is_alive():
        p.terminate()
        p.join(5.0)
        if p.is_alive():
            p.kill()
        try: os.unlink(out_path)
        except FileNotFoundError: pass
        raise TimeoutError(f"plan_imaging exceeded {timeout_s:.1f}s (killed at {elapsed:.1f}s)")

    if p.exitcode != 0:
        try: os.unlink(out_path)
        except FileNotFoundError: pass
        raise RuntimeError(f"plan_imaging subprocess exited with code {p.exitcode}")

    with open(out_path, "rb") as f:
        result = pickle.load(f)
    try: os.unlink(out_path)
    except FileNotFoundError: pass

    if not result.get("ok"):
        raise RuntimeError(
            f"{result.get('error_type','Error')}: {result.get('error_msg','')}\n"
            + result.get('traceback', '')
        )
    return result["schedule"]
