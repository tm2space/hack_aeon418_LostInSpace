"""
mock_sim
========

A lightweight physics simulator that produces the same Telemetry payload the
Basilisk version does, WITHOUT requiring Basilisk to be installed.

What it does:
  * SGP4 forward-propagate the orbit at `dt_s` resolution
  * Treat the commanded attitude schedule as perfectly tracked:
       q_meas(t) = SLERP(schedule.attitude, t)
       omega_meas(t) = numerical derivative of q_meas
  * Approximate wheel momentum from body-frame angular momentum via the
    pyramidal pseudoinverse:  tau_w = W_plus @ (I @ omega_body)
    where W is the 3x4 wheel-axis matrix.

What it DOESN'T do:
  * No reaction-wheel friction, no control loop, no torque noise
  * No gravity-gradient torque
  * No actuator saturation feedback (it'll report H > H_max honestly, so the
    scorer's wheel-saturation gate still works)

Use this for:
  * End-to-end testing of scoring
  * CI / sanity checks
  * Teams who want to dry-run their planner before you open the real grader

Do NOT use it for final leaderboard scores. That's what basilisk_sim is for.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np

from . import geometry as geo
from . import sgp4_utils as s4u
from .config import PassConfig
from .scorer import Telemetry


def _wheel_matrix_pyramid_45() -> np.ndarray:
    """
    4 RWs, 45 deg cant from body +Z, azimuths 0/90/180/270. Returns 3x4
    matrix whose columns are the wheel spin-axis unit vectors in body.
    """
    c = math.cos(math.radians(45.0))
    s = math.sin(math.radians(45.0))
    # sin*cos(az), sin*sin(az), cos
    azs = [0.0, 90.0, 180.0, 270.0]
    cols = []
    for a_deg in azs:
        a = math.radians(a_deg)
        cols.append([s * math.cos(a), s * math.sin(a), c])
    return np.array(cols).T   # 3x4


def run_mock(cfg: PassConfig, schedule: Dict[str, Any],
             dt_s: float = 0.050) -> Telemetry:
    """
    Produce a Telemetry struct at `dt_s` cadence.
    dt_s=50ms is a reasonable default: fine enough for smear checks, coarse
    enough to score a full pass in ~1 s.
    """
    T_pass = s4u.pass_duration_s(cfg.pass_start, cfg.pass_end)
    n_steps = int(math.floor(T_pass / dt_s)) + 1
    t_s = np.linspace(0.0, T_pass, n_steps)

    # ----- orbit
    prop = s4u.Sgp4Propagator(cfg.tle1, cfg.tle2)
    samples = prop.propagate_series(cfg.pass_start, cfg.pass_end, dt_s=dt_s)
    # The propagate_series function generates its own n; resample to our grid.
    s_t     = np.array([s.t       for s in samples])
    s_reci  = np.array([s.r_eci   for s in samples])
    s_gmst  = np.array([s4u.gmst_rad(s.utc) for s in samples])
    r_eci    = np.stack([np.interp(t_s, s_t, s_reci[:, k]) for k in range(3)], axis=1)
    gmst_rad = np.interp(t_s, s_t, s_gmst)

    # ----- attitude track (perfect)
    q_BN = np.zeros((n_steps, 4))
    for i, t in enumerate(t_s):
        q_BN[i] = geo.sample_attitude(schedule["attitude"], float(t))

    # Body rates from numerical differentiation of the quaternion track.
    omega_B = _quat_deriv_to_body_rates(t_s, q_BN)

    # Wheel momentum approximation.
    I = np.array(cfg.sc_params["inertia_kgm2"])
    W = _wheel_matrix_pyramid_45()
    W_pinv = np.linalg.pinv(W)
    # H_body = I @ omega_B  -> H_wheels = W_pinv @ H_body  (minimum-norm)
    H_body = (I @ omega_B.T).T        # (N,3)
    H_wheels = (W_pinv @ H_body.T).T  # (N,4)

    return Telemetry(
        t_s=t_s, q_BN=q_BN, omega_B=omega_B, H_wheels=H_wheels,
        r_eci=r_eci, gmst_rad=gmst_rad,
    )


# ------------------------------------------------------------------- helpers
def _quat_deriv_to_body_rates(t_s: np.ndarray, q_BN: np.ndarray) -> np.ndarray:
    """
    Central-difference dq/dt -> body-frame angular velocity.

    For scalar-last q = [qx,qy,qz,qw], and omega in body frame:
        omega_B = 2 * (q* .otimes. dq/dt)
    where q* is the conjugate [-qx,-qy,-qz,qw].
    """
    n = len(t_s)
    omega = np.zeros((n, 3))
    if n < 2:
        return omega
    dq = np.gradient(q_BN, t_s, axis=0)
    for i in range(n):
        q = q_BN[i]; qd = dq[i]
        # Normalize q defensively.
        q = q / max(np.linalg.norm(q), 1e-12)
        # conjugate, scalar-last
        qc = np.array([-q[0], -q[1], -q[2], q[3]])
        # quaternion product p = qc ⊗ qd
        p = _quat_mul(qc, qd)
        # body rates are 2*vector-part of p
        omega[i] = 2.0 * p[:3]
    return omega


def _quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Scalar-last quaternion product, Hamilton convention."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw*bx + ax*bw + ay*bz - az*by,
        aw*by - ax*bz + ay*bw + az*bx,
        aw*bz + ax*by - ay*bx + az*bw,
        aw*bw - ax*bx - ay*by - az*bz,
    ])
