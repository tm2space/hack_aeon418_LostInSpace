"""identity_stub.py — minimum viable submission.

Returns a structurally valid schedule that takes zero images. Useful for
validating the harness plumbing (should score S_orbit = 0 cleanly).
"""
from datetime import datetime


def plan_imaging(tle_line1, tle_line2, aoi_polygon_llh,
                 pass_start_utc, pass_end_utc, sc_params):
    t0 = datetime.fromisoformat(pass_start_utc.replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(pass_end_utc.replace("Z",   "+00:00"))
    T  = (t1 - t0).total_seconds()

    attitude = [
        {"t": 0.0, "q_BN": [0.0, 0.0, 0.0, 1.0]},
        {"t": T,   "q_BN": [0.0, 0.0, 0.0, 1.0]},
    ]
    return {
        "objective": "custom:stub",
        "attitude":  attitude,
        "shutter":   [],
        "notes":     "identity attitude, no images",
    }
