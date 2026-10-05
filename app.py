"""Spotter: a local-first training, nutrition and recovery log."""
import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import coach
import db
import labs
import llm
import nutrition
import samsung
import workouts

st.set_page_config(page_title="Spotter", page_icon="🏋️", layout="wide")

TODAY = date.today()


def get_profile():
    r = db.q("SELECT * FROM profile WHERE id = 1")
    return r[0] if r else None


def latest_weight():
    r = db.q("SELECT kg FROM weights ORDER BY date DESC LIMIT 1")
    return r[0]["kg"] if r else None


def model_call(label, fn, *args):
    """Run a model step with a spinner and a clear error if Ollama isn't running."""
    try:
        with st.spinner(label):
            return fn(*args)
    except Exception as e:  # noqa: BLE001
        st.error(f"The local model step failed: {e}. Check that Ollama is running "
                 f"and `{llm.MODEL}` is pulled.")
        return None


# ---------------- sidebar ----------------
profile = get_profile()
with st.sidebar:
    st.title("🏋️ Spotter")
    st.caption("Your log stays on this laptop.")
    st.markdown(f"Model `{llm.MODEL}`: " + ("running" if llm.is_up() else "**not running**, start Ollama"))
    pages = ["Today", "Log food", "Workouts", "Supplements", "Band & recovery",
             "Blood tests", "Weekly check-in", "Profile"]
    page = st.radio("Go to", pages, index=0 if profile else pages.index("Profile"))


# ---------------- pages ----------------
def page_profile():
    st.header("Profile and targets")
    p = profile or {"name": "", "age": 21, "sex": "Male", "height_cm": 175.0,
                    "activity": "Moderate (3-5 workouts/week)", "deficit_pct": 15.0,
                    "protein_g_per_kg": 2.0}
    with st.form("profile"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name", p["name"])
        age = c2.number_input("Age", 14, 90, int(p["age"]))
        sex = c3.selectbox("Sex (for the BMR formula)", ["Male", "Female"],
                           index=["Male", "Female"].index(p["sex"]))
        height = c1.number_input("Height (cm)", 120.0, 230.0, float(p["height_cm"]))
        weight = c2.number_input("Current weight (kg)", 35.0, 250.0, float(latest_weight() or 75.0))
        acts = list(nutrition.ACTIVITY)
        activity = c3.selectbox("Activity", acts, index=acts.index(p["activity"]))
        deficit = c1.slider("Calorie deficit (%)", 0, 30, int(p["deficit_pct"]),
                            help="10-20% is a common sustainable range while training.")
        protein = c2.slider("Protein (g per kg)", 1.2, 2.6, float(p["protein_g_per_kg"]), 0.1)
        if st.form_submit_button("Save profile"):
            db.x("INSERT OR REPLACE INTO profile VALUES (1,?,?,?,?,?,?,?)",
                 (name, age, sex, height, activity, deficit, protein))
            db.x("INSERT OR REPLACE INTO weights VALUES (?, ?)", (TODAY.isoformat(), weight))
            st.success("Saved profile")
            st.rerun()
    if profile and latest_weight():
        t = nutrition.targets(profile, latest_weight())
        st.subheader("Daily targets")
        c = st.columns(4)
        c[0].metric("Calories", f"{t['kcal']:.0f}", f"maintenance {t['tdee']:.0f}", delta_color="off")
        c[1].metric("Protein", f"{t['protein']:.0f} g")
        c[2].metric("Carbs", f"{t['carbs']:.0f} g")
        c[3].metric("Fat", f"{t['fat']:.0f} g")
        if t["floored"]:
            st.info("Target held at your BMR. Going lower than this tends to cost muscle and recovery.")


def macro_row(eaten, t):
    cols = st.columns(4)
    for col, (k, label, unit) in zip(cols, [("kcal", "Calories", ""), ("protein", "Protein", " g"),
                                             ("carbs", "Carbs", " g"), ("fat", "Fat", " g")]):
        col.metric(label, f"{eaten[k]:.0f} / {t[k]:.0f}{unit}", f"{t[k] - eaten[k]:.0f} left",
                   delta_color="off")
        col.progress(min(eaten[k] / t[k], 1.0) if t[k] else 0.0)


def supplement_checklist(day):
    sups = db.q("SELECT * FROM supplements WHERE active = 1 ORDER BY timing, name")
    if not sups:
        st.caption("No supplements yet. Add them on the Supplements page.")
        return
    taken = {r["supplement_id"]: r["taken"] for r in
             db.q("SELECT * FROM supplement_log WHERE date = ?", (day,))}
    for s in sups:
        label = f"{s['name']} · {s['dose'] or ''} · {s['timing'] or ''}".strip(" ·")
        v = st.checkbox(label, value=bool(taken.get(s["id"], 0)), key=f"sup_{s['id']}_{day}")
        if v != bool(taken.get(s["id"], 0)):
            db.x("INSERT OR REPLACE INTO supplement_log VALUES (?,?,?)", (day, s["id"], int(v)))


def weight_section():
    c1, c2 = st.columns([1, 3])
    with c1:
        w = st.number_input("Today's weight (kg)", 35.0, 250.0, float(latest_weight() or 75.0), 0.1)
        if st.button("Save weight"):
            db.x("INSERT OR REPLACE INTO weights VALUES (?, ?)", (TODAY.isoformat(), w))
            st.rerun()
    df = db.frame("SELECT date, kg FROM weights ORDER BY date")
    with c2:
        if len(df) >= 2:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            df["7-day average"] = df["kg"].rolling("7D").mean()
            st.line_chart(df)
            end = df.index.max()
            recent = df[df.index > end - pd.Timedelta(days=7)]["kg"]
            prior = df[(df.index <= end - pd.Timedelta(days=7)) & (df.index > end - pd.Timedelta(days=14))]["kg"]
            if len(prior) and len(recent):
                rate = recent.mean() - prior.mean()
                pct = 100 * rate / prior.mean()
                st.caption(f"Trend: {rate:+.2f} kg/week ({pct:+.1f}% of body weight).")
                if pct < -1:
                    st.caption("That's a fast cut. Watch whether your lifts and sleep hold up.")
        else:
            st.caption("Log your weight a few mornings in a row to see the trend.")


def page_today():
    st.header(f"Today, {TODAY.strftime('%A %d %b')}")
    w = latest_weight()
    t = nutrition.targets(profile, w)
    eaten = db.q("""SELECT COALESCE(SUM(kcal),0) kcal, COALESCE(SUM(protein),0) protein,
                    COALESCE(SUM(carbs),0) carbs, COALESCE(SUM(fat),0) fat
                    FROM food_log WHERE date = ?""", (TODAY.isoformat(),))[0]
    macro_row(eaten, t)

    left, right = st.columns(2)
    with left:
        st.subheader("Recovery")
        r = samsung.readiness(TODAY.isoformat())
        if r:
            st.metric("Readiness", f"{r['score']}/100")
            st.write(r["call"])
            st.caption(f"Based on: {r['why']}. A rough guide from your band data, not a medical score.")
        else:
            st.caption("No band data for today. Import your Samsung Health export on Band & recovery.")
        st.subheader("Supplements")
        supplement_checklist(TODAY.isoformat())
    with right:
        st.subheader("Today's workout")
        d = workouts.plan_for(workouts.WEEKDAYS[TODAY.weekday()])
        if d:
            st.write(f"**{d['focus']}**")
            st.dataframe(pd.DataFrame(d["exercises"])[["name", "sets", "reps", "rest_sec", "notes"]],
                         hide_index=True, width="stretch")
        else:
            st.caption("Rest day, or no plan yet. Build one on the Workouts page.")
    st.subheader("Weight")
    weight_section()


def page_food():
    st.header("Log food")
    c1, c2 = st.columns(2)
    day = c1.date_input("Date", TODAY).isoformat()
    meal = c2.selectbox("Meal", ["Breakfast", "Lunch", "Dinner", "Snack", "Pre-workout", "Post-workout"])
    text = st.text_area("What did you eat?", placeholder="3 eggs, 2 rotis with dal, a scoop of whey in milk")
    if st.button("Read my meal", type="primary") and text.strip():
        items = model_call("Reading your meal...", nutrition.parse_meal, text)
        if items:
            rows = model_call("Looking up nutrition...", nutrition.resolve, items)
            st.session_state["parsed"] = rows

    rows = st.session_state.get("parsed")
    if rows:
        st.caption("Check the grams. Calories and macros are recalculated from your edits.")
        df = pd.DataFrame([{k: r[k] for k in ("item", "quantity", "unit", "grams", "source", "remember")}
                           for r in rows])
        edited = st.data_editor(
            df, hide_index=True, width="stretch", key="food_editor",
            disabled=["item", "quantity", "unit", "source"],
            column_config={"grams": st.column_config.NumberColumn("Grams", min_value=0.0, step=5.0),
                           "remember": st.column_config.CheckboxColumn(
                               "Save food", help="Keep this AI estimate as a custom food")})
        totals = [nutrition.totals_for(g, r["per100"]) for g, r in zip(edited["grams"], rows)]
        tdf = pd.DataFrame(totals)
        st.write(f"**Meal total:** {tdf.kcal.sum():.0f} kcal · {tdf.protein.sum():.0f} g protein · "
                 f"{tdf.carbs.sum():.0f} g carbs · {tdf.fat.sum():.0f} g fat")
        if st.button("Save to log"):
            db.xm("""INSERT INTO food_log (date, meal, item, quantity, unit, grams, kcal, protein,
                     carbs, fat, source) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  [(day, meal, r["item"], r["quantity"], r["unit"], float(g), t["kcal"], t["protein"],
                    t["carbs"], t["fat"], r["source"])
                   for r, g, t in zip(rows, edited["grams"], totals)])
            for r, keep in zip(rows, edited["remember"]):
                if keep and r["source"].startswith("AI estimate"):
                    p = r["per100"]
                    db.x("INSERT OR REPLACE INTO custom_foods VALUES (?,?,?,?,?,?)",
                         (r["item"], p["kcal"], p["protein"], p["carbs"], p["fat"], json.dumps(r["units"])))
            st.session_state.pop("parsed")
            st.success("Saved to log")
            st.rerun()

    st.subheader(f"Logged on {day}")
    log = db.frame("""SELECT id, meal, item, grams, kcal, protein, carbs, fat, source
                      FROM food_log WHERE date = ? ORDER BY id""", (day,))
    if len(log):
        log.insert(0, "delete", False)
        ed = st.data_editor(log, hide_index=True, width="stretch",
                            disabled=[c for c in log.columns if c != "delete"], key="log_editor")
        if st.button("Delete selected"):
            for i in ed.loc[ed["delete"], "id"]:
                db.x("DELETE FROM food_log WHERE id = ?", (int(i),))
            st.rerun()
    else:
        st.caption("Nothing logged for this day yet.")


def page_workouts():
    st.header("Workouts")
    tab_plan, tab_log, tab_prog = st.tabs(["Plan", "Log sets", "Progress"])
    with tab_plan:
        with st.form("plan"):
            days = st.multiselect("Training days", workouts.WEEKDAYS, ["Mon", "Tue", "Thu", "Fri", "Sat"])
            c1, c2, c3 = st.columns(3)
            equipment = c1.selectbox("Equipment", list(workouts.EQUIPMENT))
            experience = c2.selectbox("Experience", ["Beginner", "Intermediate", "Advanced"], 1)
            minutes = c3.slider("Session length (min)", 30, 120, 60, 15)
            focus = st.text_input("Goals and preferences",
                                  "Keep strength while cutting, bring up chest and back")
            go = st.form_submit_button("Build my plan", type="primary")
        if go and days:
            plan = model_call("Building your plan...", workouts.generate, days, equipment,
                              experience, minutes, focus)
            if plan:
                workouts.save_plan(plan)
                st.success("Saved your plan")
            elif plan is not None:
                st.warning("The model's plan didn't match the exercise library. Try again.")
        for d in workouts.get_plan():
            st.markdown(f"**{d['day']}: {d['focus']}**")
            st.dataframe(pd.DataFrame(d["exercises"]), hide_index=True, width="stretch")

    with tab_log:
        c1, c2 = st.columns(2)
        day = c1.date_input("Date", TODAY, key="wdate")
        planned = workouts.plan_for(workouts.WEEKDAYS[day.weekday()])
        options = [e["name"] for e in planned["exercises"]] if planned else []
        options += [n for n in workouts.LIBRARY if n not in options]
        with st.form("log_set", clear_on_submit=False):
            ex = st.selectbox("Exercise", options)
            c = st.columns(4)
            sets = c[0].number_input("Sets", 1, 10, 3)
            reps = c[1].number_input("Reps", 1, 50, 8)
            kg = c[2].number_input("Weight (kg)", 0.0, 400.0, 20.0, 2.5)
            rpe = c[3].number_input("RPE", 5.0, 10.0, 8.0, 0.5)
            if st.form_submit_button("Add sets"):
                db.x("""INSERT INTO workout_log (date, exercise, sets, reps, weight_kg, rpe, notes)
                        VALUES (?,?,?,?,?,?,'')""", (day.isoformat(), ex, sets, reps, kg, rpe))
                st.success(f"Logged {sets} x {reps} @ {kg} kg {ex}")
        st.dataframe(db.frame("""SELECT exercise, sets, reps, weight_kg, rpe FROM workout_log
                                 WHERE date = ? ORDER BY id""", (day.isoformat(),)),
                     hide_index=True, width="stretch")

    with tab_prog:
        hist = db.frame("SELECT date, exercise, reps, weight_kg FROM workout_log")
        if len(hist):
            ex = st.selectbox("Exercise", sorted(hist.exercise.unique()))
            h = hist[hist.exercise == ex].copy()
            h["Estimated 1RM (kg)"] = [workouts.e1rm(w, r) for w, r in zip(h.weight_kg, h.reps)]
            st.line_chart(h.groupby("date")["Estimated 1RM (kg)"].max())
            st.caption("If this line holds steady while your weight drops, the cut is going well.")
        else:
            st.caption("Log a few sessions to see strength trends.")


def page_supplements():
    st.header("Supplements")
    with st.form("add_sup", clear_on_submit=True):
        c = st.columns(3)
        name = c[0].text_input("Name", placeholder="Creatine monohydrate")
        dose = c[1].text_input("Dose", placeholder="5 g")
        timing = c[2].selectbox("Timing", ["Morning", "Pre-workout", "Post-workout", "With lunch",
                                           "With dinner", "Before bed"])
        if st.form_submit_button("Add supplement") and name.strip():
            db.x("INSERT OR REPLACE INTO supplements (name, dose, timing, active) VALUES (?,?,?,1)",
                 (name.strip(), dose, timing))
            st.rerun()
    st.subheader("Today")
    supplement_checklist(TODAY.isoformat())

    sups = db.frame("SELECT id, name, dose, timing, active FROM supplements ORDER BY name")
    if len(sups):
        st.subheader("Last 14 days")
        log = db.frame("""SELECT s.name, l.date, l.taken FROM supplement_log l
                          JOIN supplements s ON s.id = l.supplement_id
                          WHERE l.date >= date('now', '-14 day')""")
        if len(log):
            st.bar_chart(log.groupby("name")["taken"].sum())
        st.subheader("Manage")
        ed = st.data_editor(sups, hide_index=True, disabled=["id", "name"], key="sup_editor",
                            column_config={"active": st.column_config.CheckboxColumn("Active")})
        if st.button("Save changes"):
            for r in ed.itertuples():
                db.x("UPDATE supplements SET dose=?, timing=?, active=? WHERE id=?",
                     (r.dose, r.timing, int(r.active), int(r.id)))
            st.rerun()
        if st.button("Review my stack"):
            stack = "\n".join(f"{r.name}, {r.dose}, {r.timing}" for r in sups.itertuples() if r.active)
            note = model_call("Reviewing...", llm.chat,
                              "You review a gym-goer's supplement list. Comment only on timing and on "
                              "commonly known spacing between items (e.g. iron and calcium). No doses, "
                              "no medical advice. End by suggesting he confirm with a pharmacist or "
                              "doctor. Under 150 words.", stack)
            if note:
                st.info(note)


def page_band():
    st.header("Band & recovery")
    st.caption("In Samsung Health: profile → Settings → Download personal data. Zip the exported "
               "folder (or pick the CSVs) and upload it here. Nothing is sent anywhere.")
    files = st.file_uploader("Samsung Health export", type=["zip", "csv"], accept_multiple_files=True)
    if files and st.button("Import", type="primary"):
        daily, used = samsung.parse_files([(f.name, f.getvalue()) for f in files])
        if len(daily):
            n = samsung.save(daily)
            st.success(f"Imported {n} days from {len(used)} files")
        else:
            st.warning("No sleep, heart rate, steps or stress files were found in that upload.")
    r = samsung.readiness(TODAY.isoformat())
    if r:
        st.metric("Today's readiness", f"{r['score']}/100")
        st.write(r["call"])
    df = db.frame("SELECT * FROM band_daily WHERE date >= date('now', '-30 day') ORDER BY date")
    if len(df):
        df = df.set_index("date")
        c1, c2 = st.columns(2)
        c1.subheader("Sleep (hours)")
        c1.bar_chart(df["sleep_hours"])
        c2.subheader("Resting heart rate")
        c2.line_chart(df["resting_hr"])
        c1.subheader("Steps")
        c1.bar_chart(df["steps"])
        c2.subheader("Stress")
        c2.line_chart(df["stress"])


def page_labs():
    st.header("Blood tests")
    st.caption("Spotter reads the report and flags values outside the lab's own range. "
               "It does not diagnose. Take anything flagged to a doctor.")
    up = st.file_uploader("Lab report (PDF)", type=["pdf"])
    if up and st.button("Read report", type="primary"):
        res = model_call("Reading the report...", labs.extract, up.getvalue())
        if res:
            st.session_state["lab"] = (res[0], res[1], up.name)
    if "lab" in st.session_state:
        d, df, name = st.session_state["lab"]
        test_date = st.date_input("Test date", pd.to_datetime(d).date() if d else TODAY)
        st.caption("Check every value against the PDF before saving.")
        edited = st.data_editor(df, hide_index=True, width="stretch", num_rows="dynamic")
        if st.button("Save results"):
            labs.save(test_date.isoformat(), edited.dropna(subset=["marker", "value"]), name)
            st.session_state.pop("lab")
            st.success("Saved results")
            st.rerun()

    all_res = db.frame("SELECT * FROM lab_results ORDER BY test_date")
    if len(all_res):
        latest_date = all_res.test_date.max()
        latest = all_res[all_res.test_date == latest_date].copy()
        latest["flag"] = latest.apply(labs.flag, axis=1)
        st.subheader(f"Latest report ({latest_date})")
        st.dataframe(latest[["marker", "value", "unit", "ref_low", "ref_high", "flag"]],
                     hide_index=True, width="stretch")
        flagged = latest[latest.flag != "In range"]
        if len(flagged) and st.button(f"Explain the {len(flagged)} flagged results"):
            txt = model_call("Explaining...", labs.explain, flagged)
            if txt:
                st.info(txt)
        st.subheader("Trends")
        m = st.selectbox("Marker", sorted(all_res.marker.unique()))
        st.line_chart(all_res[all_res.marker == m].set_index("test_date")["value"])


def page_coach():
    st.header("Weekly check-in")
    monday = TODAY - timedelta(days=TODAY.weekday())
    week = st.date_input("Week starting", monday - timedelta(days=7))
    week = week - timedelta(days=week.weekday())
    stats = coach.week_stats(week, profile)
    c = st.columns(4)
    show = lambda v, s="": "–" if v is None else f"{v}{s}"
    c[0].metric("Avg calories", show(stats["avg_calories"]), f"target {show(stats['calorie_target'])}",
                delta_color="off")
    c[1].metric("Protein target hit", f"{stats['days_protein_target_hit']}/7 days")
    c[2].metric("Training days", stats["training_days"], f"{stats['total_working_sets']} sets",
                delta_color="off")
    c[3].metric("Avg sleep", show(stats["avg_sleep_hours"], " h"))
    if st.button("Write my check-in", type="primary"):
        note = model_call("Writing your check-in...", coach.write_note, stats, week)
        if note:
            st.info(note)
    for n in db.q("SELECT * FROM coach_notes ORDER BY week_start DESC LIMIT 6"):
        with st.expander(f"Week of {n['week_start']}"):
            st.write(n["note"])


if page != "Profile" and not (profile and latest_weight()):
    st.info("Set up your profile first so Spotter can work out your targets.")
    page_profile()
else:
    {"Today": page_today, "Log food": page_food, "Workouts": page_workouts,
     "Supplements": page_supplements, "Band & recovery": page_band, "Blood tests": page_labs,
     "Weekly check-in": page_coach, "Profile": page_profile}[page]()
