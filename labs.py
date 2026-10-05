"""Blood test reports: the model extracts, the code flags. Nothing is diagnosed."""
import io

import pandas as pd
import pdfplumber
from rapidfuzz import fuzz, process

import db
import llm

EXTRACT_SYSTEM = """Extract lab results from this blood test report text. JSON only:
{"test_date": "YYYY-MM-DD" or null,
 "results": [{"marker": str, "value": number, "unit": str,
              "ref_low": number or null, "ref_high": number or null}]}
Only include results with a numeric value. Use the report's own reference range.
"<200" means ref_high 200, ref_low null. ">40" means ref_low 40, ref_high null.
Use standard marker names (e.g. "Hemoglobin", "LDL Cholesterol", "Vitamin D (25-OH)").
Copy numbers exactly. Do not guess values that are not in the text."""

EXPLAIN_SYSTEM = """You explain blood test results to a 21-year-old gym-goer in plain language.
For each marker given: say in one sentence what it measures, and note anything about
training, diet or supplements that is commonly relevant. Then list 3 questions he could
ask his doctor. Do not diagnose, do not recommend medication or doses, and say clearly
that a doctor should interpret the results. Under 250 words."""


def pdf_text(raw: bytes):
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract(raw: bytes):
    text = pdf_text(raw)
    if len(text.strip()) < 50:
        raise ValueError("No text found. This looks like a scanned PDF; export a text PDF from the lab portal.")
    known = [r["marker"] for r in db.q("SELECT DISTINCT marker FROM lab_results")]
    date, rows = None, []
    for i in range(0, len(text), 6000):
        data = llm.chat_json(EXTRACT_SYSTEM, text[i:i + 6000])
        date = date or data.get("test_date")
        for r in data.get("results", []):
            value = _num(r.get("value"))
            if value is None or not r.get("marker"):
                continue
            marker = str(r["marker"]).strip()
            hit = process.extractOne(marker, known, scorer=fuzz.token_sort_ratio, score_cutoff=90) if known else None
            rows.append({"marker": hit[0] if hit else marker, "value": value,
                         "unit": r.get("unit") or "", "ref_low": _num(r.get("ref_low")),
                         "ref_high": _num(r.get("ref_high"))})
    df = pd.DataFrame(rows, columns=["marker", "value", "unit", "ref_low", "ref_high"])
    return date, df.drop_duplicates("marker")


def flag(row):
    if pd.notna(row.get("ref_low")) and row["value"] < row["ref_low"]:
        return "Low"
    if pd.notna(row.get("ref_high")) and row["value"] > row["ref_high"]:
        return "High"
    return "In range"


def save(test_date, df, source):
    db.xm("""INSERT INTO lab_results (test_date, marker, value, unit, ref_low, ref_high, source_file)
             VALUES (?,?,?,?,?,?,?)""",
          [(test_date, r.marker, r.value, r.unit,
            None if pd.isna(r.ref_low) else r.ref_low,
            None if pd.isna(r.ref_high) else r.ref_high, source)
           for r in df.itertuples()])


def explain(df):
    lines = [f"{r.marker}: {r.value} {r.unit} (range {r.ref_low}-{r.ref_high}) -> {r.flag}"
             for r in df.itertuples()]
    return llm.chat(EXPLAIN_SYSTEM, "\n".join(lines))
