# Full-stack version: FastAPI (Render) + React (Vercel) + Supabase

```
backend/    FastAPI API + planning engine (core/) + Supabase storage (db.py)
frontend/   React (Vite) UI with Leaflet maps
supabase/   schema.sql  (trips, trip_days, activities)
```
Put these three folders next to `app.py` in your repo. The Streamlit app keeps working as a fallback.

## 1. Supabase (database)
1. supabase.com > New project (save the database password).
2. SQL Editor > New query > paste `supabase/schema.sql` > Run.
3. Project Settings > API: copy the **Project URL** and the **service_role** key (secret - backend only, never in the frontend).

## 2. Run locally
Backend (terminal 1):
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                               # macOS/Linux: cp .env.example .env  (then fill it in)
```
FastAPI does not read `.env` by itself, so set the variables in the same terminal:
```powershell
$env:SUPABASE_URL="https://YOUR-PROJECT.supabase.co"
$env:SUPABASE_SERVICE_KEY="your-service-role-key"
$env:ALLOWED_ORIGINS="http://localhost:5173"
uvicorn main:app --reload --port 8000
```
(If you skip the Supabase variables, a local SQLite file is used instead.) Check http://localhost:8000/health and http://localhost:8000/docs.

Frontend (terminal 2):
```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```
Open http://localhost:5173.

## 3. Deploy the backend on Render
1. render.com > Dashboard > **Add New > Web Service** > connect your GitHub repo.
2. Settings: **Root Directory** `backend` · **Runtime** Python 3 · **Build Command** `pip install -r requirements.txt` · **Start Command** `uvicorn main:app --host 0.0.0.0 --port $PORT` · Instance type Free.
3. **Environment Variables**: `PYTHON_VERSION` = `3.11.9`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ALLOWED_ORIGINS` (set after step 4; use your Vercel URL), optional `GEMINI_API_KEY` / `GROQ_API_KEY`.
4. Create Web Service. Your API URL looks like `https://your-api.onrender.com` - test `/health`.

## 4. Deploy the frontend on Vercel
1. vercel.com > **Add New > Project** > import the same repo.
2. **Root Directory** `frontend` · Framework Preset **Vite** (auto-detected) · Build `npm run build` · Output `dist`.
3. **Environment Variables**: `VITE_API_URL` = your Render URL (no trailing slash).
4. Deploy. Copy the Vercel URL (e.g. `https://your-app.vercel.app`).
5. Back in Render, set `ALLOWED_ORIGINS` to that Vercel URL and let it redeploy (otherwise the browser blocks API calls with a CORS error).

## API overview
| Method | Path | Purpose |
|---|---|---|
| GET | /health | status + storage backend |
| POST | /api/recommend | top-3 destinations |
| POST | /api/itinerary | clustered day-by-day plan |
| POST | /api/swap | replace one activity |
| POST | /api/regenerate-day | rebuild one day |
| POST | /api/summary | recompute totals after FX edits |
| POST | /api/pdf | itinerary -> PDF |
| GET/POST | /api/trips | list / save trips |
| GET/DELETE | /api/trips/{id} | load / delete a trip |
| GET | /api/trips/{id}/pdf | saved trip -> PDF |

Trips are scoped by an anonymous `X-Client-Id` (generated in the browser), so visitors only see their own.

## Troubleshooting
- **CORS error in the browser console**: `ALLOWED_ORIGINS` on Render must exactly match your Vercel URL (https, no trailing slash).
- **First request is slow / "Cannot reach the server"**: Render's free tier sleeps after ~15 min; wait ~1 minute and retry.
- **Saving fails with a Supabase error**: confirm schema.sql ran, and that you used the `service_role` key.
