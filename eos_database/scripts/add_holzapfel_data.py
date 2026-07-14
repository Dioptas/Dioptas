"""
Add the formula_units_per_cell column to the materials table and fill it
for materials whose crystal structure is unambiguous.

This is the data Holzapfel needs: to convert the unit-cell volume (Å³) to
the molar volume Peritheos expects, we must know how many formula units
sit in one unit cell (the crystallographic "Z"). n (atoms per formula) and
Z (summed atomic number) are computed from the chemical formula in Dioptas
itself — only this cell count has to be stored per material.

Usage (after confirming DATABASE_URL points at the right database):
    cd eos_database
    python scripts/add_holzapfel_data.py

Idempotent: safe to run more than once.
"""
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal

# Material name -> formula units per unit cell, from the known structures:
# fcc metals & solidified noble gases: 4 | bcc metals: 2 | hcp metals: 2
# rocksalt MgO: 4 | CsCl-type (B2) KCl/KBr: 1 | diamond: 8 (atoms, formula=C)
# graphite: 4 | corundum-type Al2O3/Fe2O3 (hex cell): 6 | B4C: 3
# cubic perovskite aristotype CaSiO3: 1
FORMULA_UNITS = {
    "Gold": 4, "Platinum": 4, "Copper": 4, "Ir": 4,
    "Neon": 4, "Neon (fcc)": 4, "Argon": 4,
    "Tungsten": 2, "Rhenium": 2,
    "MgO": 4, "KCl": 1, "KBr": 1,
    "Diamond": 8, "Graphite": 4,
    "Alumina": 6, "Fe2O3": 6, "B4C": 3,
    "CaSiO3 (Perovskite)": 1,
    # Intentionally not set (structure ambiguous across the stored EoS
    # references, or uncertain): "Fe", "Iron", "CaSiO3" (wollastonite).
}


def main():
    db = SessionLocal()
    try:
        db.execute(text(
            "ALTER TABLE materials "
            "ADD COLUMN IF NOT EXISTS formula_units_per_cell INTEGER"))
        for name, zc in FORMULA_UNITS.items():
            result = db.execute(
                text("UPDATE materials SET formula_units_per_cell = :zc "
                     "WHERE name = :name"),
                {"zc": zc, "name": name})
            print(f"  {name:24} Zc = {zc}  (rows: {result.rowcount})")
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
