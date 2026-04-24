# Lost in Space Track — Teams' Testing Kit

A local tester for your Lost in Space Track submission. Lets you validate
your `plan_imaging()` function structurally and score it against all three
pass geometries before submitting.

## What you submit to the organizers

**Exactly one Python file** containing a function named `plan_imaging(...)`
matching the signature in the problem statement (Section 7). Name the file
anything you like.

That's it. No zip, no requirements.txt, no write-up — just the .py file.
Explain your approach in your 2-minute presentation.

## Quick start

```bash
# 1. Install deps (numpy, scipy, sgp4, shapely)
pip install -r requirements.txt

# 2. Run the stub to confirm the kit works
python test_my_submission.py example_submissions/identity_stub.py

# 3. Copy a starting point and start editing
cp example_submissions/stop_and_stare.py my_submission.py

# 4. Score your draft
python test_my_submission.py my_submission.py

# Single case + verbose JSON
python test_my_submission.py my_submission.py --case case1 --json result.json
```

## What the score means

```
    === SUMMARY (mock sim) ===
    S_total = 0.1539
      weights = {'case1': 0.25, 'case2': 0.35, 'case3': 0.4}
```

`S_total` is the weighted sum of three per-orbit scores. Each per-orbit
score is

```
    S_orbit = C * (1 + alpha*eta_E + beta*eta_T) * Q_smear
```

Breakdown per case:

- **C** — fraction of the AOI covered by valid frames (0 to 1)
- **eta_E** — 1 − (ΔH_used / 200 mNms), clipped to [0, 1]
- **eta_T** — 1 − (T_active / T_pass), clipped to [0, 1]
- **Q_smear** — 1 − (fraction of frames that violated the rate limit)
- **frames kept / attempted** — how many of your shutter windows produced
  valid imagery after the three hard gates (wheel saturation, smear,
  off-nadir)
- **rejects** — dictionary of why frames were thrown out. Read this when
  debugging: `smear_exceeded` ≫ 0 means your body rate is too high during
  shutters; `off_nadir` ≫ 0 means you're pointing too far from nadir.

## Mock vs. real simulator

This kit uses a **mock physics simulator** that pretends your commanded
attitude is tracked perfectly (zero controller lag, zero RW dynamics). The
organizers run a full 6-DoF Basilisk simulation with a real reaction-wheel
cluster. The validator, scorer, TLEs, AOI polygon, and gate logic are
identical.

Practical implication: your local scores are **optimistic**. If you barely
pass the smear gate (0.049°/s body rate), the real sim's tracking overshoot
will almost certainly push you over 0.05°/s and reject the frame. Leave
margin:

- Target body rate ≤ 0.03°/s during integration (not the 0.05°/s limit)
- Target off-nadir ≤ 55° for frames you care about (not 60°)
- Don't rely on wheels sitting exactly at their 30 mNms cap

If your mock score is 0, your real score will also be 0. If your mock score
is 0.5, your real score will probably land somewhere in [0.3, 0.5].

## The example submissions

- `identity_stub.py` — structurally valid, takes zero images, scores 0. Use
  as a scaffold for your own submission.
- `nadir_greedy.py` — **intentionally failing reference.** Tracks nadir
  (pointing straight down) and fires every 1 s while overhead of the AOI.
  The body must rotate at orbital rate (~0.06°/s) to keep the imager pointed
  at the moving subsatellite point, which violates the 0.05°/s smear limit.
  Every frame is discarded. Read this file to understand the common pitfall.
- `stop_and_stare.py` — a working baseline that scores ~0.15 S_total. Slews
  between inertially-held stares at the AOI centroid. Beat this.

## Strategy ideas

Everything past the stub is fair game. A few directions:

- **Mosaic the AOI**, don't just stare at the centroid. The AOI is ~100×100 km
  and the FOV is ~17×17 km at nadir — you can fit ~36 non-overlapping frames
  if you're ambitious, and cover the whole AOI.
- **Pre-settle before each shutter.** Start arriving at the stare orientation
  a few hundred ms before `t_start` so the body rate is genuinely zero (not
  just numerically close) when the shutter opens.
- **Case 3 is brutal.** At 60° off-nadir from the AOI centroid, the AOI
  corners sit outside the pointing envelope. You'll either optimize a
  partial-coverage strategy, or concede coverage and grind `eta_E` / `eta_T`
  for whatever credit you can get.
- **Attitude sample density matters.** The harness SLERPs between your
  samples, so sparse samples during slews give the controller less to track.
  Use 20-50 Hz (the max allowed is 50 Hz / min spacing 20 ms).

## Hard rules your function must obey

- Single file, exports `plan_imaging(...)` with the exact signature from
  Section 7.2 of the problem statement
- Returns in under 120 seconds per case
- Deterministic — same inputs, same output (fix any random seeds)
- Uses only: `numpy`, `scipy`, `sgp4` (pre-installed by the grader)
- Don't import `Basilisk` — you don't need it and it won't help you
- Don't read files outside your own source, don't make network calls

## Troubleshooting

- **"schedule failed validation: ..."** — your returned dict has a
  structural problem. The error message points you to which key. Common:
  attitude spacing < 20 ms, shutter duration ≠ 0.120 s, quaternion not
  unit-norm.
- **Frames all rejected as `smear_exceeded`** — your body rotates during
  integration. You need to stop-and-stare (hold attitude for the 120 ms
  window), not track a moving ground point.
- **Frames all rejected as `off_nadir`** — you're pointing too far from
  nadir. At 60° max, some parts of the AOI are physically unreachable in
  case 3.
- **"plan_imaging exceeded 120s budget"** — your planner is too slow.
  Profile with `cProfile` and cut work. Pre-computation scales badly if you
  sample attitude at 50 Hz for 12 minutes = 36,000 samples; 20 Hz is usually
  enough and gives you 2.5× headroom.

## Submission deadline

Whatever your organizers told you. Submit the one .py file via the channel
they specified. Do not submit this testing kit.

Good luck.
