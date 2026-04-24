# Lost in Space Track — Organizer Harness

Automated grader for the Lost in Space Track hackathon. Loads a team's
`plan_imaging()` function, drives it through a Basilisk spacecraft
simulation for three pre-defined passes, and produces a score.

```
submission.py ──▶ plan_imaging() ─── schedule ───▶ Basilisk sim ───▶ AOI scorer ───▶ S_orbit
                   (120 s budget)    (validated)    (6-DoF + RWs)    (coverage+effort)
```

## Layout

```
harness/
├── basilisk_harness/          the Python package (import as `basilisk_harness`)
│   ├── __init__.py
│   ├── config.py              PassConfig dataclass, JSON loader
│   ├── schedule_validator.py  structural gate (runs before sim)
│   ├── sgp4_utils.py          SGP4 + WGS84 + GMST
│   ├── geometry.py            footprint projection + coverage accumulator
│   ├── scorer.py              AoiScorer -> OrbitScore
│   ├── mock_sim.py            physics-lite simulator (no Basilisk needed)
│   ├── basilisk_sim.py        real Basilisk simulator
│   └── harness.py             top-level orchestration + subprocess timeout
├── configs/
│   ├── case1.json             direct overpass     (~0 deg off-nadir)
│   ├── case2.json             30 deg off-nadir    (~293 km cross-track)
│   └── case3.json             60 deg off-nadir    (~1009 km cross-track)
├── example_submissions/
│   ├── identity_stub.py       structural scaffold (S = 0 but valid)
│   ├── nadir_greedy.py        negative example — fails smear gate by design
│   └── stop_and_stare.py      correct baseline (~0.15 S_total)
├── tests/
│   └── test_validator.py
├── calibrate_tles.py          one-off helper used to pick RAAN + pass_start
├── run_evaluation.py          CLI entry point
└── requirements.txt
```

## Install

```bash
# Base deps
pip install -r requirements.txt

# Basilisk — follow upstream build instructions at
#   https://hanspeterschaub.info/basilisk
# The harness falls back to mock_sim if Basilisk is missing, but the real
# sim is required for leaderboard scores.
```

## Quick start

```bash
# Validator sanity check
python tests/test_validator.py

# Dry-run a team submission without Basilisk (mock physics)
python run_evaluation.py --submission example_submissions/stop_and_stare.py --all --mock -v

# Real scored run (requires Basilisk)
python run_evaluation.py --submission path/to/team_submission.py --all --json scores.json
```

## Running one case only

```bash
python run_evaluation.py --submission path/to/team_submission.py --case case1 -v
```

## What the harness does to a submission

1. **Sandbox-import** `submission.py` in a fresh `spawn` subprocess.
2. **Call** `plan_imaging(tle1, tle2, aoi_polygon_llh, pass_start, pass_end, sc_params)`
   under a 120 s wall-clock budget (enforced with SIGTERM/SIGKILL).
3. **Structural validate** the returned dict (keys, types, quaternion norms,
   shutter durations, attitude spacing). Malformed → S_orbit = 0.
4. **Simulate** in Basilisk (or mock_sim) with the schedule as the attitude
   reference. The sim integrates 6-DoF rigid-body dynamics with a 4-wheel
   pyramidal RW cluster at 45° cant.
5. **Score** with `AoiScorer`:
   ```
   S_orbit = C · (1 + α·η_E + β·η_T) · Q_smear
   ```
   where frames are gated per Section 3 / 7.5 of the problem statement
   (wheel saturation, smear rate, off-nadir limit).

## Scoring configuration

All three cases default to: α = 0.25, β = 0.10, ΔH_budget = 0.200 Nms.
Override per-case in `configs/caseN.json`. Weights for `S_total`:

|         | weight |
| ------- | ------ |
| case 1  | 0.25   |
| case 2  | 0.35   |
| case 3  | 0.40   |

## Basilisk version-sensitive bits

Search `basilisk_sim.py` for `BSK-VERIFY:` comments. Those flag places
where module names / message-payload field names have shifted across
Basilisk releases. The file targets Basilisk ≥ 2.2 (post-module-rename).
You may need to patch imports (e.g. `mrpFeedback` vs `MRP_Feedback`,
`spacecraft` vs `spacecraftPlus`, message naming) to match your install.

If a Basilisk run throws during `sim.ExecuteSimulation()`, run with
`--mock` first to verify scoring works, then debug the Basilisk wiring in
isolation.

## Rescoring after config changes

If you tweak TLEs or the AOI, regenerate pass windows with:

```bash
python calibrate_tles.py
```

This scans RAAN × time grid to find actual passes over the AOI centroid
(and the two offset targets) and prints updated TLE+pass-window pairs.
Paste the result into `configs/caseN.json`.

## Leaderboard pipeline suggestion

```bash
for submission in submissions/*.py; do
    team=$(basename "$submission" .py)
    python run_evaluation.py --submission "$submission" --all \
        --json "results/$team.json" 2>&1 | tee "logs/$team.log"
done
python aggregate_leaderboard.py results/   # your own roll-up script
```

The JSON output contains per-case breakdowns (C, η_E, η_T, Q_smear, frame
reject counts) so you can publish sub-leaderboards for "best coverage",
"best energy efficiency", etc.

## Known limitations

- **mock_sim** treats the commanded attitude as perfectly tracked and
  derives body rates from the numerical derivative of the command. Use it
  for plumbing tests only. Real RW dynamics, friction, and tracking lag
  come from `basilisk_sim`.
- **TEME ≈ J2000** approximation in `sgp4_utils` introduces ~30 m ground
  error for 2° FOV at 500 km — well inside a single pixel for most EO
  imagers. Swap in astropy or skyfield if you need higher fidelity.
- **Frame conventions** are pinned to body→ECI scalar-last quaternions.
  If your Basilisk install uses different conventions in `AttRefMsg`,
  adjust `basilisk_sim._ScheduleAttRefModule` accordingly.

## License / distribution

Internal use for the hackathon. Do not redistribute team submissions
without permission.
