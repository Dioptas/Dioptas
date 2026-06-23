"""
Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Material Schemas
# ============================================================================

class DiffractionPeakBase(BaseModel):
    """Base schema for diffraction peaks"""
    d_spacing: float = Field(..., description="d-spacing in Angstroms")
    intensity: Optional[float] = Field(None, description="Relative intensity")
    h: int = Field(..., description="Miller index h")
    k: int = Field(..., description="Miller index k")
    l: int = Field(..., description="Miller index l")


class DiffractionPeakCreate(DiffractionPeakBase):
    """Schema for creating diffraction peak"""
    pass


class DiffractionPeak(DiffractionPeakBase):
    """Schema for diffraction peak response"""
    id: UUID
    material_id: UUID
    
    model_config = ConfigDict(from_attributes=True)


class MaterialBase(BaseModel):
    """Base schema for material"""
    name: str = Field(..., max_length=200, description="Material name")
    formula: str = Field(..., max_length=100, description="Chemical formula")
    symmetry: Optional[str] = Field(None, description="Crystal symmetry")
    a: Optional[float] = Field(None, description="Lattice parameter a (Å)")
    b: Optional[float] = Field(None, description="Lattice parameter b (Å)")
    c: Optional[float] = Field(None, description="Lattice parameter c (Å)")
    alpha: Optional[float] = Field(None, description="Lattice angle alpha (°)")
    beta: Optional[float] = Field(None, description="Lattice angle beta (°)")
    gamma: Optional[float] = Field(None, description="Lattice angle gamma (°)")
    notes: Optional[str] = None


class MaterialCreate(MaterialBase):
    """Schema for creating material"""
    diffraction_peaks: Optional[List[DiffractionPeakCreate]] = None


class MaterialUpdate(BaseModel):
    """Schema for updating material"""
    name: Optional[str] = None
    formula: Optional[str] = None
    symmetry: Optional[str] = None
    a: Optional[float] = None
    b: Optional[float] = None
    c: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    gamma: Optional[float] = None
    notes: Optional[str] = None


class Material(MaterialBase):
    """Schema for material response"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class MaterialWithPeaks(Material):
    """Material with diffraction peaks"""
    diffraction_peaks: List[DiffractionPeak] = []


# ============================================================================
# EoS Parameter Schemas
# ============================================================================

class EoSParametersBase(BaseModel):
    """Base schema for EoS parameters"""
    eos_type: str = Field(..., description="EoS type (Birch-Murnaghan, Vinet, etc.)")
    eos_order: Optional[int] = Field(None, description="Order (2, 3, or 4 for BM)")
    reference: Optional[str] = Field(None, description="Publication reference")
    
    # Core parameters
    v0: float = Field(..., gt=0, description="Zero-pressure volume (ų)")
    k0: float = Field(..., gt=0, description="Bulk modulus at P=0 (GPa)")
    k0_prime: float = Field(..., description="dK/dP at P=0")
    k0_double_prime: Optional[float] = Field(None, description="d²K/dP² at P=0")
    
    # Thermal parameters
    alpha0: Optional[float] = Field(None, description="Thermal expansion (K⁻¹)")
    dK_dT: Optional[float] = Field(None, description="dK/dT (GPa/K)")
    reference_temperature: float = Field(298.15, description="Reference temperature (K)")
    
    # Holzapfel-specific parameters
    n: Optional[int] = Field(None, description="Atoms per formula unit")
    Z: Optional[int] = Field(None, description="Atomic number or effective Z")
    
    # Validity ranges
    pressure_range_min: Optional[float] = Field(None, description="Min pressure (GPa)")
    pressure_range_max: Optional[float] = Field(None, description="Max pressure (GPa)")
    temperature_range_min: Optional[float] = Field(None, description="Min temperature (K)")
    temperature_range_max: Optional[float] = Field(None, description="Max temperature (K)")
    
    additional_params: Optional[Dict[str, Any]] = Field(None, description="Additional parameters")
    notes: Optional[str] = None


class EoSParametersCreate(EoSParametersBase):
    """Schema for creating EoS parameters"""
    material_id: UUID


class EoSParametersUpdate(BaseModel):
    """Schema for updating EoS parameters"""
    eos_type: Optional[str] = None
    eos_order: Optional[int] = None
    reference: Optional[str] = None
    v0: Optional[float] = None
    k0: Optional[float] = None
    k0_prime: Optional[float] = None
    k0_double_prime: Optional[float] = None
    alpha0: Optional[float] = None
    dK_dT: Optional[float] = None
    reference_temperature: Optional[float] = None
    pressure_range_min: Optional[float] = None
    pressure_range_max: Optional[float] = None
    temperature_range_min: Optional[float] = None
    temperature_range_max: Optional[float] = None
    additional_params: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class EoSParameters(EoSParametersBase):
    """Schema for EoS parameters response"""
    id: UUID
    material_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class EoSParametersWithMaterial(EoSParameters):
    """EoS parameters with material information"""
    material: Material


# ============================================================================
# Calculation Schemas
# ============================================================================

class PressureCalculationRequest(BaseModel):
    """Request to calculate pressure from volume"""
    eos_id: UUID = Field(..., description="EoS parameters ID")
    volume: float = Field(..., gt=0, description="Volume (ų)")
    temperature: Optional[float] = Field(298.15, description="Temperature (K)")


class VolumeCalculationRequest(BaseModel):
    """Request to calculate volume from pressure"""
    eos_id: UUID = Field(..., description="EoS parameters ID")
    pressure: float = Field(..., ge=0, description="Pressure (GPa)")
    temperature: Optional[float] = Field(298.15, description="Temperature (K)")


class BulkModulusRequest(BaseModel):
    """Request to calculate bulk modulus at pressure"""
    eos_id: UUID = Field(..., description="EoS parameters ID")
    pressure: float = Field(..., ge=0, description="Pressure (GPa)")
    temperature: Optional[float] = Field(298.15, description="Temperature (K)")


class CalculationResult(BaseModel):
    """Calculation result"""
    value: float = Field(..., description="Calculated value")
    unit: str = Field(..., description="Unit of measurement")
    eos_type: str = Field(..., description="EoS type used")
    material_name: str = Field(..., description="Material name")


# ============================================================================
# Search Schemas
# ============================================================================

class SearchResult(BaseModel):
    """Search result item"""
    type: str = Field(..., description="Type: material or eos")
    id: UUID
    name: str
    formula: Optional[str] = None
    eos_type: Optional[str] = None
    reference: Optional[str] = None
    relevance_score: float = Field(..., description="Search relevance score")
