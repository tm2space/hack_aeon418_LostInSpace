# AI/ML in Space Track — Problem Statement

> **Hackathon Problem Statement** — Earth-Observation Foundation Models for Orbital Compute

| | |
|---|---|
| **Track**       | AI/ML in Space — TerraMind for Orbital Compute |
| **Format**      | Open-ended. You pick the use case. |
| **Deliverable** | A code folder + a short writeup + a 2-minute presentation |
| **Judging**     | Presentation + writeup + code, scored against the rubric in [`JUDGING.md`](./JUDGING.md) |

---

## 1. The Setup

### TakeMe2Space and orbital compute

[TakeMe2Space (TM2Space)](https://www.tm2.space/orbitlab) is a Hyderabad-based spacetech startup running **OrbitLab** — a platform where customers upload AI models to TM2Space's MOI satellites and pay roughly $2/minute for orbital compute. Their first satellite (**MOI-TD**) flew on ISRO's PSLV C60 in December 2024 — India's first AI lab in space. **MOI-1** is operational. A 6U cubesat carrying an Nvidia Jetson is on a Falcon 9 rideshare later this year.

The core idea TM2Space sells is simple: **downlinking raw satellite imagery is bandwidth-expensive and slow.** If you can run inference *on* the satellite and downlink only the result — a flood mask, a ship count, a "yes there's smoke here" flag — you save ~99% of the bandwidth and the answer arrives in minutes instead of hours. This matters for agriculture, insurance, mining, disaster response, and maritime monitoring.

### IBM TerraMind

[TerraMind](https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base) (IBM + ESA + Jülich Supercomputing Centre, released April 2025) is a generative any-to-any foundation model for Earth observation. Pretrained on 9 modalities (Sentinel-1 SAR GRD/RTC, Sentinel-2 optical L1C/L2A/RGB, NDVI, Copernicus DEM, ESRI LULC, coordinates, text captions), it ships in `tiny` / `small` / `base` / `large` sizes and fine-tunes through [TerraTorch](https://github.com/IBM/terratorch). Its standout capability is **Thinking-in-Modalities (TiM)** — the model can generate a missing modality (e.g., predict SAR from optical, or NDVI from RGB) as an intermediate reasoning step to improve a downstream task.

Small variants are plausibly small enough to run on a Jetson-class satellite payload. Which is the entire point.

## 2. The Challenge

> **Build something with TerraMind that a satellite operator could plausibly run on-orbit, and that a customer would plausibly pay for.**

That's the whole brief. The constraint that defines a good entry is **"downlink the answer, not the data"** — your system should turn a stream of Earth-observation imagery into a small, useful output (a mask, a classification, a flag, a metric, a generated band, a routing decision) that's worth more to the customer than the raw bytes would have been.

What you build is up to you. Pick your own use case, dataset, fine-tuning recipe, and demo. [Section 5](#5-example-directions) lists seven starter ideas — these are *inspirations, not assignments*. You're encouraged to invent your own. The only hard requirement is that TerraMind is meaningfully part of your solution (encoder, generator, TiM, or fine-tuned head — your call).

## 3. Constraints & Ground Rules

These are non-negotiable. Everything else is up to you.

- **No training from scratch.** TerraMind's pretraining took 9,216 A100-hours. Use the published checkpoints. Fine-tuning the `tiny` or `small` variant on a downstream dataset is the expected path.
- **Reproducible.** Whatever you build, someone else has to be able to run it from your repo. Pin your dependencies, list your dataset sources, and write down the steps. If your demo only runs on your laptop, it doesn't exist for judging purposes.
- **Honest about limits.** If your model only works on cloud-free Sentinel-2 over Europe in summer, say that. If your inference takes 90 seconds per tile on a V100, say that too. Overclaimed performance is worse than modest, honest performance.
- **TerraMind has to do real work.** Loading TerraMind and then ignoring it (e.g., piping tiles into a separately-trained UNet) doesn't count. The model should be doing something only a foundation model can — feature extraction, generation, TiM, multi-modal reasoning.
- **Datasets must be legal to use.** Open Sentinel data, public benchmarks, GEO-Bench, etc. are fine. Scraped imagery from someone's commercial portal is not.
- **Single team folder.** All of your code, notebooks, and writeup live in `submissions/<team_name>/`. See [`SUBMITTING.md`](../SUBMITTING.md).

## 4. What You Submit

Three things, in `submissions/<your_team_name>/`:

### 4.1 The code

Notebooks, scripts, configs — whatever you used to build it. Structure your folder however you like, but include:

- A way to run inference on a sample input (`infer.py`, a notebook cell, an app — your call)
- Pinned dependencies (`requirements.txt` or `environment.yml`)
- Any small sample data needed for the demo (do **not** commit large datasets — link them instead)
- Trained weights *only if small* (< 200 MB). Otherwise, host externally and link from your README.

### 4.2 The writeup

A `README.md` inside your team folder, ≤ 2 pages. It should answer:

1. **What problem are you solving?** (One paragraph. Who's the customer? Why would they pay?)
2. **What did you build?** (One paragraph. Architecture, dataset, fine-tuning recipe.)
3. **How did you measure it?** (Numbers vs. a baseline. Even a weak baseline is better than none.)
4. **What's the orbital-compute story?** (How does this fit on a satellite? Model size, latency, power.)
5. **What doesn't work yet?** (Be honest. The next-question section is the most useful one.)

### 4.3 The presentation

2 minutes. Slides + a live demo (or recorded clip if your model is too slow to demo live). Judges want to see:

- The customer problem in one slide
- The model in one slide
- A working demo (clip is fine)
- Numbers
- Honest limits

We'll publish a slot schedule the day before. Don't run over — judges cut you off at 2:00.

## 5. Example Directions

Below are seven *starting ideas* drawn from real customer pitches TM2Space has fielded. They are deliberately under-specified — the framing tells you the problem and hints at a dataset, but **the architecture, fine-tuning recipe, and demo are yours to design**. You can tackle one of these as-stated, mix two together, or invent something entirely different that fits the core constraint in [Section 2](#2-the-challenge).

Difficulty ratings are calibrated for a 48-hour build by a final-year team of 3–4. They assume zero prior TerraMind experience and include setup time.

### 5.1 Crop monitoring under cloud cover · ★★★

Sentinel-2 optical sensors are useless when there are clouds, and most of the time over interesting agricultural land there are clouds. An agribusiness customer (think: crop insurance, yield forecasting, irrigation scheduling) wants crop-type maps regardless. TerraMind's TiM mode can *imagine* the missing optical bands from SAR, or synthesize NDVI from a partially-cloudy input. Show that TiM beats a naive cloud-masked baseline.

**Customer:** agriculture, crop insurance. **Dataset starters:** GEO-Bench South Africa crop type, EuroSAT (for a quick sanity check). **Watch out for:** TiM-fine-tuning is slower than vanilla fine-tuning — budget your time.

### 5.2 Real-time flood segmentation · ★★

Monsoon flooding (Chennai, Assam, Kerala, Bangladesh) repeats every year and the response window is hours, not days. A government responder wants a flood mask + an affected-area-in-km² number, fast. Sentinel-1 SAR sees through clouds and works at night, which is exactly when flood imaging is hardest. Fine-tune TerraMind on flood data and wrap it in something a non-technical user can hit.

**Customer:** disaster response agencies, NDMA, insurance. **Dataset starters:** Sen1Floods11. **Bonus:** add a TiM-generated LULC layer and measure the mIoU bump.

### 5.3 Burn-scar / wildfire damage mapping · ★★

After a fire, insurers and forestry agencies need acreage, severity, and a polygon they can paste into a claim or a recovery plan. Output should be a shapefile + numbers, not a pretty picture. Bonus points for a before/after NDVI delta computed using TerraMind's generation capability — *what was this hillside before it burned?*

**Customer:** insurance, forestry departments. **Dataset starters:** HLS Burn Scars (IBM ships a TerraTorch config for this). **Watch out for:** small datasets reward heavy augmentation.

### 5.4 Smart downlink / scene triage · ★★★

**This is the most TM2Space-native direction in the list.** A customer doesn't want every tile MOI captures — they want only the tiles that matter to them. Build a lightweight classifier on top of TerraMind's frozen encoder that scores incoming tiles for "interestingness" against a query: *"only downlink tiles containing ships,"* or *"only tiles with > 30% cloud-free farmland,"* or *"only tiles where this hectare has changed since last week."* Simulate the bandwidth savings: *"downlinked 12% of captured frames, caught 94% of events."*

**Customer:** literally TM2Space's pricing model. **Dataset starters:** any labelled multi-class set (BigEarthNet-MM, EuroSAT) repurposed as a triage problem. **Why it scores well:** it directly demonstrates *why* compute-in-orbit beats bandwidth-to-ground.

### 5.5 Ship & maritime activity detection · ★★★

India's EEZ is 2 million km² and largely unmonitored. A coast guard or fisheries enforcement customer wants ship detections from SAR (which works through clouds and at night, again), with rough heading and size. Fine-tune TerraMind on Sentinel-1 SAR for ship detection and produce annotated chips + a CSV.

**Customer:** maritime domain awareness, fisheries enforcement, port authorities. **Dataset starters:** xView3 (or a subset — the full set is large). **Watch out for:** SAR is unintuitive; allocate time to look at your data before training.

### 5.6 Cloud-removal generator · ★★

Use TerraMind's generation mode (no fine-tuning required) to convert a cloudy Sentinel-2 tile into a synthetic Sentinel-1 view of the same area, revealing structure under the clouds. Or go the other way: hallucinate plausible optical from radar. Evaluate qualitatively + with a quantitative metric on a held-out cloud-free pair.

**Customer:** anyone with a cloud-coverage problem (which is everyone). **Dataset starters:** any co-registered S1+S2 pair set; small custom AOI from Copernicus Browser works fine. **Why it scores well:** it's the most visually impressive demo on this list and the easiest to present to a non-technical judge.

### 5.7 Bi-temporal change detection · ★★★★

Pick a real Indian district. Pull two Sentinel-2 tiles a year apart. Extract TerraMind features for both, compute a meaningful difference, and fine-tune a small head on a change-detection dataset. Use cases: illegal mining audits, deforestation monitoring, urban sprawl tracking, encroachment detection.

**Customer:** ministries, NGOs, environmental auditors, real estate. **Dataset starters:** LEVIR-CD or OSCD for fine-tuning; pick your own AOI for the demo. **Caveat:** bi-temporal pipelines eat time. Scope down or start from a single AOI.

---

> **Inventing your own?** Fine. The acid test is: *would a TM2Space sales engineer be able to pitch this to a customer?* If yes, ship it. If no, reconsider the use case.

## 6. Judging

See [`JUDGING.md`](./JUDGING.md) for the full rubric and presentation tips. Headline:

| Criterion | Weight |
|---|---|
| Fit to TM2Space's orbital-compute story | 25% |
| Quantitative result vs. a baseline | 30% |
| Live demo or runnable app | 20% |
| Edge-inference feasibility (discussed, not necessarily proven) | 15% |
| Code quality & documentation | 10% |

Judges score independently and average. Tie-breaks go to (a) quality of writeup, then (b) the team that demoed live vs. recorded.

## 7. Practical Setup

Read [`teams_kit/README.md`](../teams_kit/README.md) for the full setup walkthrough — including pinned versions, model-size guidance, and the known Mac/MPS gotcha. Headline:

- Use the **TerraMind-1.0-small** checkpoint as your default. The base variant is too heavy for Colab free tier; tiny is fine for sanity checks but underpowered for most downstream tasks.
- Pin `terratorch >= 1.2.4` and `diffusers == 0.30.0`. Other version combos break in interesting ways.
- Python 3.11+.
- **Do not download TerraMesh** (the pretraining set). It's 14 TB. You don't need it.

## 8. Resources

- [Datasets reference](./DATASETS.md) — pre-staged datasets with download links and sizes
- [TerraMind on HuggingFace](https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base)
- [TerraMind GitHub (official notebooks + configs)](https://github.com/IBM/terramind)
- [TerraMind paper (arXiv)](https://arxiv.org/html/2504.11171)
- [IBM Research blog post](https://research.ibm.com/blog/terramind-esa-earth-observation-model)
- [TerraTorch fine-tuning toolkit](https://github.com/IBM/terratorch)
- [TakeMe2Space OrbitLab](https://www.tm2.space/orbitlab)

---

*Good luck, and aim well.* · Questions: open an issue. · Organizers may issue clarifications at any time before the submission deadline.
