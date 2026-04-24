"""nadir_greedy.py — INTENTIONALLY FAILING reference submission.

⚠️  This planner FAILS the smear gate and should score S_orbit = 0.
    It is shipped as a negative example — read this file to understand the
    common pitfall it demonstrates.

What it does
------------
Computes the nadir-pointing attitude (imager +Z pointed at the subsatellite
point) continuously at 20 Hz, and fires a shutter every ~1 s while the
subsatellite point is inside the AOI bounding box.

Why it fails
------------
To keep the imager pointed at the moving subsatellite point, the body must
rotate at roughly the orbital angular rate:
    ω_body ≈ v_sat / r_sat ≈ 7500 / 500,000 ≈ 0.015 rad/s ≈ 0.86°/s.
That is **17× the 0.05°/s smear limit** in the problem statement. Every frame
therefore violates Section 3 / 7.5 and is discarded.

The correct EO pattern under a tight smear constraint is "stop-and-stare":
slew between targets, then HOLD inertially during each 120 ms shutter window.
See stop_and_stare.py for a reference implementation.

Dependencies: numpy, sgp4 (both pre-installed by the harness).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import numpy as np
from sgp4.api import Satrec, jday


# ------------------- constants (same as harness, kept local for portability)
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)
OMEGA_E  = 7.2921150e-5


# ------------------- helpers ------------------------------------------------
def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _gmst(dt: datetime) -> float:
    jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                  dt.second + dt.microsecond * 1e-6)
    T = ((jd - 2451545.0) + fr) / 36525.0
    gmst_sec = (67310.54841
                + (876600.0 * 3600.0 + 8640184.812866) * T
                + 0.093104 * T * T
                - 6.2e-6 * T * T * T) % 86400.0
    if gmst_sec < 0:
        gmst_sec += 86400.0
    return math.radians(gmst_sec / 240.0)


def _ecef_to_llh(r):
    x, y, z = float(r[0]), float(r[1]), float(r[2])
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - WGS84_E2))
    for _ in range(6):
        sl = math.sin(lat)
        N = WGS84_A / math.sqrt(1 - WGS84_E2 * sl * sl)
        alt = p / math.cos(lat) - N
        lat = math.atan2(z, p * (1 - WGS84_E2 * N / (N + alt)))
    sl = math.sin(lat)
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sl * sl)
    alt = p / math.cos(lat) - N
    return math.degrees(lat), math.degrees(lon), alt


def _mat_to_quat_xyzw(R: np.ndarray) -> List[float]:
    """Shepperd's method: rotation matrix -> scalar-last unit quaternion."""
    m = R
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        S = math.sqrt(tr + 1.0) * 2
        qw = 0.25 * S
        qx = (m[2, 1] - m[1, 2]) / S
        qy = (m[0, 2] - m[2, 0]) / S
        qz = (m[1, 0] - m[0, 1]) / S
    elif (m[0, 0] > m[1, 1]) and (m[0, 0] > m[2, 2]):
        S = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        qw = (m[2, 1] - m[1, 2]) / S
        qx = 0.25 * S
        qy = (m[0, 1] + m[1, 0]) / S
        qz = (m[0, 2] + m[2, 0]) / S
    elif m[1, 1] > m[2, 2]:
        S = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        qw = (m[0, 2] - m[2, 0]) / S
        qx = (m[0, 1] + m[1, 0]) / S
        qy = 0.25 * S
        qz = (m[1, 2] + m[2, 1]) / S
    else:
        S = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        qw = (m[1, 0] - m[0, 1]) / S
        qx = (m[0, 2] + m[2, 0]) / S
        qy = (m[1, 2] + m[2, 1]) / S
        qz = 0.25 * S
    q = np.array([qx, qy, qz, qw])
    return (q / np.linalg.norm(q)).tolist()


def _nadir_quat_BN(r_eci: np.ndarray, v_eci: np.ndarray) -> List[float]:
    """
    Body frame with +Z = -r_hat (nadir), +X along velocity component perpendicular
    to nadir, +Y = Z x X. Returns q_BN = R_BN -> quaternion (body->inertial).
    """
    z_body_in_N = -r_eci / np.linalg.norm(r_eci)         # +Z points at nadir (imager boresight)
    vhat = v_eci / np.linalg.norm(v_eci)
    # Make X perpendicular to Z, roughly along track.
    x_body_in_N = vhat - np.dot(vhat, z_body_in_N) * z_body_in_N
    x_body_in_N = x_body_in_N / np.linalg.norm(x_body_in_N)
    y_body_in_N = np.cross(z_body_in_N, x_body_in_N)
    # R_BN has body-axis vectors expressed in N as columns.
    R_BN = np.column_stack([x_body_in_N, y_body_in_N, z_body_in_N])
    return _mat_to_quat_xyzw(R_BN)


def _in_aoi_bbox(lat, lon, aoi) -> bool:
    lats = [p[0] for p in aoi]; lons = [p[1] for p in aoi]
    return (min(lats) <= lat <= max(lats)) and (min(lons) <= lon <= max(lons))


# ------------------- entry point -------------------------------------------
def plan_imaging(tle_line1, tle_line2, aoi_polygon_llh,
                 pass_start_utc, pass_end_utc, sc_params):
    ATT_DT      = 0.050     # 20 Hz attitude track (50 ms spacing, >= 20 ms)
    SHUTTER_DT  = 1.0       # one image per second while over AOI
    INTEG       = float(sc_params["integration_s"])

    t0 = _parse_iso(pass_start_utc)
    t1 = _parse_iso(pass_end_utc)
    T  = (t1 - t0).total_seconds()
    n  = int(math.floor(T / ATT_DT)) + 1

    sat = Satrec.twoline2rv(tle_line1, tle_line2)

    attitude = []
    shutter  = []
    last_shutter_end = -math.inf

    for i in range(n):
        t = min(i * ATT_DT, T)
        when = t0 + timedelta(seconds=t)
        jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute,
                      when.second + when.microsecond * 1e-6)
        err, r_km, v_kmps = sat.sgp4(jd, fr)
        if err != 0:
            # Fallback to identity; harness will still accept a valid structure.
            attitude.append({"t": t, "q_BN": [0.0, 0.0, 0.0, 1.0]})
            continue
        r_eci = np.asarray(r_km, float) * 1000.0
        v_eci = np.asarray(v_kmps, float) * 1000.0

        q_BN = _nadir_quat_BN(r_eci, v_eci)
        attitude.append({"t": t, "q_BN": q_BN})

        # Shutter gating: subsatellite point in AOI bbox & spacing respected.
        theta = _gmst(when)
        c, s = math.cos(-theta), math.sin(-theta)
        r_ecef = np.array([ c*r_eci[0] - s*r_eci[1],
                             s*r_eci[0] + c*r_eci[1],
                             r_eci[2] ])
        lat, lon, _ = _ecef_to_llh(r_ecef)
        if _in_aoi_bbox(lat, lon, aoi_polygon_llh):
            if t >= last_shutter_end + SHUTTER_DT and (t + INTEG) <= T:
                shutter.append({"t_start": round(t, 4), "duration": INTEG})
                last_shutter_end = t + INTEG

    return {
        "objective": "max_coverage",
        "attitude":  attitude,
        "shutter":   shutter,
        "notes":     "nadir-pointing greedy: image once/sec while over AOI bbox",
    }
