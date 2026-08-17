CREATE TABLE IF NOT EXISTS users (
    id       SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id     SERIAL PRIMARY KEY,
    role   TEXT NOT NULL,
    skills TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    id     SERIAL PRIMARY KEY,
    name   TEXT NOT NULL,
    skills TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    id               SERIAL PRIMARY KEY,
    student          TEXT NOT NULL,
    recommended_job  TEXT NOT NULL,
    match_score      NUMERIC(5,2) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed jobs.csv into the `jobs` table via Supabase Table Editor -> Import CSV,
-- or run an INSERT per row here.
