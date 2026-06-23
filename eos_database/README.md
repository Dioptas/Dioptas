# Equation of State Database System

## Project Overview

This system provides a searchable database of equation of state (EoS) parameters for high-pressure crystallography, with (future) integration into Dioptas for pressure calculations.

## Features

- **Database**: PostgreSQL used for storing EoS parameters from scientific publications 
- **API**: FastAPI-based REST API for querying and calculating pressures
- **Web Interface**: Searchable web UI for browsing materials
- **Dioptas Integration**: Python API for direct integration (not implemented yet)

## System Architecture (for now i am doing everything in a locker database with basic python syntaxes for plotting)

```
┌─────────────────┐
│  Dioptas (GUI)  │
└────────┬────────┘
         │
         ├─────────── Python API calls
         │
┌────────▼─────────┐
│  FastAPI Server  │
│  - REST endpoints │
│  - EoS calculator│
└────────┬─────────┘
         │
┌────────▼─────────┐
│   UI in HTML
│    
└──────────────────┘
```

## Database Schema

### Materials Table
- `id`: UUID (primary key)
- `name`: String (e.g., "Gold", "MgO")
- `formula`: String (e.g., "Au", "MgO")
- `symmetry`: String (e.g., "CUBIC", "HEXAGONAL")
- `lattice_parameters`: JSONB (a, b, c, alpha, beta, gamma)
- `created_at`: Timestamp

### EoS Parameters Table
- `id`: UUID (primary key)
- `material_id`: UUID (foreign key)
- `eos_type`: String (e.g., "Birch-Murnaghan", "Vinet", "Murnaghan")
- `reference`: String (publication info)
- `v0`: Float (zero-pressure volume in ų)
- `k0`: Float (bulk modulus in GPa)
- `k0_prime`: Float (pressure derivative of K0)
- `k0_double_prime`: Float (optional, second derivative)
- `alpha0`: Float (thermal expansion coefficient)
- `temperature`: Float (reference temperature in K)
- `parameters`: JSONB (additional EoS-specific parameters)
- `created_at`: Timestamp

### Diffraction Peaks Table (from JCPDS)
- `id`: UUID (primary key)
- `material_id`: UUID (foreign key)
- `d_spacing`: Float (in Angstroms)
- `intensity`: Float (relative intensity)
- `h`, `k`, `l`: Integer (Miller indices)

## Supported Equation of State Types

1. **Birch-Murnaghan (2nd, 3rd, 4th order)**
   - Most commonly used
   - Based on finite strain theory
   - 3rd one is the most common
   
2. **Vinet**
   - Better for high compressions
   - Universal EoS

3. **Murnaghan**
   - Simple linear K(P) relationship
   - Good for compressions up to ~10%

4. **Natural Strain (Poirier-Tarantola)**
   - Logarithmic strain definition

## API Endpoints

### Materials
- `GET /api/v1/materials` - List all materials (with filtering)
- `GET /api/v1/materials/{id}` - Get specific material
- `POST /api/v1/materials` - Create new material
- `PUT /api/v1/materials/{id}` - Update material
- `DELETE /api/v1/materials/{id}` - Delete material

### EoS Parameters
- `GET /api/v1/eos` - List all EoS (with filtering by material, type, reference)
- `GET /api/v1/eos/{id}` - Get specific EoS
- `POST /api/v1/eos` - Create new EoS entry
- `PUT /api/v1/eos/{id}` - Update EoS
- `DELETE /api/v1/eos/{id}` - Delete EoS

### Calculations
- `POST /api/v1/calculate/pressure` - Calculate pressure from volume
- `POST /api/v1/calculate/volume` - Calculate volume from pressure
- `POST /api/v1/calculate/bulk_modulus` - Calculate K at given P

### Search
- `GET /api/v1/search?q={query}` - Full-text search across materials and references

## Installation

### Prerequisites
- Python 3.10+
- PostgreSQL database 
- Docker (optional, for local development)

### Setup Steps

API will be available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`. It looks incomprehensible, I don't like the way the strings are displayed in API

==CHECK QUICkSTART.md for the instructions on how to run this==


## Development

### Project Structure
```
eos_database/
├── app/
│   ├── main.py              # FastAPI application
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas used for data validation
│   ├── crud.py              # Database operations
│   ├── calculations.py      # EoS calculation functions/ based on peritheos and expanded
│   └── api/
│       └── v1/
│           ├── materials.py
│           ├── eos.py
│           └── calculations.py
├── scripts/
│   ├── init_db.py          # Database initialization
│   └── import_jcpds.py     # JCPDS file import
├── client/
│   └── eos_client.py       # Python client library
├── tests/
├── docker-compose.yml  # remove version if it acts weird
├── Dockerfile
├── requirements.txt
├── QUICKSTART.md
└── README.md
```

### Running Tests
```
pytest tests/
```

## References

- Angel, R.J. (2000). "Equations of State". Reviews in Mineralogy and Geochemistry, 41(1), 35-59.
- Birch-Murnaghan equation: [equations in PDF]
- Dioptas: https://www.clemensprescher.com/programs/dioptas
- Peritheos: https://github.com/CPrescher/peritheos/tree/main

## Contributing

See CONTRIBUTING.md

## License

MIT License
