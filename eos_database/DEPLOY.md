# Running and deploying the EoS Database API (Python only)

Everything here is plain Python — no Docker, no shell scripts.
The data lives in Neon Postgres (remote); this API is just the FastAPI
layer Dioptas talks to.

## Run locally

```
cd eos_database
pip install -r requirements.txt
python run_api.py
```

Set the database connection in a `.env` file in this directory
(copy `.env.example` and fill in the Neon `DATABASE_URL`). The API is then
available at http://localhost:8000 and the interactive docs at
http://localhost:8000/docs.

Note: running a local API is optional — Dioptas connects to the hosted
one at https://dioptas.onrender.com by default.

## Deploy on Render (native Python runtime)

Render can run the API directly as a Python service — no Dockerfile:

1. Render dashboard → **New → Web Service** → pick the `TheWarid0/Dioptas`
   repository.
2. Configure:
   - **Root Directory:** `eos_database`
   - **Runtime / Language:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free`
3. Under **Environment**, add `DATABASE_URL` = the Neon connection string
   (mark it secret — never commit it).
4. Deploy. Test at `https://<your-service>.onrender.com/health`.

**If the existing service was created as a Docker service:** Render can't
switch a service's runtime in place. Create a new Web Service with the
settings above (it can reuse the same repo), confirm it works, then delete
the old one. If you want to keep the `dioptas.onrender.com` name, delete
the old service first, then name the new one `dioptas`.

## Notes

- Free tier idles after ~15 min; the first request after idle takes
  ~30–60 s to wake. Dioptas' DB dialog connects on a background thread, so
  the app never freezes while waiting.
- Everyone (hosted API, any local API) reads the same Neon database.
