# Academia frontend

React + Vite + TypeScript + Tailwind 4 UI for the Smart Campus Analytics API. All data comes from the FastAPI backend in the parent folder; there is no mock data.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api to http://127.0.0.1:8000
npm run build    # type-checks, then writes dist/
```

Set `VITE_API_BASE_URL` (see `.env.example`) only if the API is on a different origin; then add the site origin to `CORS_ORIGINS` in the backend `.env`.

Roles (enforced by the backend, mirrored in the UI): `admin` can add/edit students; `admin`, `faculty` and `placement_officer` see student-level pages and interventions; `judge_demo` sees aggregate pages only.
