import csv
import os
import re
from datetime import datetime
from functools import wraps
from io import BytesIO, StringIO

import numpy as np
import requests
from flask import (Flask, Response, abort, redirect, render_template, request,
                   session, url_for)
from pdfminer.high_level import extract_text
from psycopg2 import errors as pg_errors
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.security import check_password_hash, generate_password_hash

import config
from db import get_conn

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")),  # https only when deployed
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,  # Vercel rejects bodies over ~4.5 MB anyway
)

NEWSAPI_URL = "https://newsapi.org/v2/everything"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --------------------------------------------------------------------------
# Auth helpers
# --------------------------------------------------------------------------
def is_admin_email(email):
    return bool(email) and email.lower() in config.ADMIN_EMAILS


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "email" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "email" not in session:
            return redirect(url_for("login"))
        if not is_admin_email(session["email"]):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    email = session.get("email")
    return {
        "is_admin": is_admin_email(email),
        "display_name": session.get("name") or (email.split("@")[0] if email else ""),
    }


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, title="Admins only",
                           message="You don't have permission to view this page."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, title="Page not found",
                           message="That page doesn't exist."), 404


@app.errorhandler(413)
def too_large(_e):
    return render_template("index.html", error="That file is too large. Please upload a PDF under 4 MB."), 413


# --------------------------------------------------------------------------
# News
# --------------------------------------------------------------------------
def get_rss_feed(skills=None):
    used_skills = []
    if not config.NEWS_API_KEY:
        return [], used_skills

    if skills:
        skill_list = [s.replace("_", " ") for s in skills.split() if len(s) > 2][:3]
        if skill_list:
            query = " OR ".join(f'"{s}" jobs India' for s in skill_list)
            used_skills = skill_list
        else:
            query = "campus placement hiring freshers India"
    else:
        query = "campus placement hiring freshers India"

    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 8,
        "apiKey": config.NEWS_API_KEY,
    }

    try:
        response = requests.get(NEWSAPI_URL, params=params, timeout=6)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return [], used_skills

    if data.get("status") != "ok":
        return [], used_skills

    articles = []
    for item in data.get("articles", [])[:5]:
        published_raw = item.get("publishedAt", "")
        published = ""
        if published_raw:
            try:
                published = datetime.strptime(published_raw, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M")
            except ValueError:
                published = published_raw[:16]

        source_obj = item.get("source") or {}
        articles.append({
            "title": item.get("title") or "Untitled",
            "link": item.get("url") or "#",
            "source": source_obj.get("name", "NewsAPI"),
            "published": published,
        })
    return articles, used_skills


# --------------------------------------------------------------------------
# Recommendation engine
# --------------------------------------------------------------------------
# Skills live in the `jobs` table as space-separated tokens; multi-word skills use
# underscores (financial_modeling). The skill vocabulary is built from that table, so
# adding a role to the database automatically teaches resume reading its skills too.

# Common ways people write a skill -> the token used in the database.
ALIASES = [
    (r"(?<![a-z0-9])node\.?js(?![a-z0-9])", "nodejs"),
    (r"(?<![a-z0-9])react\.?js(?![a-z0-9])", "react"),
    (r"(?<![a-z0-9])power\s?bi(?![a-z0-9])", "powerbi"),
    (r"(?<![a-z0-9])(?:ms|microsoft)\s+excel(?![a-z0-9])", "excel"),
    (r"(?<![a-z0-9])(?:ms|microsoft)\s+office(?![a-z0-9])", "ms office"),
    (r"(?<![a-z0-9])scikit[\s\-]?learn(?![a-z0-9])", "sklearn"),
    (r"(?<![a-z0-9])postgres(?![a-z0-9])", "postgresql"),
    (r"(?<![a-z0-9])k8s(?![a-z0-9])", "kubernetes"),
    (r"(?<![a-z0-9.])js(?![a-z0-9])", "javascript"),
    (r"(?<![a-z0-9])ci\s?/?\s?cd(?![a-z0-9])", "ci/cd"),
]
MAX_EXTRACTED_SKILLS = 30


def apply_aliases(text):
    for pattern, replacement in ALIASES:
        text = re.sub(pattern, replacement, text)
    return text


def get_jobs(cur):
    cur.execute("SELECT role, skills, department FROM jobs")
    return cur.fetchall()


def build_vocab(jobs):
    return {tok for job in jobs for tok in job[1].lower().split()}


def _skill_pattern(skill):
    """Whole-word pattern for one skill: 'financial_modeling' also matches
    'financial modeling' / 'financial-modeling', and a trailing plural (APIs)."""
    words = [re.escape(w) for w in skill.split("_")]
    return r"(?<![a-z0-9+#.])" + r"[\s\-]+".join(words) + r"s?(?![a-z0-9+#])"


def extract_skills_from_pdf_bytes(file_bytes, vocab):
    text = extract_text(BytesIO(file_bytes))
    lowered = apply_aliases(text.lower())
    hits = []
    for skill in vocab:
        m = re.search(_skill_pattern(skill), lowered)
        if m:
            hits.append((m.start(), skill))
    hits.sort()
    found = [skill.replace("_", " ") for _, skill in hits[:MAX_EXTRACTED_SKILLS]]
    return ", ".join(found), text


def normalize_skills(text, vocab):
    """Turn what a student typed ('Python, financial modeling; MS Excel') into a
    list of known skill tokens. Words we have no role for are dropped."""
    lowered = apply_aliases(text.lower())
    for skill in sorted((v for v in vocab if "_" in v), key=len, reverse=True):
        lowered = re.sub(_skill_pattern(skill), skill, lowered)
    tokens, seen = [], set()
    for raw in re.split(r"[\s,;]+", lowered):
        tok = raw.strip("()[]:,;").rstrip(".")
        if tok in vocab and tok not in seen:
            seen.add(tok)
            tokens.append(tok)
    return tokens


def extract_name_from_pdf_text(text):
    skip_keywords = ("resume", "curriculum vitae", "cv", "@", "http",
                     "email", "phone", "address", "objective", "summary")
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        lower = candidate.lower()
        if any(kw in lower for kw in skip_keywords):
            continue
        if any(ch.isdigit() for ch in candidate):
            continue
        words = candidate.split()
        if 1 < len(words) <= 4 and all(w.replace(".", "").isalpha() for w in words):
            return candidate.title()
        break
    return ""


def recommend_jobs(jobs, student_tokens, top_n=3):
    """Cosine similarity between the student's skills and every role (TF-IDF).
    Roles sharing no skill with the student are never returned."""
    if not jobs or not student_tokens:
        return []
    vectorizer = TfidfVectorizer(lowercase=True, token_pattern=r"\S+")
    job_matrix = vectorizer.fit_transform([job[1] for job in jobs])
    student_vec = vectorizer.transform([" ".join(student_tokens)])
    similarity = cosine_similarity(student_vec, job_matrix)[0]

    order = sorted(range(len(jobs)), key=lambda i: (-similarity[i], jobs[i][0]))
    results = []
    for i in order[:top_n]:
        score = float(round(similarity[i] * 100, 2))
        if score <= 0:
            break
        results.append({"job": jobs[i][0], "department": jobs[i][2],
                        "skills": jobs[i][1], "score": score})
    return results


def skill_gap(student_skills, job_skills):
    student_set = set(student_skills.lower().split())
    job_set = set(job_skills.lower().split())
    return sorted(job_set & student_set), sorted(job_set - student_set)


# --------------------------------------------------------------------------
# Pages: auth
# --------------------------------------------------------------------------
@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "email" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        raw_password = request.form.get("password", "")

        def fail(msg):
            return render_template("signup.html", error=msg, name=name, email=email)

        if not name or len(name) > 100:
            return fail("Please enter your full name.")
        if len(email) > 254 or not EMAIL_RE.match(email):
            return fail("Please enter a valid email address.")
        if len(raw_password) < 8:
            return fail("Password must be at least 8 characters.")
        if len(raw_password) > 128:
            return fail("Password is too long (max 128 characters).")

        password_hash = generate_password_hash(raw_password)
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    return fail("An account with this email already exists. Try logging in.")
                cur.execute(
                    "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                    (name, email, password_hash),
                )
                conn.commit()
        except pg_errors.UniqueViolation:
            conn.rollback()
            return fail("An account with this email already exists. Try logging in.")
        finally:
            conn.close()

        session.clear()
        session["email"] = email
        session["name"] = name
        return redirect(url_for("home"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "email" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT name, password FROM users WHERE email = %s", (email,))
                user = cur.fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user[1], password):
            session.clear()
            session["email"] = email
            session["name"] = user[0]
            return redirect(url_for("home"))
        return render_template("login.html", error="Wrong email or password.", email=email)

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Pages: student features
# --------------------------------------------------------------------------
@app.route("/upload_resume", methods=["POST"])
@login_required
def upload_resume():
    file = request.files.get("resume")
    if not file or file.filename == "":
        return redirect(url_for("home"))

    file_bytes = file.read()  # in memory only — never written to disk
    if not file_bytes.startswith(b"%PDF"):
        return render_template("index.html", error="That doesn't look like a PDF file.")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            vocab = build_vocab(get_jobs(cur))
    finally:
        conn.close()

    try:
        skills, raw_text = extract_skills_from_pdf_bytes(file_bytes, vocab)
    except Exception:
        return render_template(
            "index.html",
            error="We couldn't read that PDF. Try another file, or enter your skills manually.",
        )

    name = extract_name_from_pdf_text(raw_text)
    return render_template("index.html", extracted_skills=skills, extracted_name=name)


@app.route("/recommend", methods=["POST"])
@login_required
def recommend():
    name = request.form.get("name", "").strip()
    skills = request.form.get("skills", "").strip()

    if not name or not skills:
        return render_template("index.html", extracted_skills=skills, extracted_name=name,
                               error="Please enter both your name and at least one skill.")

    email = session["email"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            jobs = get_jobs(cur)
            tokens = normalize_skills(skills, build_vocab(jobs))
            results = recommend_jobs(jobs, tokens)
            if not results:
                return render_template(
                    "index.html", extracted_skills=skills, extracted_name=name,
                    error="We couldn't match those skills to any role. Try specific skills, "
                          "e.g. Python, Excel, Patient Care, Financial Modeling, AutoCAD.")

            top_job, top_score = results[0]["job"], results[0]["score"]
            matched, missing = skill_gap(" ".join(tokens), results[0]["skills"])

            cur.execute("INSERT INTO students (name, skills, user_email) VALUES (%s, %s, %s)",
                        (name, skills, email))
            cur.execute(
                "INSERT INTO recommendations (student, recommended_job, match_score, user_email) "
                "VALUES (%s, %s, %s, %s)",
                (name, top_job, top_score, email),
            )
            conn.commit()
    finally:
        conn.close()

    articles, used_skills = get_rss_feed(skills=" ".join(tokens))
    return render_template("result.html", name=name, results=results, articles=articles,
                           used_skills=used_skills, matched=matched, missing=missing)


@app.route("/news")
@login_required
def news():
    skill_filter = request.args.get("skills", "").strip()
    articles, used_skills = get_rss_feed(skills=skill_filter or None)
    return render_template("news.html", articles=articles, used_skills=used_skills,
                           skill_filter=skill_filter)


@app.route("/history")
@login_required
def history():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT student, recommended_job, match_score, created_at "
                "FROM recommendations WHERE user_email = %s ORDER BY created_at DESC",
                (session["email"],),
            )
            records = cur.fetchall()
    finally:
        conn.close()
    return render_template("history.html", records=records)


@app.route("/clear_history", methods=["POST"])
@login_required
def clear_history():
    """Deletes only the logged-in user's own history (POST, not GET, so a
    stray link or prefetch can't wipe data)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM recommendations WHERE user_email = %s", (session["email"],))
            conn.commit()
    finally:
        conn.close()
    return redirect(url_for("history"))


# --------------------------------------------------------------------------
# Pages: admin only
# --------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM recommendations")
            total_recs = cur.fetchone()[0]

            cur.execute("SELECT AVG(match_score) FROM recommendations")
            avg_score = cur.fetchone()[0]
            avg_score = round(float(avg_score), 2) if avg_score else 0

            cur.execute("""
                SELECT recommended_job, COUNT(*) AS cnt FROM recommendations
                GROUP BY recommended_job ORDER BY cnt DESC LIMIT 1
            """)
            top_job_row = cur.fetchone()
            top_job = top_job_row[0] if top_job_row else "N/A"

            cur.execute("SELECT student, recommended_job, match_score, created_at, user_email "
                        "FROM recommendations ORDER BY created_at DESC")
            records = cur.fetchall()
    finally:
        conn.close()

    return render_template("admin.html", total_students=total_users, total_recs=total_recs,
                           avg_score=avg_score, top_job=top_job, records=records)


def _csv_safe(value):
    """Stop spreadsheet apps treating user-typed text as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@app.route("/export_csv")
@admin_required
def export_csv():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT student, user_email, recommended_job, match_score, created_at "
                        "FROM recommendations ORDER BY created_at DESC")
            records = cur.fetchall()
    finally:
        conn.close()

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Account Email", "Recommended Job", "Match Score", "Date"])
    for r in records:
        writer.writerow([_csv_safe(r[0]), _csv_safe(r[1]), _csv_safe(r[2]), r[3], r[4]])

    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=placifier-recommendations.csv"})


# No `if __name__ == "__main__": app.run(...)` — Vercel imports `app` directly
# via api/index.py. For local testing, run: python -m flask --app app run --debug
