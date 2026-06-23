"""
One-time repair: an earlier deduplication pass grouped rows without
including eos_order, so it accidentally collapsed BM2 and BM3 rows that
(at the time) shared identical K0/K0' numbers — wiping out most BM2
entries. This recreates one BM2 row per surviving BM3 row, re-fitting K0
independently (K0' is fixed at 4 by BM2's definition).
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit
from sqlalchemy import text

sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from peritheos.eos.rt import BM2, BM3

# "dK_dT" is mixed-case in Postgres (SQLAlchemy quotes it on creation),
# so raw SQL must quote it too or Postgres folds it to lowercase.
DK_DT_COL = '"dK_dT"'


def fit_bm2_k0(v0: float, k0_bm3: float, k0p_bm3: float) -> float:
    bm3 = BM3(V0=v0, K0=k0_bm3, K0_prime=k0p_bm3)
    pressures = np.linspace(0.0, 150.0, 40)
    volumes = np.array([bm3.calculate_volume(p) for p in pressures])

    def bm2_p(V, K0):
        return BM2(V0=v0, K0=K0).pressure(V)

    (k0,), _ = curve_fit(bm2_p, volumes, pressures, p0=[k0_bm3])
    return float(k0)


def main():
    db = SessionLocal()
    try:
        bm3_rows = db.execute(text(
            f"SELECT id, material_id, reference, v0, k0, k0_prime, "
            f"alpha0, {DK_DT_COL} AS dk_dt, reference_temperature, notes "
            f"FROM eos_parameters WHERE eos_type = 'Birch-Murnaghan' AND eos_order = 3"
        )).fetchall()

        created, updated = 0, 0
        for row in bm3_rows:
            existing = db.execute(
                text(
                    "SELECT id FROM eos_parameters WHERE material_id = :mid "
                    "AND eos_type = 'Birch-Murnaghan' AND eos_order = 2 "
                    "AND (reference = :ref OR (reference IS NULL AND :ref IS NULL))"
                ),
                {"mid": row.material_id, "ref": row.reference},
            ).fetchone()

            bm2_k0 = fit_bm2_k0(row.v0, row.k0, row.k0_prime)

            if existing:
                db.execute(
                    text("UPDATE eos_parameters SET k0 = :k0 WHERE id = :id"),
                    {"k0": bm2_k0, "id": existing.id},
                )
                updated += 1
            else:
                db.execute(
                    text(
                        f"INSERT INTO eos_parameters "
                        f"(id, material_id, eos_type, eos_order, reference, v0, k0, "
                        f"k0_prime, alpha0, {DK_DT_COL}, reference_temperature, notes, "
                        f"created_at, updated_at) "
                        f"VALUES (gen_random_uuid(), :mid, 'Birch-Murnaghan', 2, :ref, "
                        f":v0, :k0, 4.0, :alpha0, :dkdt, :tref, :notes, now(), now())"
                    ),
                    {
                        "mid": row.material_id, "ref": row.reference, "v0": row.v0,
                        "k0": bm2_k0, "alpha0": row.alpha0, "dkdt": row.dk_dt,
                        "tref": row.reference_temperature, "notes": row.notes,
                    },
                )
                created += 1

        db.commit()
        print(f"Created {created} new BM2 rows, updated {updated} existing ones.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
