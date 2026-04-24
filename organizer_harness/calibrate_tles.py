"""
Calibrate TLE RAAN + pass_start so the satellite actually flies over the AOI.

Strategy: scan a grid of (RAAN, time) and find the pair minimizing the
horizontal distance between subsatellite point and the AOI centroid (for
case1) or a shifted target (case2/case3).

Prints JSON snippets to paste into configs/caseN.json.
"""
from __future__ import annotations
import math
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from basilisk_harness import sgp4_utils as s4u


TLE_TEMPLATE_L1 = "1 {satnum}U 26001{letter}   26113.50000000  .00000000  00000-0  00000-0 0  {ck:4d}"
TLE_TEMPLATE_L2 = "2 {satnum}  97.4000 {raan:8.4f} 0001000  90.0000 230.0000 15.21920000    {r:02d}"


def _tle_checksum(line_without_ck: str) -> int:
    s = 0
    for ch in line_without_ck:
        if ch.isdigit():
            s += int(ch)
        elif ch == "-":
            s += 1
    return s % 10


def build_tle(satnum: int, letter: str, raan_deg: float, revnum: int):
    l1_partial = TLE_TEMPLATE_L1.format(satnum=satnum, letter=letter, ck=0)
    l1_body = l1_partial[:68]
    ck1 = _tle_checksum(l1_body)
    l1 = l1_body + str(ck1)

    l2_body = TLE_TEMPLATE_L2.format(satnum=satnum, raan=raan_deg, r=revnum)
    l2_body = l2_body[:68]
    ck2 = _tle_checksum(l2_body)
    l2 = l2_body + str(ck2)
    return l1, l2


# Target: AOI centroid (45N, 10E). Offsets for cases in degrees of longitude.
AOI_LAT = 45.0
AOI_LON = 10.0


def cross_track_deg(lat_offset_deg: float = 0.0, lon_offset_deg: float = 0.0):
    """Haversine-ish small-angle distance in degrees (good enough for calibration)."""
    def dist(lat, lon):
        dlat = lat - (AOI_LAT + lat_offset_deg)
        dlon = (lon - (AOI_LON + lon_offset_deg) + 180) % 360 - 180
        return math.hypot(dlat, dlon * math.cos(math.radians(AOI_LAT)))
    return dist


def find_best_pass(tle1: str, tle2: str, target_dist_fn,
                    t_epoch_iso: str, scan_hours: float = 24.0,
                    dt_s: float = 30.0):
    """Return (best_utc, best_lat, best_lon, best_dist_deg)."""
    from datetime import datetime, timezone
    prop = s4u.Sgp4Propagator(tle1, tle2)
    t0 = s4u.parse_iso_utc(t_epoch_iso)
    n_steps = int(scan_hours * 3600 / dt_s)
    best = (1e9, None, None, None)
    for i in range(n_steps):
        t = t0 + timedelta(seconds=i * dt_s)
        s = prop.at(t)
        d = target_dist_fn(s.lat_deg, s.lon_deg)
        if d < best[0]:
            best = (d, t, s.lat_deg, s.lon_deg)
    return best


def calibrate_case(case_name, satnum, letter, revnum, target_offset_lon_deg):
    """
    For a given desired cross-track offset (longitude), search RAAN and time.
    We want the satellite to be at a point offset EAST of the AOI by
    target_offset_lon_deg so the imager needs to slew WEST by the corresponding
    off-nadir angle to look at the AOI.
    """
    # Scan RAAN. For each RAAN, find best pass and report closest distance.
    best_overall = (1e9, None, None, None, None)  # (d, raan, utc, lat, lon)
    for raan in [285.0 + dr for dr in range(-5, 30)]:
        l1, l2 = build_tle(satnum, letter, raan_deg=raan, revnum=revnum)
        dist_fn = cross_track_deg(lat_offset_deg=0.0,
                                  lon_offset_deg=target_offset_lon_deg)
        d, utc, lat, lon = find_best_pass(l1, l2, dist_fn,
                                          t_epoch_iso="2026-04-23T12:00:00Z",
                                          scan_hours=24.0, dt_s=30.0)
        if d < best_overall[0]:
            best_overall = (d, raan, utc, lat, lon)

    # Refine RAAN on a tighter grid around the best.
    d, raan_c, utc_c, lat_c, lon_c = best_overall
    for raan in [raan_c + 0.1 * k for k in range(-20, 21)]:
        l1, l2 = build_tle(satnum, letter, raan_deg=raan, revnum=revnum)
        dist_fn = cross_track_deg(lat_offset_deg=0.0,
                                  lon_offset_deg=target_offset_lon_deg)
        d, utc, lat, lon = find_best_pass(l1, l2, dist_fn,
                                          t_epoch_iso="2026-04-23T12:00:00Z",
                                          scan_hours=24.0, dt_s=15.0)
        if d < best_overall[0]:
            best_overall = (d, raan, utc, lat, lon)

    d, raan, utc, lat, lon = best_overall
    # Build a 12-minute pass window centered on the closest-approach time.
    pass_start = utc - timedelta(seconds=360)
    pass_end   = utc + timedelta(seconds=360)
    l1, l2 = build_tle(satnum, letter, raan_deg=raan, revnum=revnum)
    print(f"=== {case_name} ===")
    print(f"  target offset = {target_offset_lon_deg:+.2f} deg lon from AOI")
    print(f"  best RAAN     = {raan:.4f} deg")
    print(f"  closest pt    = ({lat:+.3f}, {lon:+.3f})  dist={d:.3f} deg")
    print(f"  closest utc   = {utc.isoformat()}")
    print(f"  pass_start    = {pass_start.isoformat().replace('+00:00','Z')}")
    print(f"  pass_end      = {pass_end.isoformat().replace('+00:00','Z')}")
    print(f"  TLE:")
    print(f"    {l1}")
    print(f"    {l2}")
    print()
    return {
        "raan": raan, "utc": utc, "l1": l1, "l2": l2,
        "pass_start": pass_start.isoformat().replace("+00:00", "Z"),
        "pass_end":   pass_end.isoformat().replace("+00:00", "Z"),
    }


if __name__ == "__main__":
    # Case 1: sat directly above AOI (offset = 0)
    calibrate_case("CASE 1 — direct", 99991, "A", revnum=5,
                   target_offset_lon_deg=0.0)
    # Case 2: 30 deg off-nadir ~ 293 km cross-track = 3.72 deg lon at 45N
    calibrate_case("CASE 2 — ~30 deg off-nadir", 99992, "B", revnum=6,
                   target_offset_lon_deg=-3.72)   # sat to the WEST, AOI to the east
    # Case 3: 60 deg off-nadir ~ 1009 km cross-track = 12.8 deg lon at 45N
    calibrate_case("CASE 3 — ~60 deg off-nadir", 99993, "C", revnum=7,
                   target_offset_lon_deg=-12.8)
