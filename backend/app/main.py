
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import DATABASE_URL
from app.dataset import load_dataset, get_dataset_summary

app = FastAPI(
    title="EduCare AI API",
    description="Government School Monitoring and Assistance Dashboard",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    return psycopg2.connect(DATABASE_URL)


@app.get("/")
def home():
    return {
        "message": "Welcome to EduCare AI API",
        "status": "running"
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/dataset/summary")
def dataset_summary():
    return get_dataset_summary()


@app.get("/api/dataset/states")
def dataset_states():
    df = load_dataset()
    return df[
        [
            "India/State/ UT",
            "gender_gap",
            "girls_enrolment_percentage"
        ]
    ].to_dict(orient="records")


@app.get("/api/dashboard/summary")
def dashboard_summary():
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) AS total_schools,
                        COUNT(*) FILTER (WHERE category = 'Excellent') AS excellent,
                        COUNT(*) FILTER (WHERE category = 'Good') AS good,
                        COUNT(*) FILTER (WHERE category = 'Poor') AS poor,
                        COUNT(*) FILTER (WHERE category = 'Critical') AS critical,
                        COUNT(*) FILTER (WHERE category = 'Insufficient Data') AS insufficient_data,
                        COALESCE(ROUND(AVG(need_score), 1), 0) AS average_need_score
                    FROM v_school_overview
                """)
                return dict(cur.fetchone())
    except psycopg2.Error as exc:
        raise HTTPException(status_code=500, detail="Database query failed") from exc


@app.get("/api/schools")
def get_schools(
    category: str | None = Query(default=None),
    district: str | None = Query(default=None),
    search: str | None = Query(default=None)
):
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        id, udise_code, name, school_type, district, locality,
                        students, teachers, attendance_pct, academic_score,
                        need_score, category, score_status, data_completeness
                    FROM v_school_overview
                    WHERE (%s IS NULL OR category = %s)
                    AND (%s IS NULL OR district ILIKE %s)
                    AND (%s IS NULL OR name ILIKE %s OR udise_code ILIKE %s)
                    ORDER BY need_score DESC NULLS FIRST, name
                """, (
                    category, category,
                    district, f"%{district}%" if district else None,
                    search, f"%{search}%" if search else None,
                    f"%{search}%" if search else None
                ))
                return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise HTTPException(status_code=500, detail="Database query failed") from exc


@app.get("/api/schools/{school_id}")
def get_school(school_id: int):
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM v_school_overview WHERE id = %s
                """, (school_id,))
                school = cur.fetchone()

                if school is None:
                    raise HTTPException(status_code=404, detail="School not found")

                cur.execute("""
                    SELECT academic_year, attendance_pct, academic_score
                    FROM school_history
                    WHERE school_id = %s
                    ORDER BY academic_year
                """, (school_id,))
                history = [dict(row) for row in cur.fetchall()]

                cur.execute("""
                    SELECT category, item, quantity, unit_cost,
                           estimated_cost, priority
                    FROM school_needs
                    WHERE school_id = %s
                    ORDER BY priority
                """, (school_id,))
                needs = [dict(row) for row in cur.fetchall()]

                cur.execute("""
                    SELECT need_score, category, status, data_completeness,
                           components, reasons, missing_fields, scoring_version
                    FROM school_scores
                    WHERE school_id = %s
                """, (school_id,))
                score = cur.fetchone()

                return {
                    "school": dict(school),
                    "score_details": dict(score) if score else None,
                    "history": history,
                    "needs": needs
                }
    except HTTPException:
        raise
    except psycopg2.Error as exc:
        raise HTTPException(status_code=500, detail="Database query failed") from exc



@app.get("/api/schools/urgent/list")
def urgent_schools():
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        v.id,
                        v.name,
                        v.district,
                        v.locality,
                        v.students,
                        v.need_score,
                        v.category,
                        sc.reasons
                    FROM v_school_overview v
                    JOIN school_scores sc ON sc.school_id = v.id
                    WHERE v.category = 'Critical'
                    ORDER BY v.need_score DESC NULLS FIRST
                """)
                return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Database query failed"
        ) from exc

