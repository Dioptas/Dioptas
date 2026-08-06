"""
the EoS database API locally — plain Python, no Docker.

Usage:
    cd eos_database
    pip install -r requirements.txt
    python run_api.py

The database connection is read from the DATABASE_URL environment variable
or from a .env file in this directory (see .env.example). Point it at the
shared Neon database, and this local API serves exactly the same data as
the hosted one at https://dioptas.onrender.com.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
