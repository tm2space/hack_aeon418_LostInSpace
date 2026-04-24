# Contributing

This repo is primarily a hackathon deliverable. Contributions are welcome for:

- Typos, clarity fixes, and small corrections in the problem statement
- Bugs in the testing kit (`teams_kit/`)
- Documentation improvements
- Additional example submissions (ideally pedagogical, like the existing
  `nadir_greedy.py` which illustrates the smear-gate pitfall)

## What NOT to contribute

- **Your submission.** Submissions go via the process in [`SUBMITTING.md`](./SUBMITTING.md), not as PRs against `main`.
- **Changes to the scoring logic or test cases** after the problem statement is frozen. Open an issue instead — if we agree it's a real bug, we'll publish a clarification.
- **Changes to the organizer harness** that would alter grading. Same — open an issue.

## Development setup

```bash
git clone <this-repo>
cd <repo>
pip install -r teams_kit/requirements.txt

# Validator tests
python organizer_harness/tests/test_validator.py

# Smoke-test the full pipeline with the reference submission
python teams_kit/test_my_submission.py teams_kit/example_submissions/stop_and_stare.py
```

Expected output: `S_total ≈ 0.154` with the `stop_and_stare` reference.

## Pull request conventions

- One logical change per PR.
- If you're editing `docs/PROBLEM_STATEMENT.md`, also update the `.docx` source (regenerate with the `make_docx.js` tooling in a future release) and the PDF. Don't let the three drift.
- Keep commit messages short and descriptive: `docs: clarify smear-rate definition`, `teams_kit: fix case3.json RAAN typo`.

## Reporting issues

Use the [Issues](../../issues) tab. Helpful info:

- Which file or section?
- Expected vs actual behavior
- For bugs: a minimal reproducer (a 20-line `plan_imaging` that demonstrates the problem)

Security-relevant issues (e.g. a path-traversal in the grader) can be sent to `<organizer-email>` privately.

## Code of Conduct

Be decent. No harassment, no demeaning language, no personal attacks. If something goes sideways, email the organizers.
