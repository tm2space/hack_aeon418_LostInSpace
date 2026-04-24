# AI/ML in Space Track — Hackathon

[![Problem Statement](https://img.shields.io/badge/problem%20statement-read-blue)](./docs/PROBLEM_STATEMENT.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

Build something useful with [IBM TerraMind](https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base) — a generative any-to-any foundation model for Earth observation — that fits TakeMe2Space's *"run inference in orbit, downlink the answer"* story. The track is open-ended: pick your own use case, dataset, and approach. Submissions are judged on a presentation + code + writeup, not an automated grader.

## For participants

1. **Read the problem statement** → [`docs/PROBLEM_STATEMENT.md`](./docs/PROBLEM_STATEMENT.md) (PDF / DOCX also available)
2. **Skim the example directions** → [Section 5 of the problem statement](./docs/PROBLEM_STATEMENT.md#5-example-directions). These are *starting points, not assignments*.
3. **Set up your environment** → [`teams_kit/README.md`](./teams_kit/README.md) covers TerraMind install, model loading, dataset pointers, and the gotchas (Mac/MPS, model size, version pins).
4. **Build something** → fine-tune a small TerraMind variant on a dataset that fits a real customer need. No training from scratch — the base model took 9,216 A100-hours.
5. **Submit** → see [`SUBMITTING.md`](./SUBMITTING.md).

You will ultimately deliver:

- **A code folder** under `submissions/<team_name>/` (notebook, scripts, model card — your call)
- **A short writeup** (`README.md` inside your team folder, ≤ 2 pages) covering what you built, why, and how
- **A 5-minute presentation** with a live demo or recorded clip

## Repository layout

```
.
├── docs/
│   ├── PROBLEM_STATEMENT.md       # browse it on GitHub
│   ├── PROBLEM_STATEMENT.pdf      # canonical print version
│   ├── PROBLEM_STATEMENT.docx     # editable source
│   ├── DATASETS.md                # pre-staged dataset list with links
│   └── JUDGING.md                 # rubric details + presentation tips
├── teams_kit/                     # what participants use to get started
│   ├── README.md                  # setup walkthrough
│   ├── requirements.txt           # pinned versions (terratorch, diffusers, ...)
│   └── example_submissions/       # stub submission folder showing layout
├── submissions/                   # where teams' work lives (see SUBMITTING.md)
├── SUBMITTING.md                  # submission process
├── LICENSE                        # MIT
└── README.md                      # you are here
```

> Unlike the [Lost in Space track](../lost-in-space-hackathon), this track has **no automated grader**. There's no organizer harness because there's nothing deterministic to grade — you're solving an open problem, and the judging is humans-in-the-loop against the rubric in [`docs/JUDGING.md`](./docs/JUDGING.md).

## Quick links

- [Problem statement (markdown)](./docs/PROBLEM_STATEMENT.md)
- [Problem statement (PDF)](./docs/PROBLEM_STATEMENT.pdf)
- [Datasets reference](./docs/DATASETS.md)
- [Judging rubric](./docs/JUDGING.md)
- [Teams' starter kit](./teams_kit/)
- [Submission instructions](./SUBMITTING.md)
- [File an issue](../../issues) — clarifications, broken links, dataset access problems

## About TerraMind (the short version)

TerraMind (IBM + ESA + Jülich, released April 2025) is pretrained on 9 modalities — Sentinel-1 SAR (GRD, RTC), Sentinel-2 optical (L1C, L2A, RGB), NDVI, Copernicus DEM, ESRI LULC, coordinates, and text captions. It ships in `tiny`, `small`, `base`, and `large` sizes, fine-tunes through [TerraTorch](https://github.com/IBM/terratorch), and has one headline trick called **Thinking-in-Modalities (TiM)** — the model can generate a missing modality (e.g., predict NDVI from SAR) as an intermediate reasoning step to improve a downstream task.

Why it matters for this track: small fine-tuned variants can plausibly run on a Jetson-class satellite payload — which is exactly what TM2Space's upcoming 6U cubesat carries. So the workloads you build here aren't just academic; they map onto real orbital-compute use cases.

## Credits

Built by TakeMe2Space, 2026. TerraMind © IBM Research, ESA, and Jülich Supercomputing Centre. TakeMe2Space and OrbitLab are trademarks of TakeMe2Space.

Licensed under [MIT](./LICENSE).

Have a question or a b ug to report? Let us know here: https://forms.gle/o7vEkvp8LeeXEPQn9
