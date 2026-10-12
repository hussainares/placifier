-- Placifier schema. Run once in Supabase -> SQL Editor on a fresh project.
-- (Upgrading an existing database from the old username version? Use migration.sql instead.)

CREATE TABLE IF NOT EXISTS users (
    id       SERIAL PRIMARY KEY,
    name     TEXT NOT NULL,
    email    TEXT UNIQUE NOT NULL,      -- always stored lowercase
    password TEXT NOT NULL              -- werkzeug hash, never plain text
);

CREATE TABLE IF NOT EXISTS jobs (
    id         SERIAL PRIMARY KEY,
    role       TEXT NOT NULL,
    department TEXT NOT NULL DEFAULT 'General',
    skills     TEXT NOT NULL      -- space-separated; multi-word skills use underscores
);

CREATE TABLE IF NOT EXISTS students (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    skills     TEXT NOT NULL,
    user_email TEXT
);

CREATE TABLE IF NOT EXISTS recommendations (
    id               SERIAL PRIMARY KEY,
    student          TEXT NOT NULL,
    recommended_job  TEXT NOT NULL,
    match_score      NUMERIC(5,2) NOT NULL,
    user_email       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_recommendations_user_email ON recommendations (user_email);

-- Then seed the jobs table: run seed_jobs.sql, or import jobs.csv via
-- Table Editor -> jobs -> Insert -> Import data from CSV.
