# Deploying the EoS Database API publicly

The Neon Postgres database is already remote and holds all the data
(21 materials, EoS parameters, diffraction peaks). What this guide does is
put the **API** (the FastAPI server Dioptas talks to) on a public URL, so
anyone — e.g. your professor — can point Dioptas at it without running
Docker locally.

We use **Render.com** (free tier). The API connects to the same Neon
database via the `DATABASE_URL` environment variable.

## Steps (Render dashboard)

1. Go to <https://render.com> and sign up (free). Connect your GitHub
   account when prompted.

2. **New + → Web Service** → pick the **`TheWarid0/Dioptas`** repository.

3. Configure the service:
   - **Root Directory:** `eos_database`
   - **Runtime / Language:** `Docker`
   - **Docker Command** (override the default): `./start.sh`
   - **Instance Type:** `Free`

4. Open the **Environment** section and add one variable:
   - **Key:** `DATABASE_URL`
   - **Value:** your Neon connection string
     (`postgresql://...@...neon.tech/neondb?sslmode=require`)
   - Mark it secret. **Do not** commit this string to the repo.

5. Click **Create Web Service**. Render builds the Docker image (installs
   Peritheos from git — takes a few minutes the first time) and deploys.

6. When it's live you get a public URL, e.g.
   `https://eos-database-api.onrender.com`. Test it:
   ```
   https://eos-database-api.onrender.com/health        → {"status":"healthy"}
   https://eos-database-api.onrender.com/api/v1/materials?search=Au
   ```

## Using it from Dioptas

In the EoS Database dialog (Phase panel → **DB**), replace
`http://localhost:8000` with your Render URL and click **Connect**.

## Notes

- **Cold starts:** the free tier spins the service down after ~15 min of
  inactivity. The first request after idle takes ~30–60 s to wake up; after
  that it's fast. Fine for occasional/demo use; upgrade to a paid instance
  if you need it always-on.
- **Same database for everyone:** because all instances point at the same
  Neon `DATABASE_URL`, the hosted API and any local `docker compose` setup
  serve identical data.
- **Blueprint alternative:** `render.yaml` in this folder encodes the same
  settings. To use Render's one-click Blueprint flow instead of the
  dashboard, move it to the repository root.
