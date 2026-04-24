"""
scorer
======

Turns (schedule, telemetry) into an OrbitScore.

Per-orbit formula:
    S_orbit = C * (1 + alpha*eta_E + beta*eta_T) * Q_smear

where
    C        = fraction of AOI covered by VALID frames (0..1)
    eta_E    = 1 - dH_used / dH_budget           (clipped [0,1])
    eta_T    = 1 - T_active / T_pass              (clipped [0,1])
    Q_smear  = 1 - (fraction of kept frames that violated smear)  (clipped [0,1])

A frame is VALID if, during its 120 ms shutter window, all three of:
    (1) every wheel |H_i| <= H_max  (wheel saturation gate)
    (2) |omega_body| <= smear_rate_limit_dps continuously (smear gate)
    (3) off-nadir angle at shutter midpoint <= off_nadir_max_deg
Violations disqualify that frame (its footprint is not added to coverage).

T_active is the cumulative time the sim spent either slewing (|omega|>0.5 deg/s)
or integrating (inside a shutter window), expressed as a fraction of T_pass.
This rewards algorithms that "settle and shoot" over ones that slew constantly.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Tuple

import numpy as np

from . import sgp4_utils as s4u
from . import geometry as geo
from .config import PassConfig


# ------------------------------------------------------------------- telemetry
# The shape the sim (Basilisk or mock) must produce.
@dataclass
class Telemetry:
    """
    Time-aligned samples from the simulator. All arrays length N_steps.
    """
    t_s:         np.ndarray    # (N,) seconds since pass_start
    q_BN:        np.ndarray    # (N,4) scalar-last
    omega_B:     np.ndarray    # (N,3) rad/s, body frame
    H_wheels:    np.ndarray    # (N,4) Nms per wheel
    r_eci:       np.ndarray    # (N,3) satellite pos in ECI, m
    gmst_rad:    np.ndarray    # (N,) sidereal angle at each sample


# ------------------------------------------------------------------- score DTO
@dataclass
class OrbitScore:
    case_id:      str
    S_orbit:      float
    C:            float
    eta_E:        float
    eta_T:        float
    Q_smear:      float
    frames_total: int
    frames_kept:  int
    frames_rejected_reason: Dict[str, int] = field(default_factory=dict)
    debug:        Dict[str, Any]           = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# ------------------------------------------------------------------- scorer
class AoiScorer:
    """One-shot scorer for a pass. Holds the AOI coverage accumulator."""

    def __init__(self, cfg: PassConfig):
        self.cfg = cfg
        sc = cfg.sc_params
        self.integration_s      = float(sc["integration_s"])
        self.fov_deg            = tuple(sc["fov_deg"])
        self.Hmax               = float(sc["wheel_Hmax_Nms"])
        self.smear_limit_dps    = float(sc["smear_rate_limit_dps"])
        self.off_nadir_max_deg  = float(sc["off_nadir_max_deg"])
        self.alpha              = cfg.alpha
        self.beta               = cfg.beta
        self.dH_budget          = cfg.delta_h_budget
        self.T_pass             = s4u.pass_duration_s(cfg.pass_start, cfg.pass_end)

    # ------------------------------------------------------------------ main
    def evaluate(self, schedule: Dict[str, Any], telemetry: Telemetry) -> OrbitScore:
        cov = geo.CoverageAccumulator(self.cfg.aoi_polygon)

        frames_total = len(schedule["shutter"])
        frames_kept  = 0
        reject_counts: Dict[str, int] = {
            "wheel_saturation": 0,
            "smear_exceeded":   0,
            "off_nadir":        0,
            "ray_miss":         0,
        }
        smear_violations_total = 0

        # Pre-compute wheel-H max magnitudes per sample to avoid per-frame loops.
        H_mag_per_wheel = np.abs(telemetry.H_wheels)       # (N,4)
        omega_mag_dps   = np.linalg.norm(telemetry.omega_B, axis=1) * 180.0 / np.pi  # (N,)

        # Evaluate each shutter window.
        for i, win in enumerate(schedule["shutter"]):
            t0 = float(win["t_start"])
            t1 = t0 + float(win["duration"])
            mask = (telemetry.t_s >= t0) & (telemetry.t_s <= t1)
            if not np.any(mask):
                # No telemetry samples within the window -- treat as invalid.
                reject_counts["smear_exceeded"] += 1
                continue

            # Gate 1: wheel saturation during the window (any wheel, any sample)
            if np.any(H_mag_per_wheel[mask] > self.Hmax + 1e-9):
                reject_counts["wheel_saturation"] += 1
                continue

            # Gate 2: smear rate
            violated_smear = np.any(omega_mag_dps[mask] > self.smear_limit_dps + 1e-9)
            if violated_smear:
                smear_violations_total += 1
                reject_counts["smear_exceeded"] += 1
                continue

            # Gate 3: off-nadir at window midpoint
            t_mid = 0.5 * (t0 + t1)
            idx_mid = int(np.clip(np.searchsorted(telemetry.t_s, t_mid),
                                   1, len(telemetry.t_s) - 1))
            # Interpolate attitude from the *commanded schedule* -- the harness
            # tracks the command, but in degenerate plants the actual attitude
            # could lag. We score the physical attitude (from telemetry).
            q_mid = _slerp_quat_array(
                telemetry.q_BN[idx_mid-1], telemetry.q_BN[idx_mid],
                _lerp_u(telemetry.t_s[idx_mid-1], telemetry.t_s[idx_mid], t_mid),
            )
            r_mid  = _lerp_vec(telemetry.r_eci[idx_mid-1], telemetry.r_eci[idx_mid],
                               _lerp_u(telemetry.t_s[idx_mid-1],
                                        telemetry.t_s[idx_mid], t_mid))
            gm_mid = _lerp_scalar(telemetry.gmst_rad[idx_mid-1],
                                   telemetry.gmst_rad[idx_mid],
                                   _lerp_u(telemetry.t_s[idx_mid-1],
                                            telemetry.t_s[idx_mid], t_mid))

            fp = geo.project_footprint(q_mid, r_mid, gm_mid, self.fov_deg, t_mid)
            if fp is None:
                reject_counts["ray_miss"] += 1
                continue
            if fp.off_nadir_deg > self.off_nadir_max_deg + 1e-6:
                reject_counts["off_nadir"] += 1
                continue

            # All gates passed -- add to coverage.
            cov.add_frame(fp)
            frames_kept += 1

        # C: coverage
        C = cov.coverage_fraction()

        # eta_E: control-effort efficiency
        # dH_used = integrated L1 change in total |H_wheels| vector magnitude.
        dH = np.linalg.norm(np.diff(telemetry.H_wheels, axis=0), axis=1).sum()
        eta_E = max(0.0, min(1.0, 1.0 - dH / self.dH_budget))

        # eta_T: time efficiency
        SLEW_RATE_THRESHOLD_DPS = 0.5
        slewing = omega_mag_dps > SLEW_RATE_THRESHOLD_DPS
        # Treat the span from shutter starts to ends as "active" too.
        shutter_active = np.zeros_like(telemetry.t_s, dtype=bool)
        for win in schedule["shutter"]:
            t0 = float(win["t_start"])
            t1 = t0 + float(win["duration"])
            shutter_active |= (telemetry.t_s >= t0) & (telemetry.t_s <= t1)
        active = slewing | shutter_active
        if len(telemetry.t_s) >= 2:
            dt = np.diff(telemetry.t_s, append=telemetry.t_s[-1])
            T_active = float(np.sum(dt * active.astype(float)))
        else:
            T_active = 0.0
        eta_T = max(0.0, min(1.0, 1.0 - T_active / max(self.T_pass, 1e-6)))

        # Q_smear: based on fraction of *attempted* frames that smear-failed.
        if frames_total > 0:
            frac_smear_bad = smear_violations_total / frames_total
            Q_smear = max(0.0, min(1.0, 1.0 - frac_smear_bad))
        else:
            Q_smear = 1.0  # vacuous: no frames to smear

        S = C * (1.0 + self.alpha * eta_E + self.beta * eta_T) * Q_smear

        return OrbitScore(
            case_id=self.cfg.case_id,
            S_orbit=float(S),
            C=float(C),
            eta_E=float(eta_E),
            eta_T=float(eta_T),
            Q_smear=float(Q_smear),
            frames_total=frames_total,
            frames_kept=frames_kept,
            frames_rejected_reason=reject_counts,
            debug={
                "dH_used_Nms":       float(dH),
                "dH_budget_Nms":     self.dH_budget,
                "T_active_s":        float(T_active),
                "T_pass_s":          self.T_pass,
                "aoi_area_m2":       cov.aoi_area_m2(),
                "covered_area_m2":   cov.covered_area_m2(),
            },
        )


# ------------------------------------------------------------------- helpers
def _lerp_u(t0: float, t1: float, t: float) -> float:
    if t1 <= t0:
        return 0.0
    return max(0.0, min(1.0, (t - t0) / (t1 - t0)))


def _lerp_vec(v0: np.ndarray, v1: np.ndarray, u: float) -> np.ndarray:
    return (1 - u) * v0 + u * v1


def _lerp_scalar(a: float, b: float, u: float) -> float:
    return (1 - u) * a + u * b


def _slerp_quat_array(q0: np.ndarray, q1: np.ndarray, u: float) -> np.ndarray:
    # Thin wrapper matching geometry.slerp's interface on arrays.
    return geo.slerp(q0, q1, u)
