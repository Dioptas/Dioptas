"""
Independently re-fit BM2 and Vinet parameters for every material, instead
of copying the Birch-Murnaghan-3 (K0, K0') values that the JCPDS source
files actually contain.

Why this exists
----------------
JCPDS files store exactly one (K0, K0') pair, explicitly defined for
3rd-order Birch-Murnaghan ("K0P: change in K0 with pressure, for
Birch-Murnaghan"). There is no raw P-V series to refit from. The previous
importer just copied that single pair into "BM2" and "Vinet" rows too,
which is misleading: those rows looked like independent fits but weren't.

This script instead:
  1. Takes the genuine BM3 fit as ground truth
  2. Generates a synthetic P-V curve from it (0-150 GPa)
  3. Re-fits BM2 (K0 free, K0' fixed at 4 by definition) and Vinet (K0,
     K0' both free) against that curve using least-squares

The result: BM2/BM3/Vinet rows with genuinely different, independently
computed numbers — the best each model can do at reproducing the same
underlying compression behavior, rather than duplicated parameters.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit
from sqlalchemy import text

sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from peritheos.eos.rt import BM2, BM3, Vinet


def refit_from_bm3(v0: float, k0_bm3: float, k0p_bm3: float):
    """Returns dict: {'BM2': (k0,), 'Vinet': (k0, k0_prime)}"""
    bm3 = BM3(V0=v0, K0=k0_bm3, K0_prime=k0p_bm3)
    pressures = np.linspace(0.0, 150.0, 40)
    volumes = np.array([bm3.calculate_volume(p) for p in pressures])

    def bm2_p(V, K0):
        return BM2(V0=v0, K0=K0).pressure(V)

    def vinet_p(V, K0, K0p):
        return Vinet(V0=v0, K0=K0, K0_prime=K0p).pressure(V)

    (bm2_k0,), _ = curve_fit(bm2_p, volumes, pressures, p0=[k0_bm3])
    (vinet_k0, vinet_k0p), _ = curve_fit(
        vinet_p, volumes, pressures, p0=[k0_bm3, k0p_bm3]
    )
    return {"BM2": (float(bm2_k0),), "Vinet": (float(vinet_k0), float(vinet_k0p))}


def main(verbose=True):
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT id, material_id, v0, k0, k0_prime FROM eos_parameters "
            "WHERE eos_type = 'Birch-Murnaghan' AND eos_order = 3"
        )).fetchall()

        for row in rows:
            fits = refit_from_bm3(row.v0, row.k0, row.k0_prime)

            db.execute(
                text(
                    "UPDATE eos_parameters SET k0 = :k0 "
                    "WHERE material_id = :mid AND eos_type = 'Birch-Murnaghan' "
                    "AND eos_order = 2"
                ),
                {"k0": fits["BM2"][0], "mid": row.material_id},
            )
            db.execute(
                text(
                    "UPDATE eos_parameters SET k0 = :k0, k0_prime = :k0p "
                    "WHERE material_id = :mid AND eos_type = 'Vinet'"
                ),
                {"k0": fits["Vinet"][0], "k0p": fits["Vinet"][1], "mid": row.material_id},
            )
            if verbose:
                print(
                    f"material {row.material_id}: "
                    f"BM3(K0={row.k0:.2f}, K0'={row.k0_prime:.3f}) -> "
                    f"BM2(K0={fits['BM2'][0]:.2f}) "
                    f"Vinet(K0={fits['Vinet'][0]:.2f}, K0'={fits['Vinet'][1]:.3f})"
                )

        db.commit()
        print(f"\nRe-fit {len(rows)} materials' BM2/Vinet parameters.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
