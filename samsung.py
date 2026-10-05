"""Import Samsung Health 'Download personal data' CSV exports (Galaxy Fit / Watch).

Samsung's export is a folder of CSVs. Each file starts with a metadata line,
then a header whose columns look like `com.samsung.health.sleep.start_time`.
Column sets differ between app versions, so this parser is deliberately tolerant.
"""
import io
import os
import zipfile

import pandas as pd

import db


def _read(raw: bytes):
    lines = raw.decode("utf-8-sig", errors="ignore").splitlines()
    if len(lines) < 2:
        return None
    start = 1 if lines[0].count(",") < lines[1].count(",") else 0
    try:
        df = pd.read_csv(io.StringIO("\n".join(lines[start:])), index_col=False, low_memory=False)
    except Exception:
        return None
    df.columns = [str(c).split(".")[-1].strip() for c in df.columns]
    return df.loc[:, ~pd.Index(df.columns).duplicated()]


def _time(df, col):
    s = df[col]
    if pd.api.types.is_numeric_dtype(s):
        t = pd.to_datetime(s, unit="ms", errors="coerce")
    else:
        t = pd.to_datetime(s, errors="coerce")
    if "time_offset" in df.columns:  # Samsung stores UTC plus an offset like UTC+0530
        m = df["time_offset"].astype(str).str.extract(r"UTC([+-])(\d{2})(\d{2})")
        mins = (m[1].astype(float) * 60 + m[2].astype(float)).fillna(0)
        sign = m[0].map({"+": 1, "-": -1}).fillna(0)
        t = t + pd.to_timedelta(sign * mins, unit="m")
    return t


def _sleep(df):
    if not {"start_time", "end_time"} <= set(df.columns):
        return None
    s, e = _time(df, "start_time"), _time(df, "end_time")
    hours = (e - s).dt.total_seconds() / 3600
    d = pd.DataFrame({"date": e.dt.date.astype(str), "sleep_hours": hours})
    if "sleep_score" in df.columns:
        d["sleep_score"] = pd.to_numeric(df["sleep_score"], errors="coerce")
    d = d[(d.sleep_hours > 0) & (d.sleep_hours < 16)]
    agg = {"sleep_hours": "sum"}
    if "sleep_score" in d:
        agg["sleep_score"] = "mean"
    return d.groupby("date").agg(agg)


def _heart(df):
    if "heart_rate" not in df.columns or "start_time" not in df.columns:
        return None
    hr = pd.to_numeric(df["heart_rate"], errors="coerce")
    d = pd.DataFrame({"date": _time(df, "start_time").dt.date.astype(str), "hr": hr})
    d = d[(d.hr > 30) & (d.hr < 220)]
    g = d.groupby("date")["hr"]
    # Resting HR estimate: 5th percentile of the day's readings.
    out = g.quantile(0.05).to_frame("resting_hr")
    return out[g.count() >= 6]


def _steps(df):
    col = next((c for c in ("count", "step_count") if c in df.columns), None)
    if col is None or "day_time" not in df.columns:
        return None
    d = pd.DataFrame({"date": _time(df, "day_time").dt.date.astype(str),
                      "steps": pd.to_numeric(df[col], errors="coerce")})
    return d.groupby("date")["steps"].max().to_frame()


def _stress(df):
    if "score" not in df.columns or "start_time" not in df.columns:
        return None
    d = pd.DataFrame({"date": _time(df, "start_time").dt.date.astype(str),
                      "stress": pd.to_numeric(df["score"], errors="coerce")})
    return d.groupby("date")["stress"].mean().to_frame()


def _kind(name):
    n = os.path.basename(name).lower()
    if "sleep" in n and not any(s in n for s in ("stage", "combined", "snor", "goal", "raw")):
        return _sleep
    if "heart_rate" in n and "recovery" not in n:
        return _heart
    if "step_daily_trend" in n or "pedometer_day_summary" in n:
        return _steps
    if "stress" in n and "histogram" not in n:
        return _stress
    return None


def parse_files(files):
    """files: list of (filename, bytes); zips are expanded. Returns a daily DataFrame."""
    expanded = []
    for name, raw in files:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                expanded += [(m, z.read(m)) for m in z.namelist() if m.lower().endswith(".csv")]
        else:
            expanded.append((name, raw))

    parts, used = [], []
    for name, raw in expanded:
        fn = _kind(name)
        if not fn:
            continue
        df = _read(raw)
        out = fn(df) if df is not None else None
        if out is not None and len(out):
            parts.append(out)
            used.append(os.path.basename(name))
    if not parts:
        return pd.DataFrame(), used
    daily = pd.concat(parts, axis=1)
    daily = daily.T.groupby(level=0).max().T  # merge duplicate columns from multiple files
    return daily.sort_index(), used


def save(daily):
    cols = ["sleep_hours", "sleep_score", "resting_hr", "steps", "stress"]
    rows = []
    for date, r in daily.iterrows():
        vals = [None if c not in r or pd.isna(r[c]) else float(r[c]) for c in cols]
        rows.append([date, *vals])
    db.xm(f"""INSERT INTO band_daily (date, {', '.join(cols)}) VALUES (?,?,?,?,?,?)
        ON CONFLICT(date) DO UPDATE SET
        {', '.join(f'{c}=COALESCE(excluded.{c}, band_daily.{c})' for c in cols)}""", rows)
    return len(rows)


def readiness(day):
    """A simple, transparent heuristic, not a medical score.
    Compares last night's sleep, resting HR and stress against a 14-day baseline."""
    today = db.q("SELECT * FROM band_daily WHERE date = ?", (day,))
    if not today:
        return None
    t = today[0]
    base = db.frame("""SELECT * FROM band_daily WHERE date < ? AND date >= date(?, '-14 day')""",
                    (day, day))
    clamp = lambda v: max(0.0, min(1.0, v))
    parts, why = [], []
    if t["sleep_hours"]:
        s = clamp(t["sleep_hours"] / 8)
        if t["sleep_score"]:
            s = 0.5 * s + 0.5 * clamp(t["sleep_score"] / 100)
        parts.append((s, 0.5))
        why.append(f"slept {t['sleep_hours']:.1f} h")
    if t["resting_hr"] and len(base) and base["resting_hr"].notna().sum() >= 3:
        b = base["resting_hr"].mean()
        parts.append((clamp(0.5 + (b - t["resting_hr"]) * 0.08), 0.3))
        why.append(f"resting HR {t['resting_hr']:.0f} vs usual {b:.0f}")
    if t["stress"] is not None:
        parts.append((clamp(1 - t["stress"] / 100), 0.2))
        why.append(f"stress {t['stress']:.0f}")
    if not parts:
        return None
    score = round(100 * sum(v * w for v, w in parts) / sum(w for _, w in parts))
    if score >= 75:
        call = "Ready to push. Go for top sets today."
    elif score >= 55:
        call = "Train as planned."
    else:
        call = "Go lighter: drop a set per exercise and keep effort around RPE 7."
    return {"score": score, "call": call, "why": ", ".join(why)}
