# Lost in Space Track — Problem Statement

> **Hackathon Problem Statement** — Earth-Observation Attitude & Imaging Scheduling
>
> 📄 For offline / print: [PROBLEM_STATEMENT.pdf](./PROBLEM_STATEMENT.pdf) · 📝 Editable: [PROBLEM_STATEMENT.docx](./PROBLEM_STATEMENT.docx)

| | |
|---|---|
| **Track**       | Lost in Space — Autonomous EO Tasking |
| **Deliverable** | One Python file exporting `plan_imaging(...)` + a 2-minute presentation |
| **Test cases**  | 3 orbits (0°, 30°, 60° cross-track offset from AOI) |
| **Judging**     | Presentations first, then code verification for the top 3 |

---

## 1. Scenario

A small Earth-observation satellite is in a low Earth orbit and will pass near a fixed rectangular Area of Interest (AOI) on the ground. The satellite carries a single staring imager fixed to the **+Z body axis**. The only way to aim the imager is to slew the spacecraft body using its reaction wheels.

Participants must design a **slew and imaging scheduling algorithm** that decides *what to image, when, and in which body attitude* during each pass — subject to the physical limits of the ACS.

Your algorithm will be wrapped into a **Basilisk** spacecraft simulation on the organizers' side and executed over three pre-defined passes (TLEs in [Section 8](#8-test-orbits-tles)). The simulator produces the score automatically. See [Section 9](#9-deliverables-and-judging) for the judging flow.

## 2. Spacecraft Specifications

| Parameter | Value |
|---|---|
| Imager boresight | +Z body axis |
| Integration time per image | 120 ms (ground footprint must be stable during this window) |
| Reaction wheels | 4 wheels in a 45° pyramidal configuration (cant = 45° from +Z; azimuths 0°, 90°, 180°, 270°) |
| Per-wheel momentum capacity | 30 mNms |
| Body momentum envelope (X, Y) | ≈ √2 · 30 = 42.4 mNms |
| Body momentum envelope (Z) | ≈ 2√2 · 30 = 84.9 mNms |
| Spacecraft inertia (assumed) | diag(0.12, 0.12, 0.08) kg·m² |
| Orbit altitude (nominal) | ≈ 500 km, sun-synchronous |
| Imager FOV (assumed) | 2.0° × 2.0° (≈ 17 × 17 km at nadir from 500 km) |

> *Slew dynamics follow H_body = I·ω + H_wheels. Wheels are momentum-limited (no desaturation thrusters during a pass). Treat inertia and wheel layout as fixed; do not attempt to modify the plant in the simulator.*

## 3. Operational Constraints

- **Smear constraint during integration:** body rate magnitude `|ω_body| ≤ 0.05°/s` continuously for the full 120 ms window of any valid image.
- **Off-nadir limit:** maximum pointing angle from nadir ≤ 60°.
- **Wheel saturation:** at no time may any single wheel exceed its 30 mNms momentum limit.
- **Imager FOV:** fixed at 2.0° × 2.0° for all teams and all three test cases.
- **Pass window:** each test case is a 12-minute window bracketing closest approach of the satellite to the AOI (see [Section 8](#8-test-orbits-tles)).

## 4. The Task

Design and implement a Python function that, given a propagated ephemeris (from the supplied TLE) and the AOI geometry, produces a time-tagged attitude and imaging schedule. Your function will be called by the organizers' Basilisk harness; the exact interface is specified in [Section 7](#7-what-you-submit).

Teams are free to choose **what they optimize**. Examples:

- **Maximize AOI coverage** (greedy or globally-planned mosaicking).
- **Minimize control effort** (∫|τ·ω| dt, or total Δh across wheels).
- **Minimize mission time** used within the pass.
- **Robustness-weighted coverage** (same plan performs well across all three geometries).

Explain your chosen objective and strategy in your 2-minute presentation. You can also tag it in the `schedule["objective"]` field for the record ([Section 7.3](#73--return-value-the-schedule-dict)), but the presentation is what the judges score.

## 5. Scoring Metric (Automated)

Each of the three test orbits is scored independently by the Basilisk harness, then combined. Per-orbit score:

```
S_orbit  =  C · (1 + α·η_E + β·η_T) · Q_smear
```

| Symbol | Meaning |
|---|---|
| **C**       | Fraction of AOI area imaged with valid, non-smeared frames (0–1). |
| **η_E**     | Control-effort efficiency = 1 − ΔH_used / ΔH_budget, clipped to [0,1]. ΔH_budget = 200 mNms per pass. |
| **η_T**     | Time efficiency = 1 − T_active / T_pass, where T_active is cumulative slew+image time. |
| **Q_smear** | Smear quality factor: 1.0 if all kept frames meet the rate constraint; linearly penalized down to 0 based on fraction of frames violating it. |
| **α, β**    | Reward weights: α = 0.25, β = 0.10. |

**Total score** across all three test cases:

```
S_total  =  0.25 · S_case1  +  0.35 · S_case2  +  0.40 · S_case3
```

Case 3 (60° offset) is the hardest and is weighted highest.

> **Hard disqualifiers for a frame** (frame is discarded and counts as non-imaged area):
> 1. Wheel saturation (any wheel |H_i| > 30 mNms during the window)
> 2. Off-nadir > 60°
> 3. Smear rate exceeded during the 120 ms integration

## 6. Area of Interest

A rectangular AOI in the Po Valley, northern Italy (chosen for a convenient mid-latitude SSO pass geometry). The same AOI is used for all three test cases — only the satellite ground-track offset changes.

| Corner | Latitude | Longitude |
|---|---|---|
| SW | 44.55° N | 9.37° E |
| SE | 44.55° N | 10.63° E |
| NE | 45.45° N | 10.63° E |
| NW | 45.45° N | 9.37° E |
| Center (reference) | 45.00° N | 10.00° E |

**Approximate dimensions:** ~100 km (E–W) × ~100 km (N–S) ≈ 10,000 km². The AOI is supplied to your function as a polygon (see [Section 7](#7-what-you-submit)).

## 7. What You Submit

You submit **exactly one Python file** that exports a function named `plan_imaging(...)` with the signature in [Section 7.1](#71--entry-point-signature). Name the file anything you like — the grader imports the function by name. No zip, no folder structure, no accompanying documents.

The organizers run a Basilisk-based simulation on their end. The grader imports your file, calls `plan_imaging` once per test case, and passes the returned schedule to a Basilisk attitude controller that tracks it.

### 7.1  Entry-point signature

Your file must export exactly this function, with exactly this signature (the grader imports it by name):

```python
# Any filename; exports plan_imaging(...) at module top level.
# Pre-installed dependencies: numpy, scipy, sgp4. Do not rely on anything else.

from typing import List, Dict, Any, Tuple

def plan_imaging(tle_line1:       str,
                 tle_line2:       str,
                 aoi_polygon_llh: List[Tuple[float, float]],
                 pass_start_utc:  str,
                 pass_end_utc:    str,
                 sc_params:       Dict[str, Any]
                 ) -> Dict[str, Any]:
    """
    Compute an attitude + imaging schedule for ONE pass.

    Parameters
    ----------
    tle_line1, tle_line2 : str
        Standard two-line element set. Propagate with SGP4
        (sgp4.api.Satrec.twoline2rv) in the TEME frame, then rotate to
        ECI/J2000 before reasoning about attitude.

    aoi_polygon_llh : list of (lat_deg, lon_deg)
        Closed polygon defining the AOI on the WGS-84 ellipsoid. The first
        and last vertices are equal.

    pass_start_utc, pass_end_utc : str
        ISO-8601 Zulu timestamps bounding the scored pass window
        (e.g. "2026-04-23T17:24:00Z"). All 't' values in your returned
        schedule are SECONDS relative to pass_start_utc.

    sc_params : dict
        Spacecraft parameters -- see Section 7.2.

    Returns
    -------
    schedule : dict
        See Section 7.3 for the exact required structure.
    """
    ...
    return schedule
```

### 7.2  `sc_params` dictionary (passed in by the grader)

```python
sc_params = {
    "inertia_kgm2":   [[0.12, 0.0,  0.0 ],
                       [0.0,  0.12, 0.0 ],
                       [0.0,  0.0,  0.08]],

    "wheel_layout":   "pyramid_45deg",       # 4 RWs, 45° cant, azimuths 0/90/180/270
    "wheel_Hmax_Nms": 0.030,                 # 30 mNms per wheel
    "n_wheels":       4,

    "integration_s":        0.120,           # shutter dwell -- IMMUTABLE
    "fov_deg":              [2.0, 2.0],      # cross-track, along-track
    "imager_boresight_B":   [0.0, 0.0, 1.0], # +Z in body frame

    "smear_rate_limit_dps": 0.05,            # deg/s, on |omega_body|
    "off_nadir_max_deg":    60.0,

    "earth_model":    "WGS84",
    "eci_frame":      "J2000",
}
```

### 7.3  Return value: the `schedule` dict

Your function must return a dictionary with exactly the following keys. The grader validates structure before the simulation runs; malformed schedules fail the test case with `S_orbit = 0`.

```python
schedule = {

    # --- 1. Declared objective (string, diagnostic only) ------------
    "objective": "max_coverage",

    # --- 2. Attitude command trajectory -----------------------------
    # Ordered list, strictly monotonic in 't' (seconds from
    # pass_start_utc). The grader SLERPs between samples.
    #
    # Quaternion convention: q_BN maps BODY -> INERTIAL (ECI, J2000),
    # SCALAR-LAST ordering  [qx, qy, qz, qw], unit-norm.
    # Rule of thumb: 10-50 Hz; minimum 20 ms between samples.
    # First sample MUST be at t = 0.0. Last sample MUST be at or after
    # the last shutter window's end time.
    "attitude": [
        {"t": 0.000,  "q_BN": [0.0, 0.0, 0.0, 1.0]},
        {"t": 0.020,  "q_BN": [qx,  qy,  qz,  qw ]},
        # ...
        {"t": T_end,  "q_BN": [qx,  qy,  qz,  qw ]},
    ],

    # --- 3. Shutter command list ------------------------------------
    # Each window MUST be exactly 0.120 s long. Windows MUST NOT
    # overlap and MUST be in ascending t_start order. t_start is
    # seconds from pass_start_utc.
    "shutter": [
        {"t_start": 12.340, "duration": 0.120},
        {"t_start": 13.800, "duration": 0.120},
        # ...
    ],

    # --- 4. Optional diagnostics (logged, not scored) ---------------
    "notes": "Greedy sweep from NW to SE; 1 Hz replan.",

    # --- 5. Optional per-frame target hints (logged, not scored) ----
    "target_hints_llh": [
        {"lat_deg": 45.10, "lon_deg": 9.80},
        # ...
    ],
}
```

### 7.4  Hard rules on the function

- **Single file.** One `.py` file exporting `plan_imaging` at module top level. No imports from other files you wrote.
- **Pure and deterministic.** Given the same inputs, return the same schedule. No network calls, no reading files, no wall-clock or randomness without a fixed seed.
- **Wall-clock budget:** the function must return within **120 seconds per test case**. Exceeding the budget fails the case.
- **Allowed dependencies:** `numpy`, `scipy`, `sgp4`. Nothing else is guaranteed to be present. Do not import Basilisk — the grader owns the simulator.
- **Quaternion convention:** body-to-inertial (ECI J2000), scalar-last `(x, y, z, w)`, unit-normalised.
- **Time base:** all `t` values are seconds from `pass_start_utc`. First attitude sample at `t = 0`; last at or after the final shutter window end.
- **Shutter windows** must be exactly 0.120 s and must not overlap.
- **Attitude sample density:** ≥ 20 ms spacing, ≤ 50 Hz. The grader will reject schedules with sub-20-ms spacing.

### 7.5  Exact grader call (what runs on the organizers' side)

For full transparency, this is the exact invocation your function will see on the evaluation server:

```python
# organizer-side grader (abridged)
import importlib.util, time
from basilisk_harness import SpacecraftSim, AoiScorer, load_pass_config

def run_one_case(case_id: str, submission_path: str):
    cfg = load_pass_config(case_id)

    # Import the team's single .py by path and grab plan_imaging.
    spec = importlib.util.spec_from_file_location("submission", submission_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    t0 = time.perf_counter()
    schedule = mod.plan_imaging(
        tle_line1       = cfg.tle1,
        tle_line2       = cfg.tle2,
        aoi_polygon_llh = cfg.aoi_polygon,
        pass_start_utc  = cfg.pass_start,
        pass_end_utc    = cfg.pass_end,
        sc_params       = cfg.sc_params,
    )
    assert time.perf_counter() - t0 <= 120.0, "planning budget exceeded"

    sim = SpacecraftSim(cfg)
    telemetry = sim.run(schedule)
    return AoiScorer(cfg).evaluate(schedule, telemetry)
```

### 7.6  Minimum viable stub (copy-paste starting point)

A schedule that does nothing but satisfies the structural contract — use this as your scaffold. This submission earns `S_orbit = 0` because it takes no images, but it passes the structural validator.

```python
# my_submission.py -- minimum viable stub
def plan_imaging(tle_line1, tle_line2, aoi_polygon_llh,
                 pass_start_utc, pass_end_utc, sc_params):

    from datetime import datetime
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
        "notes":     "structural stub; replace with a real planner",
    }
```

## 8. Test Orbits (TLEs)

Three SSO satellites at ≈ 500 km, inclination 97.4°, differing only in RAAN to create cross-track offsets at the AOI latitude. Common epoch: 2026-04-23 12:00 UTC. Propagate with SGP4. Your `plan_imaging` function receives both TLE lines directly.

**Scored pass window (all three cases):** `2026-04-23T17:24:00Z` to `2026-04-23T17:36:00Z` — 12 minutes bracketing closest approach.

**Case 1 — Direct overpass (ground track through AOI center, ~0° off-nadir):**

```
LOSTINSPACE-A
1 99991U 26001A   26113.50000000  .00000000  00000-0  00000-0 0     7
2 99991  97.4000 296.7000 0001000  90.0000 230.0000 15.21920000    08
```

**Case 2 — ~30° off-nadir (≈ 293 km cross-track offset):**

```
LOSTINSPACE-B
1 99992U 26001B   26113.50000000  .00000000  00000-0  00000-0 0     8
2 99992  97.4000 292.9000 0001000  90.0000 230.0000 15.21920000    07
```

**Case 3 — ~60° off-nadir (≈ 1009 km cross-track offset):**

```
LOSTINSPACE-C
1 99993U 26001C   26113.50000000  .00000000  00000-0  00000-0 0     9
2 99993  97.4000 283.9000 0001000  90.0000 230.0000 15.21920000    08
```

> **Note:** case 3 places the satellite near the 60° off-nadir limit when aimed at the AOI centroid — some AOI corners may be physically unreachable within the pointing envelope. That is intentional and is why case 3 is weighted highest.

## 9. Deliverables and Judging

You deliver exactly two things:

- **One `.py` file** exporting `plan_imaging(...)` per [Section 7](#7-what-you-submit).
- **A 2-minute presentation** explaining your approach: what you optimized for, how your planner works, and what limitations you identified.

### Judging flow

1. All teams give their 2-minute presentations.
2. Judges select the top 3 based on the quality of approach, clarity of thinking, and plausibility of claimed performance.
3. Organizers run the harness on the top-3 submissions to verify the claimed scores *match reality*. Ties are broken by `S_total`; further ties by total control effort (lower wins).
4. Final ranking is announced based on verified scores.

> **In short:** the presentation gets you into the top 3; the harness confirms you didn't over-promise. If your verified score is significantly below what you claimed in the talk, you'll be re-ranked accordingly.

## 10. Testing Your Submission

Organizers ship a **testing kit** in this repository: a Python package containing the structural validator, the official scorer, the three case configs, and a mock physics simulator. You test your file with a single command:

```bash
cd teams_kit/
pip install -r requirements.txt
python test_my_submission.py my_submission.py
```

The mock simulator treats your commanded attitude as perfectly tracked (no controller dynamics or actuator lag). The validator, scorer, gate logic, TLEs, and AOI are **identical** to the grader — so if your local score is zero, your real score will be zero too.

### Mock vs. real — leave margin

Your local (mock) scores will be optimistic compared to the organizers' Basilisk run. Leave headroom so real-sim controller overshoot doesn't trip the gates:

- Body rate during integration: target ≤ 0.03°/s (limit is 0.05°/s)
- Off-nadir for frames you care about: target ≤ 55° (limit is 60°)
- Never sit wheels at exactly 30 mNms — leave ~5 mNms margin

The [teams_kit README](../teams_kit/README.md) walks through the example submissions, including a deliberately-failing nadir-greedy planner that illustrates the classic smear-gate mistake. Read it before you start.

---

*Good luck, and aim well.*  ·  Questions: open an issue.  ·  Organizers may issue clarifications at any time before the submission deadline.
