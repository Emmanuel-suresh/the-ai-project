"""
Generate the FICTIONAL sample dataset: 60 government schools across five
Goa areas, plus 5 years of attendance/academic history per school.

Every record is invented. Village names are real places in Goa, but the schools,
codes and figures are made up for a college demonstration.

Run:  python scripts/generate_sample_data.py      (output goes to ../data/)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import DATA_DIR  # noqa: E402

rng = np.random.default_rng(42)

# district: (centre lat, centre lon, Beta(a, b) for hidden "struggle" level, localities)
DISTRICTS = {
    "Tiswadi": (15.50, 73.86, (2.2, 3.0), ["Santa Cruz", "Taleigao", "Bambolim", "Merces", "Chimbel", "Goa Velha",
                                          "Ribandar", "Carambolim", "Old Goa", "Neura", "Siridao", "Corlim"]),
    "Bardez": (15.57, 73.81, (2.9, 2.2), ["Siolim", "Assagao", "Anjuna", "Nachinola", "Parra", "Pilerne",
                                         "Aldona", "Moira", "Saligao", "Guirim", "Revora", "Calangute"]),
    "Salcete": (15.28, 73.96, (2.2, 2.8), ["Benaulim", "Colva", "Chinchinim", "Loutolim", "Raia", "Nuvem",
                                          "Verna", "Curtorim", "Varca", "Cavelossim", "Orlim", "Utorda"]),
    "Ponda": (15.40, 74.02, (3.8, 1.9), ["Curti", "Bandora", "Shiroda", "Priol", "Betora", "Farmagudi",
                                        "Usgao", "Kundaim", "Marcaim", "Veling", "Queula", "Durbhat"]),
    "Bicholim": (15.59, 73.95, (4.6, 1.7), ["Mayem", "Mulgao", "Naroa", "Lamgao", "Pale", "Advalpal",
                                           "Harvalem", "Kudnem", "Latambarcem", "Carapur", "Surla", "Sirgao"]),
}
TYPES = {  # label, student range, probability
    "Primary": ("Primary School", (35, 200), 0.40),
    "Upper Primary": ("Upper Primary School", (80, 320), 0.25),
    "Secondary": ("High School", (150, 550), 0.25),
    "Higher Secondary": ("Higher Secondary School", (200, 700), 0.10),
}
YEARS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
# school index -> fields deliberately left blank, to exercise missing-data handling
BLANKS = {4: ["attendance_pct"], 17: ["academic_score"], 29: ["electricity"], 38: ["computers"],
          46: ["internet", "computers"], 51: ["teachers", "attendance_pct", "academic_score"]}


def cl(x):
    return float(np.clip(x, 0, 1))


rows, history, n = [], [], 0
type_keys = list(TYPES)
type_p = [TYPES[k][2] for k in type_keys]

for district, (lat0, lon0, (a, b), places) in DISTRICTS.items():
    for place in places:
        n += 1
        q = float(rng.beta(a, b))                      # hidden struggle level, 0 = thriving, 1 = struggling
        j = lambda s=0.12: cl(q + rng.normal(0, s))    # noisy view of q for each indicator
        stype = str(rng.choice(type_keys, p=type_p))
        label, (lo, hi), _ = TYPES[stype]
        students = int(rng.integers(lo, hi))
        ptr = 20 + 40 * j()
        teachers = max(2, round(students / ptr))
        rooms = max(3, round(students / (26 + 34 * j())))
        good = int(round(rooms * cl(1 - q * 1.05 + rng.normal(0, 0.1))))
        toilets = max(1, round(students / (36 + 80 * j())))
        row = dict(
            udise_code=f"FICT-GA-{n:03d}", name=f"Govt. {label}, {place}", school_type=stype,
            district=district, locality=place,
            latitude=round(lat0 + rng.normal(0, 0.035), 5), longitude=round(lon0 + rng.normal(0, 0.035), 5),
            students=students, teachers=teachers, classrooms_total=rooms, classrooms_good=min(good, rooms),
            functional_toilets=toilets, girls_toilet=bool(rng.random() > q * 0.55),
            drinking_water=bool(rng.random() > q * 0.55), electricity=bool(rng.random() > q * 0.2),
            computers=int(round(students * (12 * (1 - j(0.15))) / 100)),
            internet=bool(rng.random() > q * 0.9),
            attendance_pct=round(96 - 36 * j(), 1), academic_score=round(85 - 48 * j(), 1),
            is_fictional=True,
        )
        # five-year history ending at the current values; weak schools tend to have declined
        drift = (q - 0.5) * 1.6 + rng.normal(0, 0.7)
        for t, year in enumerate(reversed(YEARS)):     # t = years before the latest
            history.append(dict(
                udise_code=row["udise_code"], academic_year=year,
                attendance_pct=round(float(np.clip(row["attendance_pct"] + drift * t + rng.normal(0, 0.8), 40, 99)), 1)
                if t else row["attendance_pct"],
                academic_score=round(float(np.clip(row["academic_score"] + drift * 1.5 * t + rng.normal(0, 1.2), 25, 95)), 1)
                if t else row["academic_score"],
            ))
        for field in BLANKS.get(n - 1, []):
            row[field] = None
            if field in ("attendance_pct", "academic_score"):
                for h in history[-1:]:                 # latest year is blank too
                    h[field] = None
        rows.append(row)

df = pd.DataFrame(rows)
for col in ["girls_toilet", "drinking_water", "electricity", "internet", "is_fictional"]:
    df[col] = df[col].map({True: "yes", False: "no"})   # blanks stay empty
for col in ["teachers", "computers"]:
    df[col] = df[col].astype("Int64")

DATA_DIR.mkdir(exist_ok=True)
df.to_csv(DATA_DIR / "sample_schools.csv", index=False)
pd.DataFrame(history).to_csv(DATA_DIR / "sample_school_history.csv", index=False)
# Excel copy so the upload feature can be tested with both formats
df.to_excel(DATA_DIR / "sample_schools.xlsx", index=False)
print(f"Wrote {len(df)} schools and {len(history)} history rows to {DATA_DIR}")
