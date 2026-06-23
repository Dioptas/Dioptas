# Quick Import Guide

## Import JCPDS Files Using Docker (Recommended)

### Step 1: Update docker-compose.yml

Edit `docker-compose.yml` and update the JCPDS path to match yours:

```yaml
volumes:
  - ./app:/app/app
  - ./scripts:/app/scripts
  - ./client:/app/client
  # Update this path to your JCPDS directory
  - ~/Desktop/DATABASE/JCPDS_Starting_Point:/data/jcpds:ro
```

### Step 2: Restart Docker

```bash
docker compose down
docker compose up -d
```

### Step 3: Import Files

```bash
# Files are now available at /data/jcpds inside container
docker compose exec api python scripts/import_jcpds.py /data/jcpds
```

## Alternative: Install Dependencies Locally

If you prefer to run outside Docker:

```bash
# Install dependencies
pip install sqlalchemy psycopg2-binary

# Set database URL
export DATABASE_URL="postgresql://eos_user:eos_password@localhost:5432/eos_db"

# Run import
python scripts/import_jcpds.py /Users/alex.oprea/Desktop/DATABASE/JCPDS_Starting_Point
```

## Verify Import

```bash
# Check materials
curl http://localhost:8000/api/v1/materials

# Check EoS parameters
curl http://localhost:8000/api/v1/eos
```
