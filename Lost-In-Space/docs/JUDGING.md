# Judging Rubric

How Lost in Space submissions are scored. Read this *before* you start building.

Judging is two-stage:

1. **Presentation gate (this rubric).** All teams give a 2-minute talk. Judges use the rubric below to pick the **top 3**.
2. **Harness verification.** Organizers run the [Basilisk harness](../organizer_harness/) on the top-3 submissions. Final ranking among the top 3 is the verified `S_total` from [Section 5 of the problem statement](./PROBLEM_STATEMENT.md#5-scoring-metric-automated). Ties broken by total control effort (lower wins).

So: the presentation gets you in; the harness ranks you within the top 3. If your verified score is far below what you claimed in the talk, you'll be re-ranked accordingly.

## The presentation rubric

Judges score each submission independently across five criteria. All criteria are scored 0–10; the weights below convert to a final 100-point gate score.

| # | Criterion | Weight | What we're looking for |
|---|---|---|---|
| 1 | **Strategy clarity** | 30% | A judge should be able to restate your planner's algorithm in one sentence after the talk: e.g. *"greedy raster from NW corner, replanned every 1 Hz"* or *"two-pass: solve a coverage MILP offline, then track."* If we can't name your approach, criterion 1 is gone. |
| 2 | **Constraint reasoning** | 25% | Show you understood the three hard gates (smear ≤ 0.05°/s, wheel ≤ 30 mNms, off-nadir ≤ 60°) and how your plan respects them. Bonus for naming the trap: nadir-greedy looks great until smear discards every frame. |
| 3 | **Case-3 awareness** | 20% | Case 3 (60° offset) is weighted 40% of `S_total` and has AOI corners that are physically unreachable. Did you adapt — partial-coverage strategy, prioritized regions, accepted trade-off? "Same plan everywhere" is a weak answer. |
| 4 | **Honesty of claimed numbers** | 15% | If you cite a coverage % or `S_total`, it should match your mock-harness output. Wild over-claims trigger a re-rank when the real harness runs. State your local mock score directly — judges respect honesty. |
| 5 | **Time discipline + visual evidence** | 10% | Hard cut at 2:00. Skip title and agenda slides. One screenshot of a mock-harness scoreboard or a coverage plot is worth more than rhetoric. |

Tie-breaks for the top-3 selection: (a) clarity of constraint reasoning, then (b) Case-3 awareness.

## What we are *not* scoring at the presentation stage

- **Slide design.** A whiteboard sketch on plain paper is fine.
- **Algorithmic novelty.** A textbook greedy planner that respects the gates beats a fancy one that violates them.
- **Code walkthrough.** Save it. The harness reads your code; the judges want strategy and trade-offs.
- **Lines of code.** Short and correct beats long and clever.

## Common ways to lose points

Real failure modes — avoid these.

- **No mention of smear.** Smear is the #1 silent killer. If a judge has to ask "how do you handle smear during integration?", criterion 2 is gone.
- **No Case-3 plan.** Treating all three orbits as the same problem misses the 40%-weighted hardest case. Mention it explicitly.
- **Claiming a score you didn't measure.** "We expect ~0.85 coverage" — measured how? "Mock harness reports 0.82 on Case 1" — yes, that's the form.
- **Forgetting the schedule contract.** If your file doesn't pass the structural validator (see [Section 7.4](./PROBLEM_STATEMENT.md#74--hard-rules-on-the-function)), the harness scores `S_orbit = 0` regardless of presentation. Test locally first.
- **Running over time.** We cut at 2:00 mid-sentence. Practice on a stopwatch.

## The 2-minute presentation

You get 2 minutes. We cut at 2:00. Suggested structure:

| Time | Slide / segment | What goes here |
|---|---|---|
| 0:00–0:20 | **Objective + headline** | What you optimized for (coverage / effort / robustness) and your local `S_total`. One sentence each. |
| 0:20–1:10 | **Planner walkthrough** | How it works. How it dodges smear / saturation / off-nadir. One diagram. |
| 1:10–1:40 | **Case 3** | The hard one. What's your strategy when corners are unreachable? |
| 1:40–2:00 | **Limits + what's next** | What's brittle, what you'd improve with another day. |

Skip "Hi, we're team X." Skip the agenda slide. Just open with the headline number.

## Verification (top 3 only)

After presentations, the organizers run [`organizer_harness/run_evaluation.py`](../organizer_harness/run_evaluation.py) on the top 3 submissions against all three test cases in the real Basilisk simulator. The validator, scorer, and gate logic are identical to the mock you tested with locally — only the physics is real (controller dynamics, actuator lag, integrator coupling).

Expect 5–15% degradation from your mock score because of controller overshoot. Leave margin (target body rate ≤ 0.03°/s, off-nadir ≤ 55°, wheels ≤ 25 mNms) — see [Section 10 of the problem statement](./PROBLEM_STATEMENT.md#mock-vs-real--leave-margin).

Final ranking is verified `S_total`. Ties broken by total control effort.

## Questions

Open an [issue](../../issues) before the submission deadline. After the deadline, judging is silent.
