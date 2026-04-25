# Submitting Your Entry

You deliver **three things** to the organizers:

1. **A code folder** under `submissions/<your_team_name>/`
2. **A short writeup** as `README.md` inside that folder (≤ 2 pages)
3. **A 2-minute presentation** (slides + live or recorded demo)

See [Section 4 of the problem statement](./docs/PROBLEM_STATEMENT.md#4-what-you-submit) for the full deliverable spec, and [`docs/JUDGING.md`](./docs/JUDGING.md) for what scores well.

## How to submit the code

### Zip upload via form

Zip your `submissions/<team_name>/` folder and upload at https://docs.google.com/forms/d/e/1FAIpQLSfBc8iCeqE2sQpObKmA7qn6OSgqu2e3g0QU4o_d_eOkZYPrAQ/viewform?usp=publish-editor. One submission per team.

---

## What goes in your team folder

The folder is yours to organize, but the structure below is a sane default:

```
submissions/<team_name>/
├── README.md              # your writeup (REQUIRED)
├── requirements.txt       # pinned deps (REQUIRED)
├── infer.py               # or a notebook — judge needs ONE entry point
├── train.py               # or a notebook — how you fine-tuned (recommended)
├── configs/               # any TerraTorch / training configs
├── src/                   # supporting code
├── notebooks/             # exploration, EDA, eval
├── sample_input/          # ≤ 10 MB, used by your demo
├── docs/                  # any extra design notes, model card, etc.
└── slides.pdf             # your presentation (recommended; can also email separately)
```

The hard requirements are `README.md`, `requirements.txt`, and one entry point a judge can run.

## What NOT to submit

- ❌ **Large datasets in your folder.** Link them in your README. We won't clone a 14-GB submission.
- ❌ **Trained weights larger than 200 MB.** Host externally (HuggingFace, Drive, S3) and link.
- ❌ **Notebook checkpoints, `__pycache__/`, `.ipynb_checkpoints/`.
- ❌ **API keys, credentials, anything in `.env`.** Even if you think the key is dead.
- ❌ **Code from other teams**, even if they said it was OK. Build your own.
- ❌ **AI-generated boilerplate writeups.** Judges read the README. Generic Claude/ChatGPT output is obvious and will lose points.

Submissions that violate these rules will be flagged and may be disqualified.

## Pre-submission checklist

Run through this before you submit:

- [ ] Folder name is a valid slug (letters / digits / dashes only)
- [ ] `README.md` answers the five questions from [Section 4.2 of the problem statement](./docs/PROBLEM_STATEMENT.md#42-the-writeup)
- [ ] `requirements.txt` is pinned (no `>=`, just exact versions you used)
- [ ] A judge running `pip install -r requirements.txt` followed by your one entry point should see *something* in under 10 minutes on a Colab GPU
- [ ] No files > 200 MB in your folder
- [ ] No API keys committed
- [ ] Slides are ready (PDF preferred — Google Slides links break)
- [ ] Your demo runs end-to-end on a fresh machine *(test this on a teammate's laptop, not yours)*

## The 2-minute presentation

Detailed structure is in [`docs/JUDGING.md`](./docs/JUDGING.md#the-2-minute-presentation). Headline:

1. **The customer** (1 slide)
2. **The model** (1 slide)
3. **The evidence** (the bulk — recorded clip or quick live demo)
4. **The numbers** (1 slide)
5. **Limits + what's next** (1 slide)

You have 120 seconds. Judges cut at 2:00. Skip the table-of-contents slide.

## After submission

- All teams present.
- Judges score against the [rubric](./docs/JUDGING.md).
- Top entries get a quick code skim to confirm the claimed numbers and demo are real.
- Winners announced at the closing ceremony.

If your verified work materially disagrees with what you presented, you'll be re-ranked. We don't expect this to happen often, but it does.

## Questions

Open an [issue](../../issues) before the deadline. After the deadline, silence — so everyone competes on equal footing.
