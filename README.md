# 🎓 Placement Recommendation System

A modern Flask application that intelligently matches student skills to job roles using **TF-IDF NLP ranking and Cosine Similarity**. The system seamlessly parses uploaded PDF resumes to extract core competencies, aggregates relevant industry career news, and features a persistent white-and-blue dark mode architecture.

---

## 🚀 Key Features

* **AI-Powered Matching:** Calculates proximity vectors between parsed resume text and seed job matrices.
* **Resume Parsing:** Automated client-side extraction of candidate names and skill matrices from PDF data.
* **Dynamic News Feed:** Real-time job trends via external API synchronization.
* **Optimized Architecture:** Stateless application logic tailored specifically for serverless lifecycles.
* **Modern Interface:** High-contrast white/blue UI layout with system-syncing dark mode state hydration.

---

## 🛠️ Tech Stack & Architecture

* **Backend Framework:** Flask (Python)
* **Vector Vectorization:** Scikit-Learn (TF-IDF + Cosine Similarity)
* **Database Layer:** PostgreSQL (Hosted via Supabase)
* **Hosting Platform:** Vercel (Serverless Functions)

### Directory Mapping
```text
├── api/
│   └── index.py        # Vercel serverless gateway function
├── static/
│   ├── style.css       # Semantic CSS variables for light/dark layouts
│   └── theme.js        # Hydration logic for system theme toggles
├── templates/          # Jinja2 contextual HTML pages
├── app.py              # Main Flask application routers
├── config.py           # Strictly typed environment configuration
├── db.py               # Optimized, pooled per-request DB clients
└── vercel.json         # Infrastructure build and routing definitions
```

---

## ⚡ Quick Start

### 1. Database Provisioning (Supabase)
1. Initialize a new project on the **[Supabase Dashboard](https://supabase.com/dashboard)**.
2. Navigate to **Project Settings → Database → Connection string** and select **Transaction Pooler** (Port `6543`).
3. Execute the `schema.sql` declarations inside the **SQL Editor** to construct core application entities.
4. Populate core data by executing `seed_jobs.sql` or importing `jobs.csv` within the **Table Editor**.

### 2. Environment Management
Clone the configuration boilerplate and define required structural strings:
```bash
cp .env.example .env
```
Ensure your configuration file contains these variables:
* `DATABASE_URL` — Your Supabase Transaction Pooler connection string.
* `SECRET_KEY` — Cryptographic string (Generate using `python -c "import secrets; print(secrets.token_hex(32))"`).
* `NEWS_API_KEY` — *(Optional)* Live query credentials generated from `https://newsapi.org`.

### 3. Local Development Core
```bash
# Instantiate and toggle virtual runtime environments
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Populate dependencies and boot development servers
pip install -r requirements.txt
flask --app app run --debug
```
Access the exposed application loop directly at `http://127.0.0.1:5000`.

---

## 📦 Deployment Strategies

### Repository Initialization
```bash
git init
git add .
git commit -m "feat: infrastructure tracking, pooled storage context, structural modes"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

### Vercel Serverless Orchestration

#### Option A: Git Dashboard (Recommended)
1. Connect repositories directly inside the **[Vercel New Project Wizard](https://vercel.com/new)**.
2. Keep the Framework Preset configured to **Other** (The workspace `vercel.json` maps execution scopes dynamically).
3. Inject production credentials inside **Settings → Environment Variables** (`DATABASE_URL`, `SECRET_KEY`, `NEWS_API_KEY`).
4. Trigger compilation pipelines.

#### Option B: Terminal Client Lifecycle
```bash
npm i -g vercel
vercel login
vercel env add DATABASE_URL
vercel env add SECRET_KEY
vercel env add NEWS_API_KEY
vercel --prod
```

---

## 🎨 Creative Theme Mechanics

* **Layout State Management:** Custom theme bindings parse system-level parameters via runtime attribute tracking (`html[data-theme="dark"]`).
* **Visual Flash Prevention:** Synchronous blocker headers look up native client values inside document headers (`localStorage`) **prior** to client layout paints to isolate visual clipping or styling pops.
