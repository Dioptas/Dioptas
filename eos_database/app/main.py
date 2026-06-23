"""
Main FastAPI application for Equation of State Database.
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app import crud, models, schemas, calculations
from app.database import get_db, engine

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Equation of State Database API",
    description="API for high-pressure crystallography EoS parameters and calculations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, will specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/", tags=["Health"])
def root():
    """API root endpoint"""
    return {
        "message": "Equation of State Database API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# ============================================================================
# Material Endpoints
# ============================================================================

@app.get("/api/v1/materials", response_model=List[schemas.Material], tags=["Materials"])
def list_materials(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all materials with optional search filtering.
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **search**: Search term for name or formula
    """
    materials = crud.get_materials(db, skip=skip, limit=limit, search=search)
    return materials


@app.get("/api/v1/materials/{material_id}", response_model=schemas.MaterialWithPeaks, tags=["Materials"])
def get_material(
    material_id: UUID,
    db: Session = Depends(get_db)
):
    """Get specific material by ID, including diffraction peaks"""
    material = crud.get_material(db, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@app.post("/api/v1/materials", response_model=schemas.Material, status_code=201, tags=["Materials"])
def create_material(
    material: schemas.MaterialCreate,
    db: Session = Depends(get_db)
):
    """Create a new material"""
    # Check if material with same formula already exists
    existing = crud.get_material_by_formula(db, material.formula)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Material with formula '{material.formula}' already exists"
        )
    
    return crud.create_material(db, material)


@app.put("/api/v1/materials/{material_id}", response_model=schemas.Material, tags=["Materials"])
def update_material(
    material_id: UUID,
    material_update: schemas.MaterialUpdate,
    db: Session = Depends(get_db)
):
    """Update material information"""
    material = crud.update_material(db, material_id, material_update)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@app.delete("/api/v1/materials/{material_id}", tags=["Materials"])
def delete_material(
    material_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete material (cascades to EoS and peaks)"""
    success = crud.delete_material(db, material_id)
    if not success:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"message": "Material deleted successfully"}


# ============================================================================
# EoS Parameters Endpoints
# ============================================================================

@app.get("/api/v1/eos", response_model=List[schemas.EoSParametersWithMaterial], tags=["EoS Parameters"])
def list_eos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    material_id: Optional[UUID] = None,
    eos_type: Optional[str] = None,
    reference: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List equation of state parameters with filtering.
    
    - **material_id**: Filter by material UUID
    - **eos_type**: Filter by EoS type (e.g., 'Birch-Murnaghan', 'Vinet')
    - **reference**: Search in reference field
    """
    eos_list = crud.get_eos_list(
        db,
        skip=skip,
        limit=limit,
        material_id=material_id,
        eos_type=eos_type,
        reference=reference
    )
    return eos_list


@app.get("/api/v1/eos/{eos_id}", response_model=schemas.EoSParametersWithMaterial, tags=["EoS Parameters"])
def get_eos(
    eos_id: UUID,
    db: Session = Depends(get_db)
):
    """Get specific EoS parameters by ID"""
    eos = crud.get_eos(db, eos_id)
    if not eos:
        raise HTTPException(status_code=404, detail="EoS parameters not found")
    return eos


@app.post("/api/v1/eos", response_model=schemas.EoSParameters, status_code=201, tags=["EoS Parameters"])
def create_eos(
    eos: schemas.EoSParametersCreate,
    db: Session = Depends(get_db)
):
    """Create new EoS parameters"""
    # Verify material exists
    material = crud.get_material(db, eos.material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    return crud.create_eos(db, eos)


@app.put("/api/v1/eos/{eos_id}", response_model=schemas.EoSParameters, tags=["EoS Parameters"])
def update_eos(
    eos_id: UUID,
    eos_update: schemas.EoSParametersUpdate,
    db: Session = Depends(get_db)
):
    """Update EoS parameters"""
    eos = crud.update_eos(db, eos_id, eos_update)
    if not eos:
        raise HTTPException(status_code=404, detail="EoS parameters not found")
    return eos


@app.delete("/api/v1/eos/{eos_id}", tags=["EoS Parameters"])
def delete_eos(
    eos_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete EoS parameters"""
    success = crud.delete_eos(db, eos_id)
    if not success:
        raise HTTPException(status_code=404, detail="EoS parameters not found")
    return {"message": "EoS parameters deleted successfully"}


# ============================================================================
# Calculation Endpoints
# ============================================================================

@app.post("/api/v1/calculate/pressure", response_model=schemas.CalculationResult, tags=["Calculations"])
def calculate_pressure(
    request: schemas.PressureCalculationRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate pressure from volume using specified EoS.
    
    Uses Peritheos for calculations.
    Returns calculated pressure in GPa.
    """
    # Get EoS parameters
    eos = crud.get_eos(db, request.eos_id)
    if not eos:
        raise HTTPException(status_code=404, detail="EoS parameters not found")
    
    try:
        pressure = calculations.calculate_pressure(
            volume=request.volume,
            v0=eos.v0,
            k0=eos.k0,
            k0_prime=eos.k0_prime,
            eos_type=eos.eos_type,
            k0_double_prime=eos.k0_double_prime,
            order=eos.eos_order or 3,
            temperature=request.temperature,
            alpha0=eos.alpha0,
            reference_temperature=eos.reference_temperature,
            n=eos.n,
            Z=eos.Z
        )
        
        return schemas.CalculationResult(
            value=pressure,
            unit="GPa",
            eos_type=eos.eos_type,
            material_name=eos.material.name
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation error: {str(e)}")


@app.post("/api/v1/calculate/volume", response_model=schemas.CalculationResult, tags=["Calculations"])
def calculate_volume(
    request: schemas.VolumeCalculationRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate volume from pressure using specified EoS.
    
    Uses Peritheos for calculations.
    Returns calculated volume in angstrom cube.
    """
    # Get EoS parameters
    eos = crud.get_eos(db, request.eos_id)
    if not eos:
        raise HTTPException(status_code=404, detail="EoS parameters not found")
    
    try:
        volume = calculations.calculate_volume_from_pressure(
            pressure=request.pressure,
            v0=eos.v0,
            k0=eos.k0,
            k0_prime=eos.k0_prime,
            eos_type=eos.eos_type,
            k0_double_prime=eos.k0_double_prime,
            order=eos.eos_order or 3,
            temperature=request.temperature,
            alpha0=eos.alpha0,
            reference_temperature=eos.reference_temperature,
            n=eos.n,
            Z=eos.Z
        )
        
        return schemas.CalculationResult(
            value=volume,
            unit="Ų",
            eos_type=eos.eos_type,
            material_name=eos.material.name
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation error: {str(e)}")


@app.post("/api/v1/calculate/bulk_modulus", response_model=dict, tags=["Calculations"])
def calculate_bulk_modulus_endpoint(
    request: schemas.BulkModulusRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate bulk modulus and its pressure derivative at given pressure. Not implemented in the UI.
    
    Uses Peritheos library for calculations.
    Returns K(P) and K'(P).
    """
    # Get EoS parameters
    eos = crud.get_eos(db, request.eos_id)
    if not eos:
        raise HTTPException(status_code=404, detail="EoS parameters not found")
    
    try:
        k_at_p, kprime_at_p = calculations.calculate_bulk_modulus_at_pressure(
            pressure=request.pressure,
            v0=eos.v0,
            k0=eos.k0,
            k0_prime=eos.k0_prime,
            eos_type=eos.eos_type,
            k0_double_prime=eos.k0_double_prime,
            order=eos.eos_order or 3,
            temperature=request.temperature,
            alpha0=eos.alpha0,
            reference_temperature=eos.reference_temperature,
            n=eos.n,
            Z=eos.Z
        )
        
        return {
            "bulk_modulus": k_at_p,
            "k_prime": kprime_at_p,
            "unit": "GPa",
            "pressure": request.pressure,
            "eos_type": eos.eos_type,
            "material_name": eos.material.name
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation error: {str(e)}")


# ============================================================================
# Search Endpoint
# ============================================================================

@app.get("/api/v1/search", response_model=List[schemas.SearchResult], tags=["Search"])
def search(
    q: str = Query(..., min_length=1, description="Search query"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Full-text search across materials and EoS parameters.
    
    Searches in:
    - Material names and formulas
    - EoS references
    - Notes
    """
    results = crud.search_all(db, query=q, skip=skip, limit=limit)
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
