# Submitting Your Entry

You deliver **two things** to the organizers:

1. **One Python file** exporting `plan_imaging(...)` (see [Section 7 of the problem statement](./docs/PROBLEM_STATEMENT.md#7-what-you-submit))
2. **A 2-minute presentation** (slides or live demo — your call)

## How to submit the code

> Organizers: pick ONE of the options below and delete the rest before pushing the repo.

### Option A — Pull request (GitHub-native, recommended for technical cohorts)

1. **Fork this repository.**
2. Create a directory for your team under `submissions/`:
   ```
   submissions/<team_name>/
   └── submission.py
   ```
   `<team_name>` should be a short slug — letters, digits, dashes only. No spaces.
3. Add your single `.py` file there. Optionally include a `README.md` inside your team folder describing your approach (not scored — the presentation is).
4. Open a pull request against `main` with the title `[submission] <team_name>`.
5. CI will sanity-check structural validity (imports, function signature). It will **not** score your submission publicly.
6. Before the deadline, you can push additional commits. After the deadline, PRs are frozen.

No other files. No data files, no pickle caches, no notebook checkpoints.

### Option B — Email

Email your single `.py` file to `<organizer-email>` before the deadline. Subject line: `[LIST submission] <team_name>`. One email per team; we'll take the most recent one received before the deadline.

### Option C — Form upload

Use the submission form at `<form-url>`. Upload one `.py` file. One submission per team.

---

## Naming your file

Name it anything. The grader imports `plan_imaging` by function name, not by filename. `submission.py`, `planner.py`, `my_team_galaxy_brain.py` all work.

## What NOT to submit

- ❌ Zip files, tarballs
- ❌ Multiple Python files
- ❌ `requirements.txt` (you may only use `numpy`, `scipy`, `sgp4` — all pre-installed)
- ❌ Data files, pickle caches, trained weights
- ❌ Anything that imports Basilisk
- ❌ Anything that makes network calls or reads files outside your `.py`

Submissions that violate these rules will be flagged and may be disqualified.

## Pre-submission checklist

Run through this before you submit:

- [ ] `python teams_kit/test_my_submission.py my_submission.py` returns in under 120 seconds per case
- [ ] Local `S_total > 0` (if this is zero, your real score will be zero)
- [ ] No `import Basilisk`, no `requests`, no `urllib`, no `open(...)` outside your file
- [ ] All randomness has a fixed seed
- [ ] Same inputs → same schedule every time you run it
- [ ] Your 2-minute presentation is ready

## The 2-minute presentation

Keep it simple. Judges want:

1. **What did you optimize for?** (Coverage? Energy? Time? A weighted combo?)
2. **How does your planner work?** (One-sentence summary of the algorithm.)
3. **Your claimed score.** (From your local mock run — be honest; we verify.)
4. **What doesn't work / what you'd do with more time.**

You have 120 seconds. Slides are optional. Do not read code aloud.

## After submission

- Top 3 presentations go to the verification round.
- Organizers run `organizer_harness/run_evaluation.py` on your submission against all three cases.
- Scores are published to the leaderboard.
- If your verified score materially disagrees with what you claimed in the talk, you will be re-ranked.

## Questions

Open an [issue](../../issues) before the deadline. After the deadline, silence — so everyone competes on equal footing.
