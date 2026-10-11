<<<<<<< HEAD
# Smart Campus Analytics — CSV-backed full project

A React/Vite/TypeScript frontend (the Academia redesign) and FastAPI backend for a student analytics dashboard. It loads the supplied Excel dataset converted to CSV, computes a transparent student success score and rule-based support indicators, and lets an administrator add students or edit student records. **No SQL database is required.** Student and intervention changes are written back to CSV files; authentication users are stored as password hashes in `data/users.json`.

> Scores and support indicators are prototype guidance, not probabilities or official institutional measures. Review data and thresholds before real-world use.

## Project structure

```text
smart-campus-analytics-backend/
├── app/                 # FastAPI, CSV services, scoring, RBAC and routes
├── data/                # Live working CSV files and source worksheet snapshots
├── docs/                # API notes
├── frontend/            # React + Vite dashboard
├── tests/               # API, CSV persistence, scoring and auth tests
├── .env.example
├── requirements.txt
└── README.md
```

## 1. Configure the backend (Windows PowerShell)

Open PowerShell in this folder (the folder containing `app`, `data`, and `requirements.txt`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

In `.env`, set a random `AUTH_SECRET_KEY` and a unique administrator password of at least 12 characters. Generate the secret with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set `AUTH_BOOTSTRAP_ADMIN_USERNAME` to your preferred login username and `AUTH_BOOTSTRAP_ADMIN_PASSWORD` to your private password. Do not leave any `REPLACE_...` placeholder in `.env`. Never commit or share `.env`.

Start the backend:

```powershell
uvicorn app.main:app --reload --env-file .env
```

On the first successful startup, the API creates `data/users.json` and adds the bootstrap admin if that username is not already present. The password is stored as a salted PBKDF2-HMAC-SHA256 hash. Changing bootstrap values later does not overwrite an existing user's password automatically. To reset an existing admin password without deleting other accounts, run `python scripts/reset_admin_password.py` and follow the prompts.

Backend URLs:

- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/health`

## 2. Start the frontend

Open a **second** PowerShell terminal:

```powershell
cd frontend
npm install
npm run dev
```

(Requires Node.js 20.19+ or 22.12+.)

Open the URL Vite prints, usually `http://localhost:5173`. Keep both terminals running. The Vite dev server proxies `/api` requests to the FastAPI backend.

## 3. Sign in and manage records

- Sign in with an account already in `data/users.json` (the existing `skmuzamill` admin keeps working), or with `AUTH_BOOTSTRAP_ADMIN_USERNAME` and `AUTH_BOOTSTRAP_ADMIN_PASSWORD` from your `.env`.
- Open **Students** and use **Add student** to create a record. The backend generates a new `STU########` ID if you leave the ID blank.
- Open a student and choose **Edit student** to change the record; **Record intervention** logs support.
- Admin create/update operations write the student row to `students.csv` and all feature CSVs, then reload the analytics service so scores, risks, and dashboard metrics refresh.
- Interventions are saved in `data/interventions.csv`.
- CSV files in the top-level `data/` directory are the live working data. `data/source_sheets/` contains read-only snapshots of the imported workbook sheets and is not edited by the dashboard.

Run the tests:

```powershell
pytest
```

Tests count the rows in `data/students.csv`, so they keep passing as students are added.

## 4. API highlights

- `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/users`
- `GET /api/dashboard/summary`
- `GET /api/students`, `GET /api/students/{student_id}`
- `POST /api/students` — admin only, adds a student and initializes their feature rows
- `PATCH /api/students/{student_id}` — admin only, updates student fields
- `GET /api/students/{student_id}/score`, `GET /api/students/{student_id}/recommendations`
- `GET /api/risks`, `GET /api/analytics/departments`, `GET /api/segments`
- `GET/POST/PATCH /api/interventions...` — intervention writes persist to CSV

## 5. Data and limitations

The workbook's multiple attendance, engagement, skill, and feedback rows are aggregated into per-student feature files for this dashboard. The aggregation rules and approximations are documented in `data/DATASET_README.md`. No machine-learning model is claimed here. The success score and risk levels use transparent configurable rules in `app/config.py` and should be validated by institutional staff.

CSV persistence is appropriate for a local demo or single-process prototype. Keep a backup of `data/*.csv`, run one backend worker, and use a transactional database with backups/permissions/audit logs before multi-user production deployment. Do not expose this development server directly to the public internet.

Student-level CSV files and source-sheet snapshots are excluded from Git because they can contain names, IDs, emails, and other personal data. Before starting a checkout or deployment, provision only institution-approved data through private storage; do not commit real student records to a public repository. Use persistent private storage for CSV writes, or replace CSV persistence with an appropriate database before multi-user production use.

## Groq AI data assistant

The authenticated **AI data assistant** is available from the left navigation. It answers questions using aggregate metrics from the current CSV datasets and a small set of relevant, de-identified records. Student names, IDs, and email addresses are removed before dataset context is sent to Groq; authorized staff labels are restored locally in the answer. Demo viewers receive aggregate-only context.

1. Add `GROQ_API_KEY` and optionally `GROQ_MODEL=openai/gpt-oss-120b` to the backend `.env` file. Never put the Groq key in the frontend `.env` or commit it.
2. Restart FastAPI after editing `.env`.
3. Sign in to the app and choose **AI data assistant**.

The assistant uses the Groq API and therefore requires internet access and a valid key. Answers are grounded to the provided context but can still be imperfect; verify important figures against the dashboard/CSV files. Risk indicators are support prompts, not probabilities or final decisions.
=======
# AcademiaAi
Academia AI is an AI-powered student analytics platform that analyzes academic performance, attendance, engagement, skills, and placement readiness through interactive dashboards, risk insights, and an AI assistant to support data-driven decisions and improve student success.
>>>>>>> ded523df7ed8155e67253772fa74ba751a7d80d4
