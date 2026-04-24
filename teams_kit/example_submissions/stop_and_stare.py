"""stop_and_stare.py — correct reference submission.

Strategy
--------
Proper EO imaging pattern for the 0.05 deg/s smear constraint:

  1. Between shutter windows: SLEW to pre-aim at the next target
  2. During each shutter window: HOLD inertially (body rate = 0)
  3. Repeat

Attitude schedule has two kinds of samples:
  * "slew backbone"  -- coarse (1 Hz) samples SLERPing between consecutive
                        stare orientations; body rotates during these
  * "stare brackets" -- at t_start and t_start+integration we pin the SAME
                        quaternion, so interpolation during the window has
                        zero body rate and the smear gate passes

The target is the AOI centroid.

This is a reference. It leaves lots of optimization on the table:
  * smarter sub-target sequences to cover more of the AOI than just its centroid
  * skipping impossible frames (off-nadir > 60 deg) earlier
  * pre-settling before shutter instead of arriving exactly at t_start

Dependencies: numpy, sgp4.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import List

import numpy as np
from sgp4.api import Satrec, jday


# ---- WGS84 ----------------------------------------------------------------
WGS84_A  = 6378137.0
WGS84_F  = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)


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


def _llh_to_ecef(lat_deg, lon_deg, alt_m=0.0):
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    sl, cl = math.sin(lat), math.cos(lat)
    ss, cs = math.sin(lon), math.cos(lon)
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sl * sl)
    return np.array([(N + alt_m) * cl * cs,
                     (N + alt_m) * cl * ss,
                     (N * (1 - WGS84_E2) + alt_m) * sl])


def _ecef_to_eci(r_ecef: np.ndarray, gmst: float) -> np.ndarray:
    c, s = math.cos(gmst), math.sin(gmst)
    return np.array([c * r_ecef[0] - s * r_ecef[1],
                     s * r_ecef[0] + c * r_ecef[1],
                     r_ecef[2]])


def _mat_to_quat_xyzw(m: np.ndarray) -> List[float]:
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


def _stare_quat_BN(r_sat_eci: np.ndarray, r_tgt_eci: np.ndarray,
                    v_sat_eci: np.ndarray) -> List[float]:
    """Body -> Inertial quaternion aiming +Z (imager) at r_tgt_eci."""
    z_body_in_N = r_tgt_eci - r_sat_eci
    z_body_in_N = z_body_in_N / np.linalg.norm(z_body_in_N)
    vhat = v_sat_eci / np.linalg.norm(v_sat_eci)
    x_body_in_N = vhat - np.dot(vhat, z_body_in_N) * z_body_in_N
    nrm = np.linalg.norm(x_body_in_N)
    if nrm < 1e-6:
        arbitrary = np.array([1.0, 0.0, 0.0])
        x_body_in_N = arbitrary - np.dot(arbitrary, z_body_in_N) * z_body_in_N
        nrm = np.linalg.norm(x_body_in_N)
    x_body_in_N = x_body_in_N / nrm
    y_body_in_N = np.cross(z_body_in_N, x_body_in_N)
    return _mat_to_quat_xyzw(np.column_stack([x_body_in_N, y_body_in_N, z_body_in_N]))


def _sat_state(sat: Satrec, when: datetime):
    jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute,
                  when.second + when.microsecond * 1e-6)
    err, r_km, v_kmps = sat.sgp4(jd, fr)
    if err != 0:
        return None, None
    return (np.asarray(r_km, float) * 1000.0,
            np.asarray(v_kmps, float) * 1000.0)


# -------------------------- entry point ------------------------------------
def plan_imaging(tle_line1, tle_line2, aoi_polygon_llh,
                 pass_start_utc, pass_end_utc, sc_params):
    SLEW_DT      = 1.0      # coarse 1 Hz backbone between shutters
    SHUTTER_GAP  = 2.0      # at least 2s between shutter window starts
    INTEG        = float(sc_params["integration_s"])
    OFF_NADIR_MAX = float(sc_params["off_nadir_max_deg"])

    # Target: AOI centroid.
    if len(aoi_polygon_llh) > 1 and aoi_polygon_llh[0] == aoi_polygon_llh[-1]:
        verts = aoi_polygon_llh[:-1]
    else:
        verts = aoi_polygon_llh
    tgt_lat = sum(p[0] for p in verts) / len(verts)
    tgt_lon = sum(p[1] for p in verts) / len(verts)
    r_tgt_ecef = _llh_to_ecef(tgt_lat, tgt_lon, 0.0)

    t0 = _parse_iso(pass_start_utc)
    t1 = _parse_iso(pass_end_utc)
    T  = (t1 - t0).total_seconds()
    sat = Satrec.twoline2rv(tle_line1, tle_line2)

    # ---- 1. Build the slew backbone (1 Hz) -----------------------------------
    # Each sample = stare orientation at that exact instant.
    backbone = []   # list of (t, q_BN)
    n_bb = int(math.floor(T / SLEW_DT)) + 1
    for i in range(n_bb):
        t = min(i * SLEW_DT, T)
        when = t0 + timedelta(seconds=t)
        r_eci, v_eci = _sat_state(sat, when)
        if r_eci is None:
            backbone.append((t, [0.0, 0.0, 0.0, 1.0]))
            continue
        r_tgt_eci = _ecef_to_eci(r_tgt_ecef, _gmst(when))
        q = _stare_quat_BN(r_eci, r_tgt_eci, v_eci)
        backbone.append((t, q))

    # ---- 2. Decide shutter times, only where off-nadir is within limits -----
    shutter_times: List[float] = []
    last_end = -math.inf
    for (t, _q) in backbone:
        # Quick off-nadir check at this backbone instant.
        when = t0 + timedelta(seconds=t)
        r_eci, _v = _sat_state(sat, when)
        if r_eci is None:
            continue
        r_tgt_eci = _ecef_to_eci(r_tgt_ecef, _gmst(when))
        los = r_tgt_eci - r_eci
        los /= np.linalg.norm(los)
        nadir = -r_eci / np.linalg.norm(r_eci)
        off_nadir = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(los, nadir))))))
        if off_nadir > OFF_NADIR_MAX - 1.0:       # 1 deg margin
            continue
        if t >= last_end + SHUTTER_GAP and (t + INTEG + 0.050) <= T:
            shutter_times.append(t)
            last_end = t + INTEG

    # ---- 3. Build the attitude schedule -------------------------------------
    # Backbone samples, but for each shutter window we OVERRIDE with two
    # identical quaternions at t_start and t_start+INTEG (body rate = 0 during).
    # Hold the quaternion a bit BEFORE and AFTER the shutter so the scorer's
    # finite-difference body-rate estimate is flat across the whole window.
    HOLD_PAD = 0.15   # 150 ms pre- and post-settle
    override_pts: List[tuple] = []   # (t, q)
    for ts in shutter_times:
        when = t0 + timedelta(seconds=ts)
        r_eci, v_eci = _sat_state(sat, when)
        if r_eci is None:
            continue
        r_tgt_eci = _ecef_to_eci(r_tgt_ecef, _gmst(when))
        q = _stare_quat_BN(r_eci, r_tgt_eci, v_eci)
        t_hold_start = max(0.0, ts - HOLD_PAD)
        t_hold_end   = min(T,   ts + INTEG + HOLD_PAD)
        # Dense, identical samples straddling the shutter.
        override_pts.append((t_hold_start, q))
        override_pts.append((ts,           q))
        override_pts.append((ts + INTEG,   q))
        override_pts.append((t_hold_end,   q))

    # Merge backbone + overrides. We skip backbone samples that fall INSIDE
    # any held region (those would disturb the hold).
    def _inside_hold(t):
        for ts in shutter_times:
            if ts - HOLD_PAD - 1e-6 <= t <= ts + INTEG + HOLD_PAD + 1e-6:
                return True
        return False

    def _inside_shutter(t):
        return _inside_hold(t)

    merged = [(t, q) for (t, q) in backbone if not _inside_shutter(t)]
    merged.extend(override_pts)
    merged.sort(key=lambda x: x[0])

    # Enforce min spacing 20 ms by dropping samples that are too close.
    cleaned = []
    for (t, q) in merged:
        if cleaned and t - cleaned[-1][0] < 0.020:
            continue
        cleaned.append((t, q))

    # Validator requires first sample at t=0 and last >= last shutter end.
    if cleaned[0][0] > 1e-9:
        cleaned.insert(0, (0.0, cleaned[0][1]))
    t_need = (shutter_times[-1] + INTEG) if shutter_times else T
    if cleaned[-1][0] < t_need - 1e-9:
        cleaned.append((t_need, cleaned[-1][1]))

    attitude = [{"t": round(t, 4), "q_BN": list(q)} for (t, q) in cleaned]
    shutter  = [{"t_start": round(ts, 4), "duration": INTEG} for ts in shutter_times]

    return {
        "objective": "max_coverage",
        "attitude":  attitude,
        "shutter":   shutter,
        "notes":     f"stop-and-stare at AOI centroid ({tgt_lat:.3f}, {tgt_lon:.3f}); "
                     f"{len(shutter)} shots, 1 Hz slew backbone, hold during integration",
    }
