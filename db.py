"""SQLite storage. Everything lives in data/spotter.db on this machine."""
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "data" / "spotter.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
  id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT, age INTEGER, sex TEXT,
  height_cm REAL, activity TEXT, deficit_pct REAL, protein_g_per_kg REAL);
CREATE TABLE IF NOT EXISTS weights (date TEXT PRIMARY KEY, kg REAL);
CREATE TABLE IF NOT EXISTS food_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, meal TEXT, item TEXT,
  quantity REAL, unit TEXT, grams REAL, kcal REAL, protein REAL, carbs REAL,
  fat REAL, source TEXT);
CREATE TABLE IF NOT EXISTS custom_foods (
  name TEXT PRIMARY KEY, kcal REAL, protein REAL, carbs REAL, fat REAL, units TEXT);
CREATE TABLE IF NOT EXISTS supplements (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, dose TEXT,
  timing TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS supplement_log (
  date TEXT, supplement_id INTEGER, taken INTEGER, PRIMARY KEY (date, supplement_id));
CREATE TABLE IF NOT EXISTS workout_plan (id INTEGER PRIMARY KEY CHECK (id = 1), plan_json TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS workout_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise TEXT, sets INTEGER,
  reps INTEGER, weight_kg REAL, rpe REAL, notes TEXT);
CREATE TABLE IF NOT EXISTS band_daily (
  date TEXT PRIMARY KEY, sleep_hours REAL, sleep_score REAL, resting_hr REAL,
  steps INTEGER, stress REAL);
CREATE TABLE IF NOT EXISTS lab_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT, test_date TEXT, marker TEXT, value REAL,
  unit TEXT, ref_low REAL, ref_high REAL, source_file TEXT);
CREATE TABLE IF NOT EXISTS coach_notes (week_start TEXT PRIMARY KEY, note TEXT, created TEXT);
"""

_ready = False


def conn():
    global _ready
    DB_PATH.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    if not _ready:
        c.executescript(SCHEMA)
        _ready = True
    return c


def q(sql, params=()):
    c = conn()
    try:
        return [dict(r) for r in c.execute(sql, params).fetchall()]
    finally:
        c.close()


def x(sql, params=()):
    c = conn()
    try:
        with c:
            c.execute(sql, params)
    finally:
        c.close()


def xm(sql, rows):
    c = conn()
    try:
        with c:
            c.executemany(sql, rows)
    finally:
        c.close()


def frame(sql, params=()):
    c = conn()
    try:
        return pd.read_sql_query(sql, c, params=params)
    finally:
        c.close()
