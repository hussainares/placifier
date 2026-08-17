import psycopg2
import config


def get_conn():
    """Open a fresh connection per request. Serverless functions are
    short-lived/stateless — a module-level global connection (the original
    MySQL pattern) will go stale or be shared unsafely across invocations.
    The Supabase pooler (port 6543, pgbouncer transaction mode) is designed
    for exactly this connect-per-request pattern, so the overhead is small.
    Default (tuple) cursor is kept — templates index rows as r[0], r[1]..."""
    return psycopg2.connect(config.DATABASE_URL)
