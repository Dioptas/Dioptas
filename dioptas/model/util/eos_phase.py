# SPDX-License-Identifier: MIT
"""
EosPhase: Peritheos-backed equation of state calculations for jcpds phases.

Dioptas' legacy ``jcpds.compute_volume()`` only supports 3rd-order
Birch-Murnaghan, solved by numerically minimizing the squared pressure
residual. ``EosPhase`` wraps the Peritheos library instead, giving access
to BM2, BM3, Vinet, and Holzapfel, all solved with Peritheos' own root
finders.

The two implementations are independent (different code, different
numerical methods) but should agree on the same physics. Use
``EosPhase.from_jcpds`` together with the legacy ``jcpds.compute_volume()``
to cross-check the two against each other.
"""

from __future__ import annotations

from typing import Optional

from peritheos.eos.rt import BM2, BM3, Vinet
from peritheos.eos.rt.holzapfel import Holzapfel

SUPPORTED_TYPES = ("BM2", "BM3", "VINET", "HOLZAPFEL")


class EosPhase:
    """
    Thin wrapper around Peritheos EoS classes, parameterized the same way
    as a Dioptas ``jcpds`` object so the two can be cross-validated.
    """

    def __init__(
        self,
        eos_type: str,
        v0: float,
        k0: float,
        k0_prime: Optional[float] = None,
        n: Optional[float] = None,
        z: Optional[int] = None,
    ):
        self.eos_type = eos_type.upper()
        self.v0 = v0
        self.k0 = k0
        self.k0_prime = k0_prime

        if self.eos_type == "BM2":
            self._eos = BM2(V0=v0, K0=k0)
        elif self.eos_type == "BM3":
            if k0_prime is None:
                raise ValueError("BM3 requires k0_prime")
            self._eos = BM3(V0=v0, K0=k0, K0_prime=k0_prime)
        elif self.eos_type == "VINET":
            if k0_prime is None:
                raise ValueError("Vinet requires k0_prime")
            self._eos = Vinet(V0=v0, K0=k0, K0_prime=k0_prime)
        elif self.eos_type == "HOLZAPFEL":
            if k0_prime is None or n is None or z is None:
                raise ValueError("Holzapfel requires k0_prime, n and z")
            self._eos = Holzapfel(V0=v0, K0=k0, K0_prime=k0_prime, n=n, Z=z)
        else:
            raise ValueError(
                f"Unsupported EoS type '{eos_type}'. "
                f"Supported: {', '.join(SUPPORTED_TYPES)}"
            )

    def pressure(self, volume: float) -> float:
        """Pressure (GPa) at a given unit-cell volume (Å³)."""
        return float(self._eos.pressure(volume))

    def volume(self, pressure: float) -> float:
        """Unit-cell volume (Å³) at a given pressure (GPa)."""
        return float(self._eos.calculate_volume(pressure))

    @classmethod
    def from_jcpds(cls, jcpds_obj, eos_type: str = "BM3") -> "EosPhase":
        """
        Build an ``EosPhase`` from an existing Dioptas ``jcpds`` object,
        reusing its V0/K0/K0' parameters.
        """
        p = jcpds_obj.params
        return cls(
            eos_type=eos_type,
            v0=p["v0"],
            k0=p["k0"],
            k0_prime=p.get("k0p0") or p.get("k0p"),
            n=p.get("n"),
            z=p.get("z"),
        )

    def __repr__(self) -> str:
        return (
            f"EosPhase({self.eos_type}, V0={self.v0}, K0={self.k0}, "
            f"K0'={self.k0_prime})"
        )
