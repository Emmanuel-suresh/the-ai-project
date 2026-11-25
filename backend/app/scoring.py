"""
Transparent weighted School Need Score.

Score range 0-100. HIGHER = GREATER NEED.

Each of six indicators is converted to a 0-100 "need" value (0 = no problem,
100 = worst case) and combined using fixed weights:

    Infrastructure 25% | Water & sanitation 20% | Attendance 15%
    Teacher availability 15% | Academic performance 15% | Technology 10%

Bands: 0-19 Excellent, 20-39 Good, 40-69 Poor, 70-100 Critical.

Missing data is never guessed. Indicators with no usable data are left out and
the remaining weights are re-scaled. If less than MIN_COMPLETENESS % of the
weighting is backed by data, the school is labelled "Insufficient Data" and
receives no score or category.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Mapping, Optional

SCORING_VERSION = "1.0"
MIN_COMPLETENESS = 70.0

WEIGHTS = {
    "infrastructure": 0.25,
    "water_sanitation": 0.20,
    "attendance": 0.15,
    "teachers": 0.15,
    "academic": 0.15,
    "technology": 0.10,
}
LABELS = {
    "infrastructure": "Infrastructure",
    "water_sanitation": "Water and sanitation",
    "attendance": "Attendance",
    "teachers": "Teacher availability",
    "academic": "Academic performance",
    "technology": "Technology",
}
CATEGORY_BANDS = [(20, "Excellent"), (40, "Good"), (70, "Poor"), (101, "Critical")]


# ---------- input cleaning ----------
def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, str) and v.strip().lower() in {"", "na", "n/a", "nan", "null", "none", "-"}:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and math.isnan(v)) else bool(v)
    s = str(v).strip().lower()
    if s in {"yes", "y", "true", "1", "available"}:
        return True
    if s in {"no", "n", "false", "0", "unavailable"}:
        return False
    return None


def _scale(value: float, best: float, worst: float) -> float:
    """Linear 0-100: 0 at `best`, 100 at `worst` (works in either direction)."""
    return max(0.0, min(100.0, (value - best) / (worst - best) * 100.0))


def _blend(parts: list[tuple[float, Optional[float]]]) -> Optional[float]:
    """Weighted mean of the sub-parts that have data; None if none do."""
    avail = [(w, v) for w, v in parts if v is not None]
    if not avail:
        return None
    return sum(w * v for w, v in avail) / sum(w for w, _ in avail)


# ---------- indicators: each returns (need 0-100 or None, [findings]) ----------
Result = tuple[Optional[float], list[str]]


def _infrastructure(s: Mapping[str, Any]) -> Result:
    students, rooms = _num(s.get("students")), _num(s.get("classrooms_total"))
    good, elec = _num(s.get("classrooms_good")), _bool(s.get("electricity"))
    notes: list[str] = []
    cond = crowd = power = None
    if rooms and good is not None:
        pct = 100 * good / rooms
        cond = 100 - pct
        if pct < 60:
            notes.append(f"Only {good:.0f} of {rooms:.0f} classrooms ({pct:.0f}%) are in good condition")
    if rooms and students is not None:
        spc = students / rooms
        crowd = _scale(spc, 30, 60)
        if spc > 40:
            notes.append(f"Overcrowded classrooms: {spc:.0f} students per classroom (norm: about 30)")
    if elec is not None:
        power = 0.0 if elec else 100.0
        if not elec:
            notes.append("No electricity connection")
    return _blend([(0.60, cond), (0.25, crowd), (0.15, power)]), notes


def _water_sanitation(s: Mapping[str, Any]) -> Result:
    water, girls = _bool(s.get("drinking_water")), _bool(s.get("girls_toilet"))
    students, toilets = _num(s.get("students")), _num(s.get("functional_toilets"))
    notes: list[str] = []
    w = t = g = None
    if water is not None:
        w = 0.0 if water else 100.0
        if not water:
            notes.append("No safe drinking water on campus")
    if students is not None and toilets is not None:
        if toilets <= 0:
            t = 100.0
            notes.append("No functional toilets")
        else:
            spt = students / toilets
            t = _scale(spt, 40, 120)
            if spt > 60:
                notes.append(f"Too few toilets: {spt:.0f} students per functional toilet (norm: about 40)")
    if girls is not None:
        g = 0.0 if girls else 100.0
        if not girls:
            notes.append("No separate toilet for girls")
    return _blend([(0.40, w), (0.40, t), (0.20, g)]), notes


def _attendance(s: Mapping[str, Any]) -> Result:
    a = _num(s.get("attendance_pct"))
    if a is None:
        return None, []
    notes = [f"Attendance is {a:.0f}% (target: 95%)"] if a < 85 else []
    return _scale(a, 95, 60), notes


def _teachers(s: Mapping[str, Any]) -> Result:
    students, teachers = _num(s.get("students")), _num(s.get("teachers"))
    if students is None or teachers is None:
        return None, []
    if teachers <= 0:
        return 100.0, ["No teachers are posted at this school"]
    ptr = students / teachers
    notes = [f"Teacher shortage: {ptr:.0f} students per teacher (recommended maximum: about 30)"] if ptr > 35 else []
    return _scale(ptr, 25, 60), notes


def _academic(s: Mapping[str, Any]) -> Result:
    a = _num(s.get("academic_score"))
    if a is None:
        return None, []
    notes = [f"Average academic score is {a:.0f}% (benchmark: 80%)"] if a < 60 else []
    return _scale(a, 80, 40), notes


def _technology(s: Mapping[str, Any]) -> Result:
    students, computers = _num(s.get("students")), _num(s.get("computers"))
    net = _bool(s.get("internet"))
    notes: list[str] = []
    c = n = None
    if students and computers is not None:
        per100 = 100 * computers / students
        c = _scale(per100, 10, 0)
        if computers == 0:
            notes.append("No computers available for students")
        elif per100 < 3:
            notes.append(f"Very few computers: {computers:.0f} for {students:.0f} students")
    if net is not None:
        n = 0.0 if net else 100.0
        if not net:
            notes.append("No internet connection")
    return _blend([(0.60, c), (0.40, n)]), notes


INDICATORS: list[tuple[str, Callable[[Mapping[str, Any]], Result]]] = [
    ("infrastructure", _infrastructure),
    ("water_sanitation", _water_sanitation),
    ("attendance", _attendance),
    ("teachers", _teachers),
    ("academic", _academic),
    ("technology", _technology),
]


def classify(score: float) -> str:
    for upper, label in CATEGORY_BANDS:
        if score < upper:
            return label
    return "Critical"


def calculate_need_score(school: Mapping[str, Any]) -> dict:
    """Return a JSON-safe dict describing the score, category and reasons."""
    raw: dict[str, tuple[Optional[float], list[str]]] = {k: fn(school) for k, fn in INDICATORS}
    avail_w = sum(WEIGHTS[k] for k, (need, _) in raw.items() if need is not None)
    completeness = round(avail_w * 100, 1)
    missing = [LABELS[k] for k, (need, _) in raw.items() if need is None]

    components: dict[str, dict] = {}
    for k, (need, notes) in raw.items():
        if need is None:
            contrib = None
        elif avail_w > 0:
            contrib = round(WEIGHTS[k] / avail_w * need, 1)  # points added to final score
        else:
            contrib = None
        components[k] = {
            "label": LABELS[k],
            "weight": round(WEIGHTS[k] * 100),
            "need": None if need is None else round(need, 1),
            "contribution": contrib,
            "available": need is not None,
            "findings": notes,
        }

    if completeness < MIN_COMPLETENESS:
        return {
            "need_score": None,
            "category": "Insufficient Data",
            "status": "insufficient_data",
            "data_completeness": completeness,
            "components": components,
            "reasons": [f"Not enough data to classify this school (only {completeness:.0f}% of the "
                        f"indicators could be measured). Missing: {', '.join(missing)}."],
            "missing_fields": missing,
            "scoring_version": SCORING_VERSION,
        }

    score = round(sum(WEIGHTS[k] * need for k, (need, _) in raw.items() if need is not None) / avail_w, 1)
    ordered = sorted((c for c in components.values() if c["available"]),
                     key=lambda c: c["contribution"], reverse=True)
    reasons = [f"{c['label']}: {f}" for c in ordered for f in c["findings"]]
    if not reasons:
        reasons = ["No significant problems detected in the available indicators."]
    if missing:
        reasons.append(f"Score based on partial data. Not available: {', '.join(missing)}.")
    return {
        "need_score": score,
        "category": classify(score),
        "status": "partial" if missing else "scored",
        "data_completeness": completeness,
        "components": components,
        "reasons": reasons,
        "missing_fields": missing,
        "scoring_version": SCORING_VERSION,
    }
