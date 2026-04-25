# Judging Rubric

How submissions are scored. Read this *before* you start building — it'll tell you where to spend your last 12 hours.

## The rubric

Judges score each submission independently across five criteria, then the scores are averaged. All criteria are scored 0–10; the weights below convert to a final 100-point total.

| # | Criterion | Weight | What we're looking for |
|---|---|---|---|
| 1 | **Fit to TM2Space's orbital-compute story** | 25% | Would this workload plausibly run on MOI / a Jetson-class payload? Does the *output* (not the imagery) actually matter to a paying customer? "Downlink the answer, not the data." One real customer, named, in one sentence. |
| 2 | **Quantitative result vs. a baseline** | 30% | Not just "it runs." One slide showing metric + baseline + delta. Be honest about how much of the gain is from TerraMind specifically (vs. the dataset, vs. a smaller model). |
| 3 | **Evidence the system works** | 20% | Recorded clip, notebook output, or one input → output screenshot. Live demo is welcome if you can pull it off in 30 s; recorded is equally acceptable in this slot. The judge needs to *see* it work, not take your word for it. |
| 4 | **Edge-inference feasibility** | 15% | You don't have to *prove* it runs on a Jetson — but you should have *thought* about it. Model size in MB, inference latency on a known card, RAM ceiling, an honest "would this fit" paragraph. Hand-waving "could be quantized" is not enough; back-of-envelope numbers are. |
| 5 | **Code quality & documentation** | 10% | Reproducible? README clear? Sensible structure? A judge cloning your folder should be able to run inference in under 10 minutes. |

Tie-breaks go to (a) quality of writeup, then (b) the team that demoed live vs. recorded.

## What we are *not* scoring

- **Visual prettiness of the slides.** A clear story on a plain background beats a designed deck that obscures what you built.
- **Number of features.** One thing that works beats five things that nearly work.
- **Use of the most modalities possible.** Using Sentinel-1 + Sentinel-2 + DEM + LULC + NDVI doesn't make a project better than one that uses just Sentinel-2 well.
- **How impressive the architecture sounds.** Fine-tuning the small variant on one dataset and beating a baseline is more interesting to judges than a complicated pipeline that doesn't have numbers attached.

## Common ways to lose points

Read these. They are real failure modes from past hackathons.

- **No baseline.** "Our model gets 0.84 mIoU" — *vs. what?* Random output gets >0 on most metrics. State the baseline (even if it's "predict the majority class") and your delta.
- **Demo doesn't run live.** If the judge can't see it work, they can't score criterion #3. If your model is too slow to demo live (which is fine and honest), record a clip.
- **TerraMind isn't doing real work.** If you load TerraMind, take its output, throw it away, and run a separately-trained UNet on the raw imagery — you used TerraMind as a checkbox. Judges will notice. Use the encoder, the generator, TiM, or a fine-tuned head. Make TerraMind earn its place.
- **Overclaiming.** "Our system would replace 90% of human flood-response work" — no. "Our system reduces analyst review time by X% on this Y-tile test set" — yes. Concrete and honest beats vague and grand.
- **Hand-waved feasibility.** "This would obviously run on a satellite" — no, you have to do the math. Model size in MB, FLOPs per inference, expected latency. If you didn't measure it, say "we didn't measure it" and move on; that's better than guessing.
- **Unreproducible code.** Pinned dependencies + a README + a single command to run inference. If the judge has to debug your pip install, you've already lost criterion #5.

## The 2-minute presentation

You get 2 minutes. We cut at 2:00. Suggested structure:

| Time | Slide / segment | What goes here |
|---|---|---|
| 0:00–0:20 | **The customer** | One slide, one customer, one sentence. *"A crop insurance underwriter in Maharashtra needs to verify a claim within 48 hours."* |
| 0:20–0:50 | **The data + model** | What you used, what you fine-tuned, why. One architecture sketch. |
| 0:50–1:30 | **The evidence** | Recorded clip, screenshot, or quick live demo. Input → output, visibly. |
| 1:30–1:50 | **The numbers** | One slide. Your metric, the baseline, the delta. Inference latency. Model size. |
| 1:50–2:00 | **Limits + what's next** | What doesn't work yet. What you'd build with another week. |

Skip the table-of-contents slide. Skip "thanks for listening" — just stop talking and take questions.

Two minutes is short. Practice it on a stopwatch. Cut anything that isn't customer, evidence, numbers, or limits.

## Verification

We will skim your code after the presentation. We're not running a full reproducibility audit, but if your claimed numbers and your code are obviously inconsistent (e.g., your README says 0.84 mIoU and your notebook outputs 0.62), you'll be re-ranked.

If your demo worked live, that's strong evidence; we usually don't need to re-run anything. If your demo was recorded, expect the verification skim to be a bit more thorough.

## Questions

Open an [issue](../../issues) before the submission deadline. After the deadline, judging is silent.
