"""Weekly check-in. Code computes every number; the model only writes the note."""
import json
from datetime import date, datetime, timedelta

import db
import llm
import nutrition

COACH_SYSTEM = """You are a supportive gym buddy writing a weekly check-in for your friend.
You get his week's numbers as JSON. Write under 150 words:
- two specific wins, citing the numbers
- one thing to focus on next week, with a concrete action
Casual, warm, direct. Only use numbers from the JSON; never invent data.
No medical claims. If data is missing, say what to log next week."""


def week_stats(week_start: date, profile):
    end = week_start + timedelta(days=6)
    a, b = week_start.isoformat(), end.isoformat()
    food = db.frame("""SELECT date, SUM(kcal) kcal, SUM(protein) protein FROM food_log
                       WHERE date BETWEEN ? AND ? GROUP BY date""", (a, b))
    weights = db.frame("SELECT date, kg FROM weights WHERE date BETWEEN ? AND ? ORDER BY date", (a, b))
    band = db.frame("SELECT * FROM band_daily WHERE date BETWEEN ? AND ?", (a, b))
    lifts = db.frame("SELECT date, sets FROM workout_log WHERE date BETWEEN ? AND ?", (a, b))
    sups = db.q("""SELECT COUNT(*) n, COALESCE(SUM(taken), 0) taken FROM supplement_log
                   WHERE date BETWEEN ? AND ?""", (a, b))[0]
    n_sups = db.q("SELECT COUNT(*) n FROM supplements WHERE active = 1")[0]["n"]

    latest = db.q("SELECT kg FROM weights WHERE date <= ? ORDER BY date DESC LIMIT 1", (b,))
    t = nutrition.targets(profile, latest[0]["kg"]) if latest else None
    r = lambda v, n=0: None if v is None or v != v else round(float(v), n)

    stats = {
        "week": f"{a} to {b}",
        "days_food_logged": int(len(food)),
        "avg_calories": r(food.kcal.mean()) if len(food) else None,
        "calorie_target": r(t["kcal"]) if t else None,
        "avg_protein_g": r(food.protein.mean()) if len(food) else None,
        "protein_target_g": r(t["protein"]) if t else None,
        "days_protein_target_hit": int((food.protein >= 0.9 * t["protein"]).sum()) if t and len(food) else 0,
        "training_days": int(lifts.date.nunique()) if len(lifts) else 0,
        "total_working_sets": int(lifts.sets.sum()) if len(lifts) else 0,
        "weight_start_kg": r(weights.kg.iloc[0], 1) if len(weights) else None,
        "weight_end_kg": r(weights.kg.iloc[-1], 1) if len(weights) else None,
        "avg_sleep_hours": r(band.sleep_hours.mean(), 1) if len(band) else None,
        "avg_resting_hr": r(band.resting_hr.mean()) if len(band) else None,
        "avg_steps": r(band.steps.mean()) if len(band) else None,
        "supplement_adherence_pct": round(100 * sups["taken"] / (7 * n_sups)) if n_sups else None,
    }
    return stats


def write_note(stats, week_start: date):
    note = llm.chat(COACH_SYSTEM, json.dumps(stats), temperature=0.6)
    db.x("INSERT OR REPLACE INTO coach_notes VALUES (?, ?, ?)",
         (week_start.isoformat(), note, datetime.now().isoformat(timespec="minutes")))
    return note
