"""Workout plans. The model may only pick from this library, so it can't invent moves."""
import json
from datetime import datetime

from rapidfuzz import fuzz, process

import db
import llm

# name: (muscle group, equipment) -- equipment is gym, dumbbell or bodyweight
LIBRARY = {
    "Barbell Back Squat": ("Legs", "gym"), "Leg Press": ("Legs", "gym"),
    "Romanian Deadlift": ("Hamstrings", "gym"), "Conventional Deadlift": ("Back", "gym"),
    "Leg Extension": ("Quads", "gym"), "Lying Leg Curl": ("Hamstrings", "gym"),
    "Hip Thrust": ("Glutes", "gym"), "Seated Calf Raise": ("Calves", "gym"),
    "Barbell Bench Press": ("Chest", "gym"), "Machine Chest Press": ("Chest", "gym"),
    "Cable Fly": ("Chest", "gym"), "Overhead Press": ("Shoulders", "gym"),
    "Cable Lateral Raise": ("Shoulders", "gym"), "Face Pull": ("Rear delts", "gym"),
    "Lat Pulldown": ("Back", "gym"), "Seated Cable Row": ("Back", "gym"),
    "Barbell Row": ("Back", "gym"), "Pull-up": ("Back", "gym"), "Dips": ("Chest", "gym"),
    "Triceps Pushdown": ("Triceps", "gym"), "EZ-Bar Curl": ("Biceps", "gym"),
    "Hanging Leg Raise": ("Core", "gym"), "Incline Treadmill Walk": ("Cardio", "gym"),
    "Stationary Bike": ("Cardio", "gym"),
    "Dumbbell Bench Press": ("Chest", "dumbbell"), "Incline Dumbbell Press": ("Chest", "dumbbell"),
    "Dumbbell Fly": ("Chest", "dumbbell"), "Dumbbell Shoulder Press": ("Shoulders", "dumbbell"),
    "Dumbbell Lateral Raise": ("Shoulders", "dumbbell"), "One-Arm Dumbbell Row": ("Back", "dumbbell"),
    "Goblet Squat": ("Legs", "dumbbell"), "Dumbbell Romanian Deadlift": ("Hamstrings", "dumbbell"),
    "Bulgarian Split Squat": ("Legs", "dumbbell"), "Dumbbell Lunge": ("Legs", "dumbbell"),
    "Dumbbell Curl": ("Biceps", "dumbbell"), "Hammer Curl": ("Biceps", "dumbbell"),
    "Overhead Dumbbell Triceps Extension": ("Triceps", "dumbbell"), "Dumbbell Shrug": ("Traps", "dumbbell"),
    "Push-up": ("Chest", "bodyweight"), "Pike Push-up": ("Shoulders", "bodyweight"),
    "Bodyweight Squat": ("Legs", "bodyweight"), "Walking Lunge": ("Legs", "bodyweight"),
    "Glute Bridge": ("Glutes", "bodyweight"), "Standing Calf Raise": ("Calves", "bodyweight"),
    "Plank": ("Core", "bodyweight"), "Side Plank": ("Core", "bodyweight"),
    "Dead Bug": ("Core", "bodyweight"), "Brisk Walk": ("Cardio", "bodyweight"),
}
EQUIPMENT = {"Full gym": {"gym", "dumbbell", "bodyweight"},
             "Dumbbells at home": {"dumbbell", "bodyweight"},
             "Bodyweight only": {"bodyweight"}}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

PLAN_SYSTEM = """You are a strength coach. Build a weekly gym plan as JSON only:
{"days": [{"day": "Mon", "focus": str,
  "exercises": [{"name": str, "sets": int, "reps": str, "rest_sec": int, "notes": str}]}]}
Rules:
- Use exactly the training days given, with those day labels.
- Only use exercise names copied exactly from the allowed list.
- 4 to 7 exercises per day, compound lifts first.
- The lifter is in a calorie deficit: keep intensity high (heavy-ish, 1-3 reps in reserve)
  and volume moderate, to hold on to muscle while losing fat.
- Fit the session length given. Notes are short cues (under 12 words)."""


def allowed(equipment):
    kinds = EQUIPMENT[equipment]
    return [n for n, (_, e) in LIBRARY.items() if e in kinds]


def generate(days, equipment, experience, minutes, focus):
    names = allowed(equipment)
    prompt = json.dumps({"training_days": days, "experience": experience,
                         "session_minutes": minutes, "goal_and_preferences": focus,
                         "allowed_exercises": names})
    data = llm.chat_json(PLAN_SYSTEM, prompt)
    plan = []
    for d in data.get("days", []):
        if d.get("day") not in days:
            continue
        exs = []
        for e in d.get("exercises", []):
            hit = process.extractOne(str(e.get("name", "")), names, scorer=fuzz.token_sort_ratio, score_cutoff=90)
            if not hit:
                continue  # drop anything not in the library
            try:
                sets = max(1, min(int(e.get("sets", 3)), 6))
            except (TypeError, ValueError):
                sets = 3
            exs.append({"name": hit[0], "sets": sets, "reps": str(e.get("reps", "8-10")),
                        "rest_sec": int(e.get("rest_sec") or 90), "notes": str(e.get("notes", ""))})
        if exs:
            plan.append({"day": d["day"], "focus": str(d.get("focus", "")), "exercises": exs})
    plan.sort(key=lambda d: WEEKDAYS.index(d["day"]))
    return plan


def save_plan(plan):
    db.x("INSERT OR REPLACE INTO workout_plan (id, plan_json, created) VALUES (1, ?, ?)",
         (json.dumps(plan), datetime.now().isoformat(timespec="minutes")))


def get_plan():
    r = db.q("SELECT plan_json FROM workout_plan WHERE id = 1")
    return json.loads(r[0]["plan_json"]) if r else []


def plan_for(day_label):
    return next((d for d in get_plan() if d["day"] == day_label), None)


def e1rm(weight, reps):
    """Epley estimated one-rep max."""
    return weight * (1 + reps / 30) if reps and weight else 0
