"""
sgp4_utils
==========

SGP4 propagation and the frame rotations we need for scoring:

    TEME (SGP4 output)  ->  ECI/J2000   (approximate: identity within spec)
    ECI/J2000           ->  ECEF        (rotation about Z by GMST)
    ECEF                ->  LLH (WGS84) (iterative, Bowring)

We deliberately do NOT pull in astropy/skyfield to keep the harness cheap.
TEME and J2000 differ by precession/nutation (a few arcseconds at present
epoch); for a 2° FOV @ 500 km that's ~ 30 m ground error which is well
inside the 17-km footprint. If organizers need higher fidelity, swap this
module out for astropy.

All timestamps are ISO-8601 Zulu strings in the public API.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import numpy as np
from sgp4.api import Satrec, SGP4_ERRORS, jday

# --- WGS84 ---------------------------------------------------------------------
WGS84_A = 6378137.0              # semi-major axis [m]
WGS84_F = 1.0 / 298.257223563
WGS84_B = WGS84_A * (1.0 - WGS84_F)
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)

OMEGA_EARTH = 7.2921150e-5       # rad/s, sidereal rotation rate


# ------------------------------------------------------------------- time helpers
def parse_iso_utc(s: str) -> datetime:
    """Parse '2026-04-23T12:00:00Z' style timestamps (Z or +00:00)."""
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def pass_duration_s(pass_start_utc: str, pass_end_utc: str) -> float:
    return (parse_iso_utc(pass_end_utc) - parse_iso_utc(pass_start_utc)).total_seconds()


def gmst_rad(dt: datetime) -> float:
    """
    Greenwich Mean Sidereal Time (radians), Vallado 2013 eq. 3-47.
    Input must be UTC (close enough to UT1 for our purposes: ~1s -> 15" rotation).
    """
    # Julian centuries of TT since J2000; using UTC-as-TT is fine here (~70s offset).
    jd, fr = jday(dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second + dt.microsecond * 1e-6)
    T = ((jd - 2451545.0) + fr) / 36525.0
    # Seconds
    gmst_sec = (67310.54841
                + (876600.0 * 3600.0 + 8640184.812866) * T
                + 0.093104 * T * T
                - 6.2e-6 * T * T * T)
    # Wrap into [0, 86400)
    gmst_sec = gmst_sec % 86400.0
    if gmst_sec < 0:
        gmst_sec += 86400.0
    return (gmst_sec / 240.0) * math.pi / 180.0   # 1 sec = 1/240 deg


# ---------------------------------------------------------------- SGP4 wrapper
@dataclass
class OrbitSample:
    """State of the spacecraft at one time."""
    t: float                    # seconds since pass_start
    r_eci: np.ndarray           # (3,) meters, ECI/J2000 (TEME approximation)
    v_eci: np.ndarray           # (3,) m/s
    r_ecef: np.ndarray          # (3,) meters, ECEF
    lat_deg: float              # subsatellite point
    lon_deg: float
    alt_m:   float
    utc:     datetime


class Sgp4Propagator:
    """Wraps sgp4.Satrec with helpers for our fixed pass window."""

    def __init__(self, tle1: str, tle2: str):
        self.sat = Satrec.twoline2rv(tle1, tle2)

    def propagate_series(self, pass_start_utc: str, pass_end_utc: str,
                         dt_s: float = 1.0) -> List[OrbitSample]:
        """Evenly-spaced samples from start (t=0) to end (inclusive)."""
        t0 = parse_iso_utc(pass_start_utc)
        t1 = parse_iso_utc(pass_end_utc)
        duration = (t1 - t0).total_seconds()
        n = int(math.floor(duration / dt_s)) + 1
        samples: List[OrbitSample] = []
        for i in range(n):
            t = min(i * dt_s, duration)
            samples.append(self.at(t0 + timedelta(seconds=t), rel_t=t))
        return samples

    def at(self, when_utc: datetime, rel_t: float = 0.0) -> OrbitSample:
        """State at a specific UTC datetime."""
        jd, fr = jday(when_utc.year, when_utc.month, when_utc.day,
                      when_utc.hour, when_utc.minute,
                      when_utc.second + when_utc.microsecond * 1e-6)
        err, r_km, v_kmps = self.sat.sgp4(jd, fr)
        if err != 0:
            raise RuntimeError(f"SGP4 failed: code={err} ({SGP4_ERRORS.get(err, 'unknown')})")
        r_teme = np.asarray(r_km, dtype=float) * 1000.0
        v_teme = np.asarray(v_kmps, dtype=float) * 1000.0
        # TEME ~= J2000 for this harness's precision.
        r_eci, v_eci = r_teme, v_teme
        theta = gmst_rad(when_utc)
        r_ecef = _rotz(-theta) @ r_eci
        lat, lon, alt = ecef_to_llh(r_ecef)
        return OrbitSample(
            t=rel_t, r_eci=r_eci, v_eci=v_eci,
            r_ecef=r_ecef,
            lat_deg=math.degrees(lat), lon_deg=math.degrees(lon), alt_m=alt,
            utc=when_utc,
        )


# ------------------------------------------------------------------- math
def _rotz(theta: float) -> np.ndarray:
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[ c, -s, 0.],
                     [ s,  c, 0.],
                     [ 0.,  0., 1.]])


def ecef_to_llh(r_ecef: np.ndarray) -> Tuple[float, float, float]:
    """
    Bowring's iterative solution. Returns (lat_rad, lon_rad, alt_m).
    """
    x, y, z = float(r_ecef[0]), float(r_ecef[1]), float(r_ecef[2])
    lon = math.atan2(y, x)
    p = math.hypot(x, y)

    if p < 1e-3:
        # Polar: lat = +/- pi/2
        lat = math.copysign(math.pi / 2.0, z)
        alt = abs(z) - WGS84_B
        return lat, lon, alt

    # Initial guess
    lat = math.atan2(z, p * (1 - WGS84_E2))
    for _ in range(6):
        sin_lat = math.sin(lat)
        N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat * sin_lat)
        alt = p / math.cos(lat) - N
        lat_new = math.atan2(z, p * (1 - WGS84_E2 * N / (N + alt)))
        if abs(lat_new - lat) < 1e-12:
            lat = lat_new
            break
        lat = lat_new
    sin_lat = math.sin(lat)
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat * sin_lat)
    alt = p / math.cos(lat) - N
    return lat, lon, alt


def llh_to_ecef(lat_deg: float, lon_deg: float, alt_m: float = 0.0) -> np.ndarray:
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat = math.sin(lat); cos_lat = math.cos(lat)
    sin_lon = math.sin(lon); cos_lon = math.cos(lon)
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat * sin_lat)
    x = (N + alt_m) * cos_lat * cos_lon
    y = (N + alt_m) * cos_lat * sin_lon
    z = (N * (1 - WGS84_E2) + alt_m) * sin_lat
    return np.array([x, y, z])
