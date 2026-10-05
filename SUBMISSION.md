---
title: Spotter: I built my gym-obsessed friend a training log that keeps his bloodwork off the cloud
published: false
tags: devchallenge, weekendchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

<!-- EDIT ME: everything in [square brackets] needs your real details. Don't publish with brackets left in. -->

## What I Built

[Friend's name] is 21, trains [5] days a week, and is cutting. His tracking lives in four places: a calorie app on his phone, a Samsung band syncing sleep and heart rate to Samsung Health, a notes app for his lifts and supplements, and a folder of blood test PDFs he's never looked at twice. [Add one real detail, e.g. "He once asked me to work out his protein from a screenshot of three different apps."]

None of those places talk to each other. His calorie app doesn't know he slept five hours. His workout notes don't know his resting heart rate jumped. And nobody was looking at the Vitamin D number in his last report.

So I built him **Spotter**, a single app that runs on his own laptop and pulls all of it together:

- **Food in plain words.** He types "3 eggs, 2 rotis with dal, scoop of whey in milk" and gets back an editable table with calories and macros, measured against targets worked out from his body and his chosen deficit.
- **Supplements** as a daily checklist, so he can see whether he's actually taking the creatine he pays for.
- **A workout plan** built around his training days and equipment, with set logging and an estimated one-rep-max chart. That chart answers the question every cutting lifter has: am I losing fat or losing strength?
- **Recovery from his Samsung band.** Spotter imports the Samsung Health data export and turns last night's sleep, resting heart rate and stress into a plain call for today: push, train as planned, or go lighter.
- **Blood tests.** He drops in a lab PDF. Spotter extracts every result, flags anything outside the lab's own reference range, tracks markers across reports, and explains flagged results in plain language with questions to take to his doctor.
- **A weekly check-in** written like a message from a gym buddy, built from the week's real numbers.

## Demo

[Embed a 2-3 minute video. Suggested flow: log a meal in one sentence → Today page filling up → import the sample Samsung export and show the readiness call → upload the sample blood report and show the flags → generate the weekly check-in.]

All demo data is fictional and included in the repo under `sample_data/`. His real numbers stay on his laptop, which is rather the point.

## Code

{% github [your-username]/spotter %}

## How I Built It

Spotter is a Streamlit app backed by SQLite, with **Qwen2.5 7B running locally through Ollama** on [his/my] RTX 3050. The 3B model works too on smaller GPUs or CPU only.

The most important design decision was deciding **what the model is not allowed to do.**

A language model is great at reading "had two rotis and a bowl of dal" and terrible at arithmetic. So Spotter splits the work:

1. **The model reads.** It turns free text into structured JSON: food items with quantities and units, lab markers with values and reference ranges, a workout plan.
2. **Code does every number.** Food items are fuzzy-matched against a built-in nutrition table with Indian staples (roti, dal, poha, paneer, soya chunks) alongside the usual gym foods. Units like "bowl" or "scoop" convert to grams, and the macros are calculated in Python. Calorie targets come from the Mifflin-St Jeor formula, with a floor at his BMR so the app never suggests eating less than his body burns at rest.
3. **Guardrails catch the model when it's wrong.** When the model estimates a food that isn't in the table, Spotter checks its calorie number against the macros (4/4/9 kcal per gram). If they disagree by more than 25%, it trusts the macros. Workout plans can only use exercises from a fixed library; anything else gets dropped. Lab values always land in an editable table that he checks against the PDF before anything is saved.

The weekly check-in follows the same rule. Python computes the averages, the days he hit his protein target and the strength trends, and the model's only job is to turn those numbers into a note a friend would actually read.

The Samsung part was the most fiddly. Samsung Health exports a folder of CSVs with a metadata line on top, column names like `com.samsung.health.sleep.start_time`, and timestamps in UTC stored next to a separate offset like `UTC+0530`. The parser is deliberately forgiving about all of that, because the format changes between app versions.

[Optional: one honest paragraph on something that went wrong and how you fixed it. In testing, fuzzy matching was mapping "quinoa salad" to plain green salad, about a fifth of the real calories, so I switched to a stricter scorer and let unknown foods fall through to a model estimate instead.]

## Why Does Open Innovation Matter?

Look at what Spotter holds: everything he eats, every supplement he takes, how he slept every night, his resting heart rate, and his blood test results. That's one of the most personal datasets a 21-year-old has.

With a closed API, every meal description and every lab report would travel to someone else's server. With an open-weight model running in Ollama, **none of it leaves his laptop.** There's no account, no sync, and no privacy policy to read. The database is one SQLite file he can delete whenever he wants.

Open made three more things possible:

- **It costs nothing to run.** He'll log food three or four times a day, every day. A per-token bill on a habit app is a slow leak; a local model is free after the download.
- **I could pick the model to fit his hardware.** Qwen2.5 7B fits on his GPU; on a weaker machine it's one environment variable to switch to the 3B model. Nothing else changes.
- **It works offline.** Gym Wi-Fi is famously bad. Spotter doesn't care.

Where a closed frontier model would have done better: estimating unusual dishes from scratch, and parsing very messy lab PDFs. The answer wasn't a bigger model. It was making the small one's job smaller and checking its work in code. That split ended up being the best design choice in the project.

## Handing It Over

[This section is the bonus points. Fill it in after he's actually used it.]

[What happened when you sat him down with it? What did he log first? What confused him? Did anything surprise him, e.g. a flagged blood marker, his real average sleep, his real protein intake?]

> "[His actual words. Don't paraphrase or polish them.]"

[What you changed after watching him use it, if anything.]

## My Agent Session

[Optional: embed your DevRelay session or link it.]

## Prize Categories

[List any partner categories that apply, or delete this section.]
