# 🏋️ Spotter

A local-first training, nutrition and recovery log, built for one friend who lifts.

Spotter keeps his food, supplements, workouts, Samsung band data and blood test results in one place, on his own laptop. A local open-weight model (via Ollama) reads the messy stuff: meal descriptions, lab PDFs, plan requests. Plain Python does every number.

## What it does

- **Log food in plain words.** "3 eggs, 2 rotis with dal, scoop of whey in milk" becomes a checked, editable table with calories and macros.
- **Targets.** Maintenance and cut calories from the Mifflin-St Jeor formula, a chosen deficit that never drops below BMR, protein per kg.
- **Supplements.** A daily checklist, 14-day adherence, and a timing review that defers to a pharmacist.
- **Workouts.** A weekly plan the model builds only from a fixed exercise library, set logging, and estimated 1RM trends to check strength holds during the cut.
- **Band & recovery.** Imports the Samsung Health data export (sleep, heart rate, steps, stress) and turns last night into a simple readiness call for today's session.
- **Blood tests.** Reads a lab PDF, flags values outside the lab's own reference range, charts trends across reports, and explains flagged markers without diagnosing.
- **Weekly check-in.** Code computes the week's numbers; the model writes a short gym-buddy note from them.

## Setup

1. Install [Ollama](https://ollama.com) and pull a model:
   ```bash
   ollama pull qwen2.5:7b      # 8 GB VRAM or more (e.g. desktop RTX 3050)
   ollama pull qwen2.5:3b      # 4 GB VRAM laptops, or CPU only
   ```
2. Install and run:
   ```bash
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   streamlit run app.py
   ```
3. To use the smaller model: `SPOTTER_MODEL=qwen2.5:3b streamlit run app.py`
   (Windows PowerShell: `$env:SPOTTER_MODEL="qwen2.5:3b"; streamlit run app.py`)

**Logging from a phone:** run `streamlit run app.py --server.address 0.0.0.0` and open `http://<laptop-ip>:8501` on the same Wi-Fi. This makes the app reachable by anyone on that network, so only do it on a network you trust.

**Getting band data:** in the Samsung Health app, open your profile, then Settings, then *Download personal data*. Copy the exported folder to the laptop, zip it, and upload it on the Band & recovery page. Menu names vary a little between app versions.

## Demo data

`sample_data/` contains a fictional blood report and a fictional three-week Samsung Health export, so you can demo the app without showing anyone's real health data.

## Design notes

- **The model never does arithmetic.** It turns text into JSON; code looks up per-100 g values, converts units and sums. When the model estimates an unknown food, a check compares its calories with 4/4/9 kcal per gram of protein/carbs/fat and trusts the macros if they disagree by more than 25%.
- **The model can't invent exercises.** Plans are matched against a fixed library and anything that doesn't match is dropped.
- **Lab values are always reviewed.** Extracted results land in an editable table and are only saved after a human checks them against the PDF.
- **Readiness is a heuristic**, compared against the last 14 days of his own data. It's a nudge, not a medical score.

All data lives in `data/spotter.db` (SQLite). Delete that file to start over.

## License

MIT
