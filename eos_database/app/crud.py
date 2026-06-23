"""
CRUD (Create, Read, Update, Delete) operations for database models.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app import models, schemas


# ============================================================================
# Material CRUD
# ============================================================================

def get_material(db: Session, material_id: UUID) -> Optional[models.Material]:
    """Get material by ID"""
    return db.query(models.Material).filter(models.Material.id == material_id).first()


def get_material_by_formula(db: Session, formula: str) -> Optional[models.Material]:
    """Get material by chemical formula"""
    return db.query(models.Material).filter(models.Material.formula == formula).first()


def get_materials(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None
) -> List[models.Material]:
    """
    Get list of materials with optional filtering.
    
    Parameters:
    -----------
    db : Session
        Database session
    skip : int
        Number of records to skip (pagination)
    limit : int
        Maximum number of records to return
    search : str, optional
        Search term for name or formula
    """
    query = db.query(models.Material)
    
    if search:
        search_filter = or_(
            models.Material.name.ilike(f"%{search}%"),
            models.Material.formula.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    return query.offset(skip).limit(limit).all()


def create_material(
    db: Session,
    material: schemas.MaterialCreate
) -> models.Material:
    """Create new material"""
    # Create material
    db_material = models.Material(
        name=material.name,
        formula=material.formula,
        symmetry=material.symmetry,
        a=material.a,
        b=material.b,
        c=material.c,
        alpha=material.alpha,
        beta=material.beta,
        gamma=material.gamma,
        notes=material.notes
    )
    db.add(db_material)
    db.commit()
    db.refresh(db_material)
    
    # Add diffraction peaks if provided
    if material.diffraction_peaks:
        for peak in material.diffraction_peaks:
            db_peak = models.DiffractionPeak(
                material_id=db_material.id,
                d_spacing=peak.d_spacing,
                intensity=peak.intensity,
                h=peak.h,
                k=peak.k,
                l=peak.l
            )
            db.add(db_peak)
        db.commit()
        db.refresh(db_material)
    
    return db_material


def update_material(
    db: Session,
    material_id: UUID,
    material_update: schemas.MaterialUpdate
) -> Optional[models.Material]:
    """Update material"""
    db_material = get_material(db, material_id)
    if not db_material:
        return None
    
    # Update only provided fields
    update_data = material_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_material, field, value)
    
    db.commit()
    db.refresh(db_material)
    return db_material


def delete_material(db: Session, material_id: UUID) -> bool:
    """Delete material (and cascade to EoS and peaks)"""
    db_material = get_material(db, material_id)
    if not db_material:
        return False
    
    db.delete(db_material)
    db.commit()
    return True


# ============================================================================
# EoS Parameters CRUD
# ============================================================================

def get_eos(db: Session, eos_id: UUID) -> Optional[models.EoSParameters]:
    """Get EoS parameters by ID"""
    return db.query(models.EoSParameters).filter(models.EoSParameters.id == eos_id).first()


def get_eos_list(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    material_id: Optional[UUID] = None,
    eos_type: Optional[str] = None,
    reference: Optional[str] = None
) -> List[models.EoSParameters]:
    """
    Get list of EoS parameters with filtering.
    
    Parameters:
    -----------
    material_id : UUID, optional
        Filter by material
    eos_type : str, optional
        Filter by EoS type
    reference : str, optional
        Search in reference field
    """
    query = db.query(models.EoSParameters)
    
    if material_id:
        query = query.filter(models.EoSParameters.material_id == material_id)
    
    if eos_type:
        query = query.filter(models.EoSParameters.eos_type.ilike(f"%{eos_type}%"))
    
    if reference:
        query = query.filter(models.EoSParameters.reference.ilike(f"%{reference}%"))
    
    return query.offset(skip).limit(limit).all()


def get_eos_by_material_and_reference(
    db: Session,
    material_formula: str,
    reference: str
) -> Optional[models.EoSParameters]:
    """Get EoS by material formula and reference"""
    return (
        db.query(models.EoSParameters)
        .join(models.Material)
        .filter(models.Material.formula == material_formula)
        .filter(models.EoSParameters.reference.ilike(f"%{reference}%"))
        .first()
    )


def create_eos(
    db: Session,
    eos: schemas.EoSParametersCreate
) -> models.EoSParameters:
    """Create new EoS parameters"""
    db_eos = models.EoSParameters(**eos.model_dump())
    db.add(db_eos)
    db.commit()
    db.refresh(db_eos)
    return db_eos


def update_eos(
    db: Session,
    eos_id: UUID,
    eos_update: schemas.EoSParametersUpdate
) -> Optional[models.EoSParameters]:
    """Update EoS parameters"""
    db_eos = get_eos(db, eos_id)
    if not db_eos:
        return None
    
    update_data = eos_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_eos, field, value)
    
    db.commit()
    db.refresh(db_eos)
    return db_eos


def delete_eos(db: Session, eos_id: UUID) -> bool:
    """Delete EoS parameters"""
    db_eos = get_eos(db, eos_id)
    if not db_eos:
        return False
    
    db.delete(db_eos)
    db.commit()
    return True


# ============================================================================
# Search
# ============================================================================

def search_all(
    db: Session,
    query: str,
    skip: int = 0,
    limit: int = 50
) -> List[schemas.SearchResult]:
    """
    Full-text search across materials and EoS parameters.
    
    Returns combined results with relevance scoring.
    """
    results = []
    
    # Search materials
    material_query = db.query(models.Material).filter(
        or_(
            models.Material.name.ilike(f"%{query}%"),
            models.Material.formula.ilike(f"%{query}%"),
            models.Material.notes.ilike(f"%{query}%")
        )
    ).limit(limit)
    
    for material in material_query:
        # Simple relevance: exact match = 1.0, partial = 0.5
        score = 1.0 if query.lower() in material.name.lower() or query.lower() == material.formula.lower() else 0.5
        
        results.append(schemas.SearchResult(
            type="material",
            id=material.id,
            name=material.name,
            formula=material.formula,
            relevance_score=score
        ))
    
    # Search EoS
    eos_query = db.query(models.EoSParameters).join(models.Material).filter(
        or_(
            models.EoSParameters.reference.ilike(f"%{query}%"),
            models.EoSParameters.eos_type.ilike(f"%{query}%"),
            models.Material.name.ilike(f"%{query}%"),
            models.Material.formula.ilike(f"%{query}%")
        )
    ).limit(limit)
    
    for eos in eos_query:
        score = 1.0 if query.lower() in (eos.reference or "").lower() else 0.5
        
        results.append(schemas.SearchResult(
            type="eos",
            id=eos.id,
            name=eos.material.name,
            formula=eos.material.formula,
            eos_type=eos.eos_type,
            reference=eos.reference,
            relevance_score=score
        ))
    
    # Sort by relevance and return
    results.sort(key=lambda x: x.relevance_score, reverse=True)
    return results[skip:skip+limit]
