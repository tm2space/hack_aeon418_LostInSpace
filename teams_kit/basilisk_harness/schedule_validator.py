"""
schedule_validator
==================

Fast structural validator for the dict returned by plan_imaging().

We run this BEFORE touching the Basilisk sim. A malformed schedule fails the
case immediately with S_orbit = 0 and the error list is logged — this gives
clear feedback to teams instead of cryptic simulation errors.

Rules enforced (mirrors Section 7 of the problem statement):
  * top-level keys: objective(str), attitude(list), shutter(list)
  * attitude: strictly monotonic t, t[0]==0, unit-norm quaternions,
              spacing >= 20 ms, spacing <= 1.0 s (sanity)
  * shutter:  exactly 0.120 s windows, non-overlapping, ascending
  * shutter:  every window fits inside attitude's [t_min, t_max]
  * optional keys: notes(str), target_hints_llh(list[dict])
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

INTEGRATION_S      = 0.120
MIN_SAMPLE_DT_S    = 0.020     # 50 Hz ceiling
MAX_SAMPLE_DT_S    = 1.000     # sanity floor (1 Hz)
QUAT_NORM_TOL      = 1e-3
FLOAT_EPS          = 1e-9


class ValidationError(Exception):
    """Raised by validate_strict when a schedule fails structural checks."""


@dataclass
class ValidationReport:
    ok: bool
    errors:   List[str]
    warnings: List[str]

    def __bool__(self) -> bool:
        return self.ok


class StructuralValidator:
    """
    Usage:
        v = StructuralValidator(pass_duration_s=T_pass)
        report = v.validate(schedule)
        if not report.ok:
            for e in report.errors: print("ERROR:", e)
    """

    def __init__(self, pass_duration_s: float):
        self.T = float(pass_duration_s)

    # ------------------------------------------------------------------ public
    def validate(self, schedule: Any) -> ValidationReport:
        errors:   List[str] = []
        warnings: List[str] = []

        if not isinstance(schedule, dict):
            return ValidationReport(False, ["top-level object is not a dict"], [])

        # ---- top-level keys ---------------------------------------------------
        for k in ("objective", "attitude", "shutter"):
            if k not in schedule:
                errors.append(f"missing required key '{k}'")
        if errors:
            return ValidationReport(False, errors, warnings)

        if not isinstance(schedule["objective"], str) or not schedule["objective"].strip():
            errors.append("'objective' must be a non-empty string")

        # ---- attitude trajectory ---------------------------------------------
        att = schedule["attitude"]
        if not isinstance(att, list) or len(att) < 2:
            errors.append("'attitude' must be a list with at least 2 samples")
        else:
            self._check_attitude(att, errors, warnings)

        # ---- shutter windows --------------------------------------------------
        sh = schedule["shutter"]
        if not isinstance(sh, list):
            errors.append("'shutter' must be a list (possibly empty)")
        else:
            self._check_shutter(sh, att if isinstance(att, list) else [], errors, warnings)

        # ---- optional extras --------------------------------------------------
        if "notes" in schedule and not isinstance(schedule["notes"], str):
            warnings.append("'notes' should be a string if present (ignored)")

        if "target_hints_llh" in schedule:
            th = schedule["target_hints_llh"]
            if not isinstance(th, list):
                warnings.append("'target_hints_llh' should be a list if present (ignored)")
            elif isinstance(sh, list) and len(th) != len(sh):
                warnings.append(
                    f"'target_hints_llh' length ({len(th)}) != shutter length ({len(sh)}); ignored"
                )

        return ValidationReport(len(errors) == 0, errors, warnings)

    def validate_strict(self, schedule: Any) -> None:
        """Raise ValidationError on failure, else return None."""
        rep = self.validate(schedule)
        if not rep.ok:
            raise ValidationError("; ".join(rep.errors))

    # ------------------------------------------------------------------ helpers
    def _check_attitude(self, att: List[Any], errors: List[str], warnings: List[str]) -> None:
        prev_t = -math.inf
        for i, s in enumerate(att):
            ctx = f"attitude[{i}]"
            if not isinstance(s, dict):
                errors.append(f"{ctx} is not a dict"); return
            if "t" not in s or "q_BN" not in s:
                errors.append(f"{ctx} missing 't' or 'q_BN'"); continue
            t = s["t"]; q = s["q_BN"]
            if not isinstance(t, (int, float)):
                errors.append(f"{ctx} 't' must be numeric"); continue
            if not (isinstance(q, (list, tuple)) and len(q) == 4):
                errors.append(f"{ctx} 'q_BN' must be length-4 list"); continue
            try:
                n = math.sqrt(sum(float(x)*float(x) for x in q))
            except (TypeError, ValueError):
                errors.append(f"{ctx} 'q_BN' contains non-numeric"); continue
            if abs(n - 1.0) > QUAT_NORM_TOL:
                errors.append(f"{ctx} quaternion norm={n:.5f} (expected 1.0 +/- {QUAT_NORM_TOL})")
            if i == 0 and abs(t) > FLOAT_EPS:
                errors.append(f"first attitude sample must have t=0 (got {t})")
            if t <= prev_t + FLOAT_EPS:
                errors.append(f"attitude timestamps not strictly increasing at index {i} (t={t}, prev={prev_t})")
            if i > 0:
                dt = t - prev_t
                if dt + FLOAT_EPS < MIN_SAMPLE_DT_S:
                    errors.append(f"attitude spacing < {MIN_SAMPLE_DT_S}s at index {i} (dt={dt:.4f})")
                elif dt > MAX_SAMPLE_DT_S:
                    warnings.append(f"attitude spacing > {MAX_SAMPLE_DT_S}s at index {i} (dt={dt:.3f}) — SLERP will be coarse")
            prev_t = t

        t_last = att[-1]["t"] if att and isinstance(att[-1], dict) else None
        if isinstance(t_last, (int, float)) and t_last > self.T + 1e-3:
            warnings.append(f"last attitude sample t={t_last:.3f}s exceeds pass duration T={self.T:.3f}s (trimmed)")

    def _check_shutter(self, sh: List[Any], att: List[Any],
                       errors: List[str], warnings: List[str]) -> None:
        t_att_min = 0.0
        t_att_max = None
        if att and isinstance(att[-1], dict) and isinstance(att[-1].get("t"), (int, float)):
            t_att_max = float(att[-1]["t"])

        prev_end = -math.inf
        for i, w in enumerate(sh):
            ctx = f"shutter[{i}]"
            if not isinstance(w, dict):
                errors.append(f"{ctx} is not a dict"); return
            if "t_start" not in w or "duration" not in w:
                errors.append(f"{ctx} missing 't_start' or 'duration'"); continue
            ts = w["t_start"]; dur = w["duration"]
            if not isinstance(ts, (int, float)) or not isinstance(dur, (int, float)):
                errors.append(f"{ctx} 't_start' and 'duration' must be numeric"); continue
            if abs(float(dur) - INTEGRATION_S) > 1e-6:
                errors.append(f"{ctx} duration={dur} must equal {INTEGRATION_S}s exactly")
            if ts + FLOAT_EPS < t_att_min:
                errors.append(f"{ctx} starts before attitude t_min={t_att_min}")
            te = ts + dur
            if t_att_max is not None and te > t_att_max + FLOAT_EPS:
                errors.append(f"{ctx} ends at t={te:.4f} past last attitude sample t={t_att_max:.4f}")
            if ts + FLOAT_EPS < prev_end:
                errors.append(f"{ctx} overlaps previous window (starts at {ts}, prev ended at {prev_end})")
            prev_end = te

        # Not an error to have zero shutter windows — just yields C=0.
        if len(sh) == 0:
            warnings.append("shutter list is empty — pass will score C=0")
