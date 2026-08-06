# EoS Database

A database of equation-of-state (EoS) parameters and diffraction data for
high-pressure crystallography, with a REST API used directly by Dioptas.
Everything is Python.

## Architecture

```
Dioptas (DB button in the Phase panel)
   │  HTTPS
   ▼
FastAPI  (this folder — hosted on Render, or run locally)
   │  SQL
   ▼
Neon Postgres  (remote database, single source of truth)
```

- **Hosted API:** https://dioptas.onrender.com (Dioptas connects to it by
  default; interactive docs at `/docs`)
- **Python client:** `dioptas/eos_client.py` — usable standalone against
  any deployment of this API, not just from inside Dioptas.
- The EoS *calculations* (BM2, BM3, Vinet, Holzapfel) run inside Dioptas
  via the [Peritheos](https://github.com/CPrescher/peritheos) library.

## Database structure

Three tables:

**materials** — one row per material
| field | meaning |
|---|---|
| name, formula | e.g. "Gold", "Au" |
| symmetry | space-group system (CUBIC, HEXAGONAL, …) |
| a, b, c, alpha, beta, gamma | zero-pressure lattice parameters (Å, °) |
| formula_units_per_cell | crystallographic Z (e.g. 4 for fcc Au) — needed by the Holzapfel EoS |

**eos_parameters** — one row per (material × EoS type × literature reference)
| field | meaning |
|---|---|
| eos_type, eos_order | Birch-Murnaghan (order 2 or 3), Vinet |
| reference | literature source of the fit |
| v0 | zero-pressure unit-cell volume (Å³) |
| k0, k0_prime | bulk modulus (GPa) and its pressure derivative |
| alpha0, dK_dT | thermal expansion (K⁻¹), temperature derivative of K0 (GPa/K) |

K0/K0′ are zero-pressure material properties: the same published values
are stored for each EoS type, and the different equations extrapolate to
high pressure differently (BM2 fixes K0′ = 4 by definition).

**diffraction_peaks** — one row per peak: h, k, l, d_spacing (Å), intensity.

In Dioptas these map onto the pydantic models in `dioptas/eos_models.py`
(`Material` → `Lattice`/`Peak`, and `EosParameters`).

## Folder layout

```
eos_database/
├── app/                FastAPI application
│   ├── main.py         API endpoints (/api/v1/materials, /eos, /calculate, /search)
│   ├── models.py       SQLAlchemy tables (the schema above)
│   ├── schemas.py      pydantic request/response models
│   ├── crud.py         database queries
│   ├── calculations.py EoS math for the /calculate endpoints (Peritheos)
│   └── database.py     connection handling (.env → DATABASE_URL)
├── scripts/
│   ├── import_jcpds.py         import .jcpds files (idempotent)
│   ├── init_db.py              create tables
│   └── add_holzapfel_data.py   fill formula_units_per_cell
├── JCPDSv1/              30 original .jcpds source files (kept as reference)
├── run_api.py            run the API locally
└── requirements.txt
```

## Running locally

```
cd eos_database
pip install -r requirements.txt
python run_api.py            # serves http://localhost:8000
```

Configuration: copy `.env.example` to `.env` and set `DATABASE_URL`
(the Neon connection string). Running locally is optional — Dioptas uses
the hosted API by default.

## Importing data

```
python scripts/import_jcpds.py JCPDSv1/
```

Safe to re-run: existing records are skipped. For each material the
importer stores BM2, BM3 and Vinet rows from the file's published
V0/K0/K0′.

## File formats

- **.jcpds** — legacy input format (kept for reference and verification)
- **.eosmat** — export format written by Dioptas: plain `KEY value` lines
  with `#` comments and a single documented peak-table header instead of
  repeated `DIHKL` keywords. Can be re-imported through the Phase panel.

## Deployment

See [DEPLOY.md](DEPLOY.md) — Render, native Python runtime, no Docker.
