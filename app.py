from flask import Flask, render_template, request, session, redirect, url_for, Response
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import requests
import numpy as np
import config
from datetime import datetime
from io import BytesIO
from pdfminer.high_level import extract_text

from db import get_conn

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

NEWSAPI_URL = "https://newsapi.org/v2/everything"


def get_rss_feed(skills=None):
    if not config.NEWS_API_KEY:
        return [], []

    if skills:
        skill_list = [s.strip() for s in skills.split() if len(s.strip()) > 2][:3]
        if skill_list:
            query = " OR ".join(f"{s} developer jobs India" for s in skill_list)
            used_skills = skill_list
        else:
            query = "software developer jobs India IT hiring"
            used_skills = []
    else:
        query = "software developer jobs India OR IT hiring India"
        used_skills = []

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
            "title": item.get("title", "Untitled"),
            "link": item.get("url", "#"),
            "source": source_obj.get("name", "NewsAPI"),
            "published": published,
        })
    return articles, used_skills


def get_jobs(cur):
    cur.execute("SELECT role, skills FROM jobs")
    return cur.fetchall()


KNOWN_SKILLS = [
    "python", "sql", "flask", "django", "java", "javascript",
    "html", "css", "react", "nodejs", "c++", "machine learning",
    "tensorflow", "sklearn", "mysql", "mongodb", "docker",
    "kubernetes", "aws", "linux", "git", "rest", "api",
    "nlp", "pytorch", "hadoop", "spark", "excel", "powerbi"
]


def extract_skills_from_pdf_bytes(file_bytes):
    text = extract_text(BytesIO(file_bytes))
    text_lower = text.lower()
    return " ".join(s for s in KNOWN_SKILLS if s in text_lower), text


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


def recommend_jobs(cur, student_skills, top_n=3):
    jobs = get_jobs(cur)
    job_skills = [job[1] for job in jobs]
    job_roles = [job[0] for job in jobs]

    data = job_skills + [student_skills]
    cv = TfidfVectorizer(lowercase=True)
    vectors = cv.fit_transform(data).toarray()

    similarity = cosine_similarity([vectors[-1]], vectors[:-1])
    top_indices = np.argsort(similarity[0])[::-1][:top_n]

    return [
        {"job": job_roles[int(i)], "score": float(round(similarity[0][i] * 100, 2))}
        for i in top_indices
    ]

def skill_gap(student_skills, job_skills):
    student_set = set(student_skills.lower().split())
    job_set = set(job_skills.lower().split())
    return list(job_set & student_set), list(job_set - student_set)


@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
                if cur.fetchone():
                    return render_template('signup.html', error="Username already exists")
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
                conn.commit()
        finally:
            conn.close()
        return redirect(url_for('login'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cur.fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user[2], password):
            session['username'] = username
            return redirect(url_for('home'))
        return render_template('login.html', error="Wrong username or password")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    if 'username' not in session:
        return redirect(url_for('login'))

    if 'resume' not in request.files or request.files['resume'].filename == '':
        return redirect('/')

    file_bytes = request.files['resume'].read()  # in-memory only — no disk write
    skills, raw_text = extract_skills_from_pdf_bytes(file_bytes)
    name = extract_name_from_pdf_text(raw_text)
    return render_template('index.html', username=session['username'],
                           extracted_skills=skills, extracted_name=name)


@app.route('/recommend', methods=['POST'])
def recommend():
    if 'username' not in session:
        return redirect(url_for('login'))

    name = request.form.get('name', '').strip()
    skills = request.form.get('skills', '').strip()

    if not name or not skills:
        return render_template('index.html', username=session['username'],
                               extracted_skills=skills, extracted_name=name,
                               error="Please enter both your name and at least one skill.")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO students (name, skills) VALUES (%s, %s)", (name, skills))
            conn.commit()

            results = recommend_jobs(cur, skills)
            top_job, top_score = results[0]['job'], results[0]['score']

            cur.execute("SELECT skills FROM jobs WHERE role = %s", (top_job,))
            row = cur.fetchone()
            matched, missing = skill_gap(skills, row[0] if row else "")

            cur.execute(
                "INSERT INTO recommendations (student, recommended_job, match_score) VALUES (%s, %s, %s)",
                (name, top_job, top_score)
            )
            conn.commit()
    finally:
        conn.close()

    articles, used_skills = get_rss_feed(skills=skills)
    return render_template('result.html', name=name, results=results, articles=articles,
                           used_skills=used_skills, matched=matched, missing=missing)


@app.route('/news')
def news():
    if 'username' not in session:
        return redirect(url_for('login'))
    skill_filter = request.args.get('skills', '').strip()
    articles, used_skills = get_rss_feed(skills=skill_filter if skill_filter else None)
    return render_template('news.html', articles=articles, used_skills=used_skills, skill_filter=skill_filter)


@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT student, recommended_job, match_score, created_at FROM recommendations ORDER BY created_at DESC")
            records = cur.fetchall()
    finally:
        conn.close()
    return render_template('history.html', records=records)


@app.route('/clear_history')
def clear_history():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM recommendations")
            conn.commit()
    finally:
        conn.close()
    return render_template('history.html', records=[])


@app.route('/admin')
def admin():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM students")
            total_students = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM recommendations")
            total_recs = cur.fetchone()[0]

            cur.execute("SELECT AVG(match_score) FROM recommendations")
            avg_score = cur.fetchone()[0]
            avg_score = round(float(avg_score), 2) if avg_score else 0

            cur.execute("""
                SELECT recommended_job, COUNT(*) as cnt FROM recommendations
                GROUP BY recommended_job ORDER BY cnt DESC LIMIT 1
            """)
            top_job_row = cur.fetchone()
            top_job = top_job_row[0] if top_job_row else "N/A"

            cur.execute("SELECT student, recommended_job, match_score, created_at FROM recommendations ORDER BY created_at DESC")
            records = cur.fetchall()
    finally:
        conn.close()

    return render_template('admin.html', total_students=total_students, total_recs=total_recs,
                           avg_score=avg_score, top_job=top_job, records=records)


@app.route('/export_csv')
def export_csv():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT student, recommended_job, match_score, created_at FROM recommendations")
            records = cur.fetchall()
    finally:
        conn.close()

    def generate():
        yield "Student,Recommended Job,Match Score,Date\n"
        for r in records:
            yield f"{r[0]},{r[1]},{r[2]},{r[3]}\n"

    return Response(generate(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=recommendations.csv"})


# No `if __name__ == "__main__": app.run(...)` — Vercel imports `app` directly
# via api/index.py. For local testing, run: flask --app app run --debug
