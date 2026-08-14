# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""Bundled equation-of-state material database (see material.py for the
data format and database.py for the loader)."""

from .material import (Material, Lattice, record_label, record_eos_type,
                       record_pressure_range, reference_authors,
                       reference_short, reference_text, reference_year)
from .database import (eos_database_path, load_materials, search_materials)
from .jcpds_builder import (build_jcpds, apply_eos_record, material_from_jcpds,
                            save_material_file, load_material_file)

__all__ = [
    "Material", "Lattice", "record_label", "record_eos_type",
    "record_pressure_range", "reference_authors", "reference_short",
    "reference_text", "reference_year",
    "eos_database_path", "load_materials", "search_materials",
    "build_jcpds", "apply_eos_record", "material_from_jcpds",
    "save_material_file", "load_material_file",
]
