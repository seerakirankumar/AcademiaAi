# API reference

Local base URL: `http://127.0.0.1:8000` · Swagger UI: `/docs`.

Success responses use `{ "status": "success", "data": ..., "meta": {...} }`. Errors use `{ "status": "error", "error": { "code", "type", "message", "details" } }`.

| Endpoint | Access | Description |
|---|---|---|
| `GET /` | Public | API welcome information |
| `GET /api/health` | Public | Dataset load status and counts |
| `POST /api/auth/login` | Public | Username/password form login; returns a bearer token |
| `GET /api/auth/me` | Signed in | Current user and role |
| `POST /api/auth/users` | Admin | Create a staff login (password is hashed in `data/users.json`) |
| `GET /api/dashboard/summary` | Staff / demo role | Dashboard KPIs |
| `GET /api/students` | Admin / faculty / placement officer | Searchable, filterable student list |
| `GET /api/students/{id}` | Admin / faculty / placement officer | Unified student profile |
| `POST /api/students` | Admin only | Add a student; generates a `STU########` ID if omitted |
| `PATCH /api/students/{id}` | Admin only | Update existing student fields |
| `GET /api/students/{id}/score` | Admin / faculty / placement officer | Score breakdown and formula |
| `GET /api/students/{id}/recommendations` | Admin / faculty / placement officer | Supportive recommendations |
| `GET /api/risks` | Admin / faculty / placement officer | Rule-based academic/placement indicators |
| `GET /api/analytics/departments` | Staff / demo role | Department metrics |
| `GET /api/analytics/trends` | Staff / demo role | Reports whether historical trend data exists |
| `GET /api/segments` | Staff / demo role | Segment summaries |
| `GET /api/interventions` | Admin / faculty / placement officer | Intervention history and filters |
| `POST /api/interventions` | Admin / faculty / placement officer | Add an intervention; persists to `data/interventions.csv` |
| `PATCH /api/interventions/{id}` | Admin / faculty / placement officer | Update intervention status/notes and persist to CSV |
| `GET /api/metadata` | Staff / demo role | Departments, status choices, dataset info |

## Student CRUD

All request bodies are JSON. The API validates numeric ranges and allowed status categories.

Example create:

```json
{
  "student_name": "Example Student",
  "department": "Computer Science and Engineering",
  "year_of_study": 1,
  "section": "A",
  "admission_year": 2026,
  "student_email": "example@college.edu",
  "cgpa": 8.2,
  "overall_attendance_pct": 92,
  "placement_status": "Not started"
}
```

`student_id` is optional; if omitted, the backend generates the next `STU########` ID. Create initializes rows in each working student feature CSV. PATCH accepts any editable field, for example `{ "student_name": "Updated Name", "cgpa": 9.1 }`. Both endpoints save to the top-level CSVs in `data/`, reload the analytics service, and recalculate scores/risks. They require the `admin` role.

## Intervention endpoints

`POST /api/interventions` accepts `student_id`, `intervention_type`, optional `assigned_date`, `status`, and `follow_up_notes`. Types: `Academic tutoring`, `Aptitude training`, `Attendance counselling`, `Coding practice`, `Mentoring`, `Mock interview`. Statuses: `Recommended`, `Assigned`, `In progress`, `Completed`. `PATCH /api/interventions/{id}` requires at least one of `status` or `follow_up_notes`.

## Persistence and authentication

No SQL database is used. Student features are stored in CSV files; interventions persist in `data/interventions.csv`; local account hashes and roles persist in `data/users.json`. Configure the first administrator in `.env`. Changing bootstrap credentials does not overwrite an existing account; use `python scripts/reset_admin_password.py` to reset it.

## Notes

- List endpoints use `limit` and `offset`; filters are case-insensitive.
- Scores and risk indicators are preliminary rule-based guidance, not probabilities.
- The live working CSVs are separate from read-only workbook snapshots in `data/source_sheets/`.
