# Quick Start Guide

## Setup for xda Project

### 1. Local Development (with Docker)

This is the easiest way to get started:

```bash
# Navigate to the project directory
cd eos_database

# Start the database and API
docker-compose up -d

# Wait for services to be ready (about 10 seconds)
sleep 10

# Import JCPDS files
docker compose exec api python scripts/import_jcpds.py /data/jcpds
# Check API is running
curl http://localhost:8000/health
```

The API will be available at `http://localhost:8000`
API documentation at `http://localhost:8000/docs`


open web:

open web_ui.html

## Troubleshooting

### Database Connection Issues

```bash
# Check if database is running
docker-compose ps

# View logs
docker-compose logs db
docker-compose logs api

# Restart services
docker-compose restart
```

### Import Issues

```bash
# Run import with verbose output
python scripts/import_jcpds.py /path/to/files/ --verbose

# Check database contents
docker-compose exec db psql -U eos_user -d eos_db -c "SELECT * FROM materials;"
```

### API Not Responding

```bash
# Check if API is running
curl http://localhost:8000/health

# View API logs
docker-compose logs -f api

# Restart API
docker-compose restart api
```


