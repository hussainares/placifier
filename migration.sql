-- Upgrade an EXISTING Supabase database (old username-based version) to Placifier.
-- !! RUN ONCE ONLY, and only if you have no real users yet. !!
-- It DROPS the users table: re-running it after launch deletes every account.
-- (Adding the new job data does NOT need this file -- just run seed_jobs.sql.)
--
-- Old accounts used usernames, not emails, so they can't log in anymore.
-- Those rows were only test accounts, so they are removed; people just sign up again.
-- Your jobs table and recommendation history are kept.

DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id       SERIAL PRIMARY KEY,
    name     TEXT NOT NULL,
    email    TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

ALTER TABLE students        ADD COLUMN IF NOT EXISTS user_email TEXT;
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS user_email TEXT;

CREATE INDEX IF NOT EXISTS idx_recommendations_user_email ON recommendations (user_email);
