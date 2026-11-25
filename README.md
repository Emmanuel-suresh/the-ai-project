# EduCare AI: Every School Deserves a Better Future

Government school monitoring and assistance dashboard (college engineering project).

> **All sample data is FICTIONAL.** Village names are real places in Goa, but every school,
> code (`FICT-GA-###`) and figure was invented. All donations are **simulated**.

## Build progress
| Stage | Content | Status |
|---|---|---|
| 1 | Project structure, PostgreSQL schema, scoring algorithm, sample dataset, seed script | Done |
| 2 | FastAPI backend: dashboard stats, school API, needs and funding estimates | Next |
| 3 | Next.js dashboard, school profiles, charts, map | |
| 4 | Dataset upload, auth (admin/donor), donation portal, reports | |
| 5 | Qwen3 / Ollama assistant with demo-mode fallback | |

## Setup (Ubuntu)
```bash
# 1. Database (once)
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'yourpassword';"
sudo -u postgres psql -c "CREATE DATABASE educare_ai;"

# 2. Config
cp .env.example .env        # then edit the password in DATABASE_URL

# 3. Python environment
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Test the scoring algorithm (8 tests should pass)
python -m pytest -q

# 5. Create tables and load the 60 fictional schools
python scripts/seed_db.py --reset
```
Expected output of the last step:
```
Loaded 60 fictional schools and 300 history rows.
  Poor              28
  Good              14
  Excellent         10
  Critical          7
  Insufficient Data 1
```
`--reset` wipes the database. Without it the script just updates existing rows.
To regenerate the CSV/Excel files: `python scripts/generate_sample_data.py`.

## School Need Score (0-100, higher = greater need)
| Indicator | Weight | Measured from |
|---|---|---|
| Infrastructure | 25% | classrooms in good condition (60%), students per classroom (25%), electricity (15%) |
| Water and sanitation | 20% | drinking water (40%), students per toilet (40%), girls' toilet (20%) |
| Attendance | 15% | attendance % (95% = no need, 60% or lower = maximum need) |
| Teacher availability | 15% | students per teacher (25 = no need, 60+ = maximum need) |
| Academic performance | 15% | average score (80% = no need, 40% or lower = maximum need) |
| Technology | 10% | computers per 100 students (60%), internet (40%) |

Bands: **0-19 Excellent, 20-39 Good, 40-69 Poor, 70-100 Critical.**

**Missing data:** blanks are never guessed. Missing indicators are left out and the remaining
weights re-scaled (the school is marked *partial*). If less than 70% of the weighting has data,
the school is labelled **Insufficient Data** and gets no score. The sample dataset includes
6 schools with deliberate gaps to demonstrate this.

Every score stores its per-indicator breakdown and plain-English reasons in `school_scores`,
so the dashboard and the AI assistant can only quote real, stored figures.

## Notes
- Goa's Ponda, Tiswadi, Bardez, Salcete and Bicholim are *talukas*. The database column is named
  `district` to match the project specification.
- `donations.is_simulated` has a database CHECK constraint: a non-simulated donation cannot be saved.
# the-ai-project
