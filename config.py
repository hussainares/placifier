import os
from dotenv import load_dotenv

load_dotenv()

# --- Supabase Postgres (use the POOLED connection string — port 6543 — for serverless) ---
# Format: postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# --- App ---
SECRET_KEY = os.environ.get("SECRET_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

# Comma-separated list of emails that can open /admin and export CSV.
# Everyone else gets a 403. Example: ADMIN_EMAILS=you@gmail.com,teacher@college.edu
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "").split(",")
    if e.strip()
}

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set. Add it in Vercel Project Settings -> Environment Variables.")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY not set. Generate one: python -c \"import secrets; print(secrets.token_hex(32))\"")
if not NEWS_API_KEY:
    print("WARNING: NEWS_API_KEY not set. News feed will be disabled.")
if not ADMIN_EMAILS:
    print("WARNING: ADMIN_EMAILS not set. Nobody will be able to open the admin dashboard.")
