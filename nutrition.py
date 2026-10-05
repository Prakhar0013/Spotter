"""Nutrition: the model reads language, the code does every number."""
import json

from rapidfuzz import fuzz, process

import db
import llm
from foods import FOODS

ACTIVITY = {
    "Sedentary": 1.2,
    "Light (1-3 workouts/week)": 1.375,
    "Moderate (3-5 workouts/week)": 1.55,
    "Very active (6-7 workouts/week)": 1.725,
    "Athlete (2x/day or physical job)": 1.9,
}

UNITS = ["g", "ml", "piece", "slice", "cup", "bowl", "plate", "scoop", "tbsp",
         "tsp", "glass", "handful", "can", "pack", "serving"]
UNIT_SYNONYMS = {
    "gm": "g", "gms": "g", "gram": "g", "grams": "g", "kg": "kg", "l": "l",
    "litre": "l", "liter": "l", "pc": "piece", "pcs": "piece", "pieces": "piece",
    "whole": "piece", "slices": "slice", "cups": "cup", "bowls": "bowl",
    "katori": "bowl", "plates": "plate", "scoops": "scoop",
    "tablespoon": "tbsp", "teaspoon": "tsp", "glasses": "glass",
}
FALLBACK_GRAMS = {"glass": 250, "cup": 240, "bowl": 200, "plate": 250,
                  "tbsp": 15, "tsp": 5, "handful": 30, "scoop": 30,
                  "serving": 100, "piece": 100, "slice": 30, "can": 330, "pack": 70}


# ---------- targets ----------

def targets(profile, weight_kg):
    """Mifflin-St Jeor BMR x activity, minus a chosen deficit, never below BMR."""
    w, h, a = weight_kg, profile["height_cm"], profile["age"]
    bmr = 10 * w + 6.25 * h - 5 * a + (5 if profile["sex"] == "Male" else -161)
    tdee = bmr * ACTIVITY.get(profile["activity"], 1.55)
    kcal = max(tdee * (1 - profile["deficit_pct"] / 100), bmr)
    protein = w * profile["protein_g_per_kg"]
    fat = max(0.8 * w, 0.25 * kcal / 9)
    carbs = max((kcal - protein * 4 - fat * 9) / 4, 0)
    return {"bmr": bmr, "tdee": tdee, "kcal": kcal, "protein": protein,
            "carbs": carbs, "fat": fat, "floored": kcal == bmr}


# ---------- food lookup ----------

def _custom_foods():
    out = {}
    for r in db.q("SELECT * FROM custom_foods"):
        out[r["name"]] = {"kcal": r["kcal"], "protein": r["protein"],
                          "carbs": r["carbs"], "fat": r["fat"],
                          "units": json.loads(r["units"] or "{}"), "aliases": []}
    return out


def match_food(name):
    table = {**FOODS, **_custom_foods()}
    choices = {}
    for key, v in table.items():
        choices[key] = key
        for a in v["aliases"]:
            choices[a] = key
    hit = process.extractOne(name.lower().strip(), list(choices),
                             scorer=fuzz.token_sort_ratio, score_cutoff=85)
    if not hit:
        return None, None, None
    key = choices[hit[0]]
    return key, table[key], ("custom" if key not in FOODS else "built-in")


def to_grams(qty, unit, food_units):
    u = (unit or "serving").lower().strip()
    u = UNIT_SYNONYMS.get(u, u)
    if u in ("g", "ml"):
        return qty, True
    if u in ("kg", "l"):
        return qty * 1000, True
    if u in food_units:
        return qty * food_units[u], True
    if u in ("piece", "plate", "serving") and "serving" in food_units:
        return qty * food_units["serving"], False
    return qty * FALLBACK_GRAMS.get(u, 100), False


# ---------- model-assisted steps ----------

PARSE_SYSTEM = f"""You turn a free-text description of food someone ate into JSON.
Return {{"items": [{{"name": str, "quantity": number, "unit": str}}]}}.
unit must be one of {UNITS}.
Use short generic food names ("roti", "chicken breast", "whey protein", "dal").
Split combined foods ("toast with butter" -> white bread + butter).
If no quantity is given, assume 1 of the most natural unit.
Never include calories or nutrients.

Example: "3 eggs, 2 slices brown bread with peanut butter and a scoop of whey in milk"
-> {{"items": [{{"name": "egg", "quantity": 3, "unit": "piece"}},
{{"name": "brown bread", "quantity": 2, "unit": "slice"}},
{{"name": "peanut butter", "quantity": 1, "unit": "tbsp"}},
{{"name": "whey protein", "quantity": 1, "unit": "scoop"}},
{{"name": "milk", "quantity": 1, "unit": "glass"}}]}}"""

ESTIMATE_SYSTEM = """You are a nutrition reference. For the food given, return typical
values PER 100 g as commonly eaten (cooked if usually cooked), plus typical grams for
household units. JSON only:
{"kcal": n, "protein": n, "carbs": n, "fat": n, "units": {"piece": g, "serving": g}}"""


def parse_meal(text):
    data = llm.chat_json(PARSE_SYSTEM, text)
    items = []
    for it in data.get("items", []):
        try:
            items.append({"name": str(it["name"]).strip(),
                          "quantity": float(it.get("quantity") or 1),
                          "unit": str(it.get("unit") or "serving")})
        except (KeyError, TypeError, ValueError):
            continue
    return items


def estimate_food(name):
    d = llm.chat_json(ESTIMATE_SYSTEM, name)
    v = {k: max(float(d.get(k) or 0), 0.0) for k in ("kcal", "protein", "carbs", "fat")}
    # Sanity check: if calories don't agree with macros, trust the macros.
    atwater = v["protein"] * 4 + v["carbs"] * 4 + v["fat"] * 9
    if atwater and abs(v["kcal"] - atwater) / atwater > 0.25:
        v["kcal"] = atwater
    units = {str(k): float(g) for k, g in (d.get("units") or {}).items()
             if isinstance(g, (int, float)) and 0 < g < 2000}
    return {**v, "units": units, "aliases": []}


def resolve(items, estimate=True):
    """Return one row per item with per-100g values and computed totals."""
    rows = []
    for it in items:
        key, food, source = match_food(it["name"])
        if food is None:
            if not estimate:
                continue
            food, key, source = estimate_food(it["name"]), it["name"].lower(), "AI estimate"
        grams, exact = to_grams(it["quantity"], it["unit"], food["units"])
        rows.append({
            "item": key, "quantity": it["quantity"], "unit": it["unit"],
            "grams": round(grams, 1), "source": source if exact else f"{source} (check grams)",
            "remember": source == "AI estimate",
            "per100": {k: food[k] for k in ("kcal", "protein", "carbs", "fat")},
            "units": food["units"],
        })
    return rows


def totals_for(grams, per100):
    return {k: round(per100[k] * grams / 100, 1) for k in ("kcal", "protein", "carbs", "fat")}
