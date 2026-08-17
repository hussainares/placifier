# Placement Recommendation System

Flask app that matches student skills to job roles (TF-IDF + cosine similarity),
extracts skills/name from an uploaded resume PDF, and shows relevant job news.
Deployed as a serverless function on Vercel, with Postgres on Supabase.

Theme: white/blue, with a light↔dark toggle (top-right of the nav) that
persists per-browser via `localStorage`.

## Project structure
```
api/index.py      # Vercel entrypoint -> imports app.py
app.py            # Flask routes
config.py         # env var loading
db.py             # Postgres connection (per-request, pooled)
schema.sql        # table definitions
jobs.csv          # seed data for the `jobs` table
static/style.css  # theme (light/dark via CSS variables)
static/theme.js   # dark-mode toggle button behavior
templates/*.html  # pages
vercel.json       # Vercel build/routing config
```

## 1. Recreate the Supabase project

1. Go to https://supabase.com/dashboard → **New project**.
2. Once it's provisioned, open **Project Settings → Database → Connection string**.
   Copy the **Transaction pooler** string (port `6543`) — this is the one built
   for serverless (short-lived, per-request connections), which is how `db.py`
   is written. It looks like:
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```
3. Open the **SQL Editor** and run the contents of `schema.sql` to create the
   `users`, `jobs`, `students`, and `recommendations` tables.
4. Seed the `jobs` table — either:
   - run `seed_jobs.sql` (included, already generated from `jobs.csv`) in the SQL Editor, or
   - **Table Editor → jobs → Insert → Import data from CSV** and upload `jobs.csv` directly.

## 2. Configure environment variables

```bash
cp .env.example .env
```
Fill in:
- `DATABASE_URL` — the pooler string from step 1
- `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- `NEWS_API_KEY` — optional, from https://newsapi.org (news feed is skipped if blank)

`.env` is already in `.gitignore` — it will never be committed.

## 3. Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app run --debug
```
Visit http://127.0.0.1:5000 — sign up for an account, then log in.

## 4. Push to GitHub

```bash
git init
git add .
git commit -m "Placement system: white/blue theme, dark mode, Vercel + Supabase"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```
(If the repo doesn't exist yet, create an empty one on GitHub first — no README/license,
so it doesn't conflict with this push.)

## 5. Deploy to Vercel

**Dashboard (recommended for first deploy):**
1. https://vercel.com/new → **Import** your GitHub repo.
2. Framework preset: **Other** (vercel.json already defines the build).
3. Add environment variables in **Settings → Environment Variables**:
   `DATABASE_URL`, `SECRET_KEY`, `NEWS_API_KEY` — same values as your `.env`.
4. Deploy.

**Or via CLI:**
```bash
npm i -g vercel
vercel login
vercel            # first deploy / preview
vercel env add DATABASE_URL
vercel env add SECRET_KEY
vercel env add NEWS_API_KEY
vercel --prod     # production deploy
```

Every subsequent `git push` to `main` auto-deploys if the repo is connected
in the Vercel dashboard.

## Notes on the dark mode implementation
- All theme colors are CSS variables in `static/style.css`, redefined under
  `html[data-theme="dark"]`.
- A small inline script in each page's `<head>` sets `data-theme` **before**
  first paint (reading `localStorage`, falling back to the OS preference) so
  there's no flash of the wrong theme.
- `static/theme.js` just wires up the moon/sun button to flip `data-theme`
  and persist the choice.
