"""
basilisk_harness
================

Organizer-side evaluation harness for the Lost in Space Track hackathon.

Runs a team's submission.plan_imaging() against three test cases, drives a
Basilisk simulation with the returned schedule, and computes S_orbit.

Entry points
------------
- run_one_case(case_id, submission_path) -> dict
- run_all(submission_path, cases=('case1','case2','case3')) -> dict
- StructuralValidator.validate(schedule) -> list[str]   # errors
- AoiScorer(cfg).evaluate(schedule, telemetry) -> dict

Modules
-------
config              Pass configuration loader (AOI + TLE + sc_params)
schedule_validator  Fast structural validation of the submitted dict
sgp4_utils          TLE -> ECI / ECEF state (SGP4 + TEME->J2000 + GMST)
geometry            Footprint projection, polygon ops, coverage accumulation
scorer              AoiScorer: produces S_orbit = C * (1+a*eE+b*eT) * Q_smear
mock_sim            Lightweight rigid-body + RW sim (no Basilisk required)
basilisk_sim        Basilisk-based SpacecraftSim (requires Basilisk install)
harness             Top-level: timeout-guarded import, validate, sim, score
"""

from .schedule_validator import StructuralValidator, ValidationError
from .config import PassConfig, load_pass_config
from .scorer import AoiScorer, OrbitScore

__all__ = [
    "StructuralValidator", "ValidationError",
    "PassConfig", "load_pass_config",
    "AoiScorer", "OrbitScore",
]

__version__ = "0.1.0"
