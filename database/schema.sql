-- EduCare AI database schema (PostgreSQL 14+)
-- NOTE: in Goa the five areas used here are talukas; the column is called
-- "district" to match the project specification.

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'donor')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS schools (
    id                SERIAL PRIMARY KEY,
    udise_code        TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    school_type       TEXT,
    district          TEXT NOT NULL,
    locality          TEXT,
    latitude          DOUBLE PRECISION,
    longitude         DOUBLE PRECISION,
    students          INTEGER CHECK (students >= 0),
    teachers          INTEGER CHECK (teachers >= 0),
    classrooms_total  INTEGER CHECK (classrooms_total >= 0),
    classrooms_good   INTEGER CHECK (classrooms_good >= 0),
    functional_toilets INTEGER CHECK (functional_toilets >= 0),
    girls_toilet      BOOLEAN,
    drinking_water    BOOLEAN,
    electricity       BOOLEAN,
    computers         INTEGER CHECK (computers >= 0),
    internet          BOOLEAN,
    attendance_pct    NUMERIC(5,2) CHECK (attendance_pct BETWEEN 0 AND 100),
    academic_score    NUMERIC(5,2) CHECK (academic_score BETWEEN 0 AND 100),
    is_fictional      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (classrooms_good IS NULL OR classrooms_total IS NULL OR classrooms_good <= classrooms_total)
);
CREATE INDEX IF NOT EXISTS idx_schools_district ON schools (district);

-- One row per school; recalculated whenever school data changes.
CREATE TABLE IF NOT EXISTS school_scores (
    school_id         INTEGER PRIMARY KEY REFERENCES schools(id) ON DELETE CASCADE,
    need_score        NUMERIC(4,1),            -- NULL when data is insufficient
    category          TEXT NOT NULL CHECK (category IN ('Excellent','Good','Poor','Critical','Insufficient Data')),
    status            TEXT NOT NULL CHECK (status IN ('scored','partial','insufficient_data')),
    data_completeness NUMERIC(4,1) NOT NULL,   -- % of weighting backed by real data
    components        JSONB NOT NULL,          -- per-indicator need, weight, contribution
    reasons           JSONB NOT NULL,          -- human-readable reasons for the classification
    missing_fields    JSONB NOT NULL DEFAULT '[]',
    scoring_version   TEXT NOT NULL,
    calculated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scores_category ON school_scores (category);
CREATE INDEX IF NOT EXISTS idx_scores_need ON school_scores (need_score DESC);

-- Yearly performance, used for the trend line chart.
CREATE TABLE IF NOT EXISTS school_history (
    school_id      INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    academic_year  TEXT NOT NULL,
    attendance_pct NUMERIC(5,2),
    academic_score NUMERIC(5,2),
    PRIMARY KEY (school_id, academic_year)
);

-- Resources a school needs, with cost estimates (generated in Stage 2).
CREATE TABLE IF NOT EXISTS school_needs (
    id             SERIAL PRIMARY KEY,
    school_id      INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    category       TEXT NOT NULL,
    item           TEXT NOT NULL,
    quantity       INTEGER NOT NULL CHECK (quantity > 0),
    unit_cost      NUMERIC(12,2) NOT NULL CHECK (unit_cost >= 0),
    estimated_cost NUMERIC(12,2) NOT NULL CHECK (estimated_cost >= 0),
    priority       INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 3)
);
CREATE INDEX IF NOT EXISTS idx_needs_school ON school_needs (school_id);

-- Donations are SIMULATED ONLY. The CHECK makes it impossible to store a
-- record that claims to be a real payment.
CREATE TABLE IF NOT EXISTS donations (
    id            SERIAL PRIMARY KEY,
    school_id     INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    donor_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    donor_name    TEXT NOT NULL,
    amount        NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    is_simulated  BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_simulated = TRUE),
    payment_ref   TEXT NOT NULL UNIQUE,        -- e.g. SIM-20260101-AB12CD
    status        TEXT NOT NULL DEFAULT 'simulated_success',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_donations_school ON donations (school_id);

CREATE TABLE IF NOT EXISTS dataset_uploads (
    id            SERIAL PRIMARY KEY,
    filename      TEXT NOT NULL,
    uploaded_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    rows_total    INTEGER NOT NULL DEFAULT 0,
    rows_valid    INTEGER NOT NULL DEFAULT 0,
    rows_invalid  INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'previewed' CHECK (status IN ('previewed','imported','failed')),
    error_report  JSONB NOT NULL DEFAULT '[]',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Convenience view for the dashboard and school list.
CREATE OR REPLACE VIEW v_school_overview AS
SELECT s.*, sc.need_score, sc.category, sc.status AS score_status, sc.data_completeness
FROM schools s
LEFT JOIN school_scores sc ON sc.school_id = s.id;
