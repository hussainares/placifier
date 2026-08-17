import os
from dotenv import load_dotenv

load_dotenv()

# --- Supabase Postgres (use the POOLED connection string — port 6543 — for serverless) ---
# Format: postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# --- App ---
SECRET_KEY = os.environ.get("SECRET_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set. Add it in Vercel Project Settings -> Environment Variables.")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY not set. Generate one: python -c \"import secrets; print(secrets.token_hex(32))\"")
if not NEWS_API_KEY:
    print("WARNING: NEWS_API_KEY not set. News feed will be disabled.")
