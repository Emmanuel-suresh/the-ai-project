"""
Create the tables, load the fictional sample schools and calculate every score.

Usage (from the backend folder, virtualenv active):
    python scripts/seed_db.py            # create tables if missing, then load sample data
    python scripts/seed_db.py --reset    # WIPE the database first, then load sample data
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import Json, execute_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import DATA_DIR, DATABASE_URL, SCHEMA_FILE  # noqa: E402
from app.scoring import calculate_need_score  # noqa: E402

BOOL_COLS = ["girls_toilet", "drinking_water", "electricity", "internet", "is_fictional"]
SCHOOL_COLS = ["udise_code", "name", "school_type", "district", "locality", "latitude", "longitude",
               "students", "teachers", "classrooms_total", "classrooms_good", "functional_toilets",
               "girls_toilet", "drinking_water", "electricity", "computers", "internet",
               "attendance_pct", "academic_score", "is_fictional"]


def clean(v):
    """Turn pandas blanks into None and numpy numbers into plain Python numbers."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    return v.item() if hasattr(v, "item") else v


def to_records(df: pd.DataFrame) -> list[dict]:
    out = []
    for r in df.to_dict("records"):
        rec = {k: clean(v) for k, v in r.items()}
        for c in BOOL_COLS:
            if c in rec and rec[c] is not None:
                rec[c] = str(rec[c]).strip().lower() in {"yes", "y", "true", "1"}
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop everything first")
    args = ap.parse_args()

    schools = to_records(pd.read_csv(DATA_DIR / "sample_schools.csv"))
    history = to_records(pd.read_csv(DATA_DIR / "sample_school_history.csv"))

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn, conn.cursor() as cur:
            if args.reset:
                cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            cur.execute(SCHEMA_FILE.read_text())

            execute_values(cur, f"""
                INSERT INTO schools ({", ".join(SCHOOL_COLS)}) VALUES %s
                ON CONFLICT (udise_code) DO UPDATE SET
                {", ".join(f"{c} = EXCLUDED.{c}" for c in SCHOOL_COLS[1:])}, updated_at = now()
                RETURNING id, udise_code""",
                [tuple(s.get(c) for c in SCHOOL_COLS) for s in schools])
            ids = {code: sid for sid, code in cur.fetchall()}

            execute_values(cur, """
                INSERT INTO school_scores (school_id, need_score, category, status, data_completeness,
                    components, reasons, missing_fields, scoring_version) VALUES %s
                ON CONFLICT (school_id) DO UPDATE SET need_score = EXCLUDED.need_score,
                    category = EXCLUDED.category, status = EXCLUDED.status,
                    data_completeness = EXCLUDED.data_completeness, components = EXCLUDED.components,
                    reasons = EXCLUDED.reasons, missing_fields = EXCLUDED.missing_fields,
                    scoring_version = EXCLUDED.scoring_version, calculated_at = now()""",
                [(ids[s["udise_code"]], r["need_score"], r["category"], r["status"], r["data_completeness"],
                  Json(r["components"]), Json(r["reasons"]), Json(r["missing_fields"]), r["scoring_version"])
                 for s in schools for r in [calculate_need_score(s)]])

            execute_values(cur, """
                INSERT INTO school_history (school_id, academic_year, attendance_pct, academic_score) VALUES %s
                ON CONFLICT (school_id, academic_year) DO UPDATE SET
                    attendance_pct = EXCLUDED.attendance_pct, academic_score = EXCLUDED.academic_score""",
                [(ids[h["udise_code"]], h["academic_year"], h["attendance_pct"], h["academic_score"]) for h in history])

            cur.execute("SELECT category, COUNT(*) FROM school_scores GROUP BY category ORDER BY 2 DESC")
            summary = cur.fetchall()
        print(f"Loaded {len(schools)} fictional schools and {len(history)} history rows.")
        for cat, count in summary:
            print(f"  {cat:<18}{count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
