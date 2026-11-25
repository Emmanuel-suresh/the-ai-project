import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scoring import WEIGHTS, calculate_need_score, classify

BEST = dict(students=200, teachers=8, classrooms_total=8, classrooms_good=8, functional_toilets=6,
            girls_toilet=True, drinking_water=True, electricity=True, computers=30, internet=True,
            attendance_pct=96, academic_score=85)
WORST = dict(students=600, teachers=5, classrooms_total=8, classrooms_good=0, functional_toilets=2,
             girls_toilet=False, drinking_water=False, electricity=False, computers=0, internet=False,
             attendance_pct=55, academic_score=30)


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_best_school_is_excellent_zero():
    r = calculate_need_score(BEST)
    assert r["need_score"] == 0.0 and r["category"] == "Excellent" and r["status"] == "scored"


def test_worst_school_is_critical_100():
    r = calculate_need_score(WORST)
    assert r["need_score"] == 100.0 and r["category"] == "Critical"
    assert len(r["reasons"]) >= 6


def test_category_boundaries():
    for score, cat in [(0, "Excellent"), (19.9, "Excellent"), (20, "Good"), (39.9, "Good"),
                       (40, "Poor"), (69.9, "Poor"), (70, "Critical"), (100, "Critical")]:
        assert classify(score) == cat


def test_contributions_add_up_to_score():
    r = calculate_need_score({**WORST, "attendance_pct": 80, "academic_score": 60})
    total = sum(c["contribution"] for c in r["components"].values())
    assert abs(total - r["need_score"]) < 0.5


def test_partial_data_is_flagged_not_guessed():
    r = calculate_need_score({**BEST, "attendance_pct": None})
    assert r["status"] == "partial" and "Attendance" in r["missing_fields"]
    assert r["data_completeness"] == 85.0 and r["need_score"] is not None


def test_insufficient_data_gets_no_score():
    r = calculate_need_score({**BEST, "attendance_pct": None, "teachers": None, "academic_score": None})
    assert r["status"] == "insufficient_data" and r["need_score"] is None
    assert r["category"] == "Insufficient Data"


def test_text_values_from_uploads_are_understood():
    r = calculate_need_score({**WORST, "electricity": "No", "internet": "NO", "drinking_water": "n"})
    assert r["category"] == "Critical"
    r2 = calculate_need_score({**BEST, "electricity": "yes", "attendance_pct": "NA"})
    assert r2["status"] == "partial"
