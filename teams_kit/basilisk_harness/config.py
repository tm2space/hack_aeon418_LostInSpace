"""
Pass configuration: everything needed to run and score one test case.

A PassConfig is exactly the bundle that gets handed to the team's
plan_imaging() call (minus the Python spacecraft-parameter dict, which is
derived here too) and to the AoiScorer.

The three shipped configs are in basilisk_harness/../configs/ as JSON so
organizers can tweak TLEs / AOIs / epoch without touching code.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

# --- spacecraft parameters (fixed across all cases per the problem statement) --
DEFAULT_SC_PARAMS: Dict[str, Any] = {
    "inertia_kgm2":         [[0.12, 0.0,  0.0],
                              [0.0,  0.12, 0.0],
                              [0.0,  0.0,  0.08]],
    "wheel_layout":         "pyramid_45deg",
    "wheel_Hmax_Nms":       0.030,
    "n_wheels":             4,
    "integration_s":        0.120,
    "fov_deg":              [2.0, 2.0],
    "imager_boresight_B":   [0.0, 0.0, 1.0],
    "smear_rate_limit_dps": 0.05,
    "off_nadir_max_deg":    60.0,
    "earth_model":          "WGS84",
    "eci_frame":            "J2000",
}

# Case weights in the final S_total
CASE_WEIGHTS: Dict[str, float] = {"case1": 0.25, "case2": 0.35, "case3": 0.40}

# Budgets that feed the scorer's efficiency terms.
DELTA_H_BUDGET_NMS = 0.200  # 200 mNms per pass


@dataclass
class PassConfig:
    """One scored pass — loaded from configs/<case_id>.json."""
    case_id:        str
    tle1:           str
    tle2:           str
    aoi_polygon:    List[Tuple[float, float]]   # [(lat_deg, lon_deg), ...] closed
    pass_start:     str                          # ISO-8601 Zulu
    pass_end:       str                          # ISO-8601 Zulu
    sc_params:      Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_SC_PARAMS))
    description:    str = ""

    # Scoring knobs (per pass). Kept in config so organizers can tune without code edits.
    alpha:          float = 0.25   # control-effort reward weight
    beta:           float = 0.10   # time-efficiency reward weight
    delta_h_budget: float = DELTA_H_BUDGET_NMS

    def case_weight(self) -> float:
        return CASE_WEIGHTS.get(self.case_id, 0.0)


# ------------------------------------------------------------------------ loader
def _configs_dir() -> Path:
    # configs/ is a sibling of basilisk_harness/.
    return Path(__file__).resolve().parent.parent / "configs"


def load_pass_config(case_id: str, configs_dir: Path | None = None) -> PassConfig:
    """Load case1/case2/case3 from JSON."""
    d = Path(configs_dir) if configs_dir else _configs_dir()
    path = d / f"{case_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Pass config not found: {path}")

    with open(path) as f:
        data = json.load(f)

    # Merge provided sc_params over the default (per-case overrides allowed).
    sc_params = dict(DEFAULT_SC_PARAMS)
    sc_params.update(data.get("sc_params_overrides") or {})

    return PassConfig(
        case_id     = case_id,
        tle1        = data["tle1"],
        tle2        = data["tle2"],
        aoi_polygon = [tuple(p) for p in data["aoi_polygon"]],
        pass_start  = data["pass_start"],
        pass_end    = data["pass_end"],
        sc_params   = sc_params,
        description = data.get("description", ""),
        alpha       = float(data.get("alpha", 0.25)),
        beta        = float(data.get("beta", 0.10)),
        delta_h_budget = float(data.get("delta_h_budget", DELTA_H_BUDGET_NMS)),
    )
