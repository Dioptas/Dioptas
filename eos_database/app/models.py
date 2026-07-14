"""
SQLAlchemy database models for equation of state database. Inspired and built on top of Peritheos
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


class Material(Base):
    """Material information table"""
    __tablename__ = "materials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, index=True)
    formula = Column(String(100), nullable=False, index=True)
    symmetry = Column(String(50))  # CUBIC, HEXAGONAL, etc.
    
    # Lattice parameters at reference conditions
    a = Column(Float)  # Angstrom
    b = Column(Float)
    c = Column(Float)
    alpha = Column(Float)  # degrees
    beta = Column(Float)
    gamma = Column(Float)

    # Formula units per unit cell (crystallographic Z), e.g. 4 for fcc Au.
    # Needed to convert unit-cell volume to molar volume (Holzapfel EoS).
    formula_units_per_cell = Column(Integer)

    # Additional metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    eos_parameters = relationship("EoSParameters", back_populates="material", cascade="all, delete-orphan")
    diffraction_peaks = relationship("DiffractionPeak", back_populates="material", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Material(name='{self.name}', formula='{self.formula}')>"


class EoSParameters(Base):
    """Equation of state parameters table"""
    __tablename__ = "eos_parameters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id"), nullable=False)
    
    # EoS identification
    eos_type = Column(String(50), nullable=False, index=True)  # Birch-Murnaghan, Vinet, etc.
    eos_order = Column(Integer)  # 2, 3, or 4 for BM; None for others
    reference = Column(String(500), index=True)  # Publication citation
    
    # Common EoS parameters
    v0 = Column(Float, nullable=False)  # Zero-pressure volume (Angstrom^3)
    k0 = Column(Float, nullable=False)  # Bulk modulus at zero pressure (GPa)
    k0_prime = Column(Float, nullable=False)  # dK/dP at P=0
    k0_double_prime = Column(Float)  # d²K/dP² at P=0 (optional)
    
    # Thermal parameters
    alpha0 = Column(Float)  # Thermal expansion coefficient at T0 (K^-1)
    dK_dT = Column(Float)  # Temperature derivative of K0 (GPa/K)
    reference_temperature = Column(Float, default=298.15)  # K
    
    # Holzapfel-specific parameters
    n = Column(Integer)  # Number of atoms per formula unit
    Z = Column(Integer)  # Atomic number (for elemental materials) or effective Z
    
    # Additional parameters stored as JSON for flexibility
    # This allows storing EoS-specific parameters
    additional_params = Column(JSON)
    
    # Metadata
    pressure_range_min = Column(Float)  # GPa - validity range
    pressure_range_max = Column(Float)  # GPa
    temperature_range_min = Column(Float)  # K
    temperature_range_max = Column(Float)  # K
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    material = relationship("Material", back_populates="eos_parameters")

    def __repr__(self):
        return f"<EoS(material='{self.material.name if self.material else 'Unknown'}', type='{self.eos_type}', ref='{self.reference}')>"


class DiffractionPeak(Base):
    """Diffraction peaks from JCPDS files"""
    __tablename__ = "diffraction_peaks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id"), nullable=False)
    
    # Peak information
    d_spacing = Column(Float, nullable=False)  # Angstrom
    intensity = Column(Float)  # Relative intensity
    
    # Miller indices
    h = Column(Integer, nullable=False)
    k = Column(Integer, nullable=False)
    l = Column(Integer, nullable=False)
    
    # Relationships
    material = relationship("Material", back_populates="diffraction_peaks")

    def __repr__(self):
        return f"<Peak(d={self.d_spacing:.3f}Å, hkl=({self.h}{self.k}{self.l}), I={self.intensity})>"
