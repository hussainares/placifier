# Placifier

Match students to job roles from their skills or resume (TF-IDF + cosine similarity),
see a skill-gap analysis, and read job news. Flask on Vercel, Postgres on Supabase.
White/blue theme with a light/dark toggle.

## Accounts
- Students sign up and log in with **email + password** (min 8 characters).
- Each student sees only their own history.
- **Admins** are set by the `ADMIN_EMAILS` environment variable (comma-separated).
  Only those emails can open `/admin` and export the CSV; everyone else gets a 403.
  An admin must still sign up like anyone else, using one of those emails.

## Environment variables
| Name | Notes |
|---|---|
| `DATABASE_URL` | Supabase **Transaction pooler** URI (port 6543, user `postgres.<project-ref>`) |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_EMAILS` | e.g. `you@gmail.com,teacher@college.edu` |
| `NEWS_API_KEY` | optional (newsapi.org) |

## Database
- **Fresh Supabase project:** run `schema.sql`, then `seed_jobs.sql`, in the SQL Editor.
- **Existing database (already has users):** just run `seed_jobs.sql`. It adds the `department`
  column and replaces the job list; it never touches users or history, and is safe to re-run.
- `migration.sql` is a one-time upgrade from the very first username-based version. It **drops
  the `users` table** — do not run it on a live database.

## Job data
`jobs.csv` (also loaded by `seed_jobs.sql`) holds 252 roles across 25 fields: software, data/AI,
cloud, security, electronics, mechanical, civil, electrical, chemical/pharma, healthcare, finance,
accounting, marketing/sales, HR, business, supply chain, design/media, education, law, science,
hospitality, agriculture, aerospace/automotive, customer service and social work.
Skills are lowercase, space-separated; multi-word skills use underscores (`financial_modeling`).
To add a role, add a row and a matching `INSERT` — resume reading picks up its new skills
automatically because the skill list is built from this table.

## Run locally
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then fill in the values
python -m flask --app app run --debug
```

## Deploy
Push to GitHub; Vercel auto-deploys `main`. Add the four env vars in
Vercel -> Project -> Settings -> Environment Variables (**redeploy after changing them**).
