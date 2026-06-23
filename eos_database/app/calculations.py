"""
Equation of State calculation functions using Peritheos library.

This module provides a wrapper around the Peritheos library for EoS calculations,
while maintaining a consistent API for the rest of our system.

Note: BM4 is implemented here due to syntax issues in Peritheos upstream.

Author: Alexandru-Octavian Oprea

References:
- Peritheos: https://github.com/CPrescher/peritheos
- Angel, R.J. (2000). Equations of State. Reviews in Mineralogy and Geochemistry, 41, 35-59.
"""
import numpy as np
from typing import Optional

# Import Peritheos EoS classes (only BM2 and BM3 - BM4 has bugs in upstream)
from peritheos.eos.rt import BM2, BM3, Vinet
from peritheos.eos.rt.holzapfel import Holzapfel


class BM4_Local:
    """
    4th-order Birch-Murnaghan EoS implementation.
    
    This is implemented locally due to syntax errors in Peritheos upstream.
    Once fixed in Peritheos, we can use their implementation.
    """
    
    def __init__(self, V0: float, K0: float, K0_prime: float, K0_second: float):
        self.V0 = V0
        self.K0 = K0
        self.K0_prime = K0_prime
        self.K0_second = K0_second
    
    def pressure(self, V):
        """Calculate pressure using 4th order BM EoS"""
        f = ((self.V0 / V) ** (2/3) - 1) / 2
        zeta = (3/4) * (4 - self.K0_prime)
        xi = (3/8) * (self.K0 * self.K0_second + (self.K0_prime - 4) * (self.K0_prime - 3) + (35/9))
        
        return (
            3 * self.K0 * f * (1 + 2*f)**(5/2) * 
            (1 + 2*zeta*f + 4*xi*f**2)
        )
    
    def bulk_modulus(self, V):
        """Calculate bulk modulus at given volume"""
        f = ((self.V0 / V) ** (2/3) - 1) / 2
        zeta = (3/4) * (4 - self.K0_prime)
        xi = (3/8) * (self.K0 * self.K0_second + (self.K0_prime - 4) * (self.K0_prime - 3) + (35/9))
        
        return (
            5 * self.K0 * (1 + 2*f)**(5/2) * (1 + 2*zeta*f + 4*xi*f**2) +
            self.K0 * (1 + 2*f)**(7/2) * (2*zeta + 8*xi*f)
        )
    
    def calculate_volume(self, P):
        """Calculate volume from pressure using scipy optimization"""
        from scipy import optimize
        
        if isinstance(P, np.ndarray) or isinstance(P, list):
            return np.array([self.calculate_volume(P_i) for P_i in P])
        else:
            start_volume = self.V0 * 0.8
            result = optimize.minimize(
                lambda V: (self.pressure(V) - P) ** 2,
                start_volume,
                method="Nelder-Mead",
            )
            return result.x[0]


def _create_eos_object(
    v0: float,
    k0: float,
    k0_prime: float,
    eos_type: str,
    k0_double_prime: Optional[float] = None,
    order: int = 3,
    n: Optional[int] = None,
    Z: Optional[int] = None
):
    """
    Create appropriate Peritheos EoS object based on type.
    
    Parameters:
    -----------
    v0 : float
        Zero-pressure volume (ų)
    k0 : float
        Bulk modulus at zero pressure (GPa)
    k0_prime : float
        Pressure derivative of bulk modulus
    eos_type : str
        Type of EoS
    k0_double_prime : float, optional
        Second pressure derivative
    order : int
        Order for BM EoS (2, 3, or 4)
    n : int, optional
        Atoms per formula unit (for Holzapfel)
    Z : int, optional
        Atomic number (for Holzapfel)
    
    Returns:
    --------
    eos : Peritheos EoS object
    """
    eos_type_lower = eos_type.lower()
    
    # Birch-Murnaghan equations
    if "birch" in eos_type_lower or "bm" in eos_type_lower:
        if order == 2:
            return BM2(V0=v0, K0=k0)
        elif order == 3:
            return BM3(V0=v0, K0=k0, K0_prime=k0_prime)
        elif order == 4:
            if k0_double_prime is None:
                raise ValueError("k0_double_prime required for 4th order BM EoS")
            return BM4_Local(V0=v0, K0=k0, K0_prime=k0_prime, K0_second=k0_double_prime)
        else:
            raise ValueError(f"Invalid order {order} for Birch-Murnaghan. Must be 2, 3, or 4")
    
    # Vinet equation
    elif "vinet" in eos_type_lower:
        return Vinet(V0=v0, K0=k0, K0_prime=k0_prime)
    
    # Holzapfel equation
    elif "holzapfel" in eos_type_lower:
        if n is None:
            n = 1  # Default to 1 atom per formula
        if Z is None:
            Z = 1  # Default atomic number
        return Holzapfel(V0=v0, K0=k0, K0_prime=k0_prime, n=n, Z=Z)
    
    # Fallback for unknown types - use BM3 as default
    else:
        print(f"Warning: Unknown EoS type '{eos_type}', using Birch-Murnaghan 3rd order")
        return BM3(V0=v0, K0=k0, K0_prime=k0_prime)


def calculate_pressure(
    volume: float,
    v0: float,
    k0: float,
    k0_prime: float,
    eos_type: str = "Birch-Murnaghan",
    k0_double_prime: Optional[float] = None,
    order: int = 3,
    temperature: Optional[float] = None,
    alpha0: Optional[float] = None,
    reference_temperature: float = 298.15,
    n: Optional[int] = None,
    Z: Optional[int] = None
) -> float:
    """
    Calculate pressure using specified equation of state (via Peritheos).
    
    Parameters:
    -----------
    volume : float
        Current volume (ų)
    v0 : float
        Zero-pressure volume at reference temperature (ų)
    k0 : float
        Bulk modulus at zero pressure (GPa)
    k0_prime : float
        Pressure derivative of bulk modulus
    eos_type : str
        Type of EoS ('Birch-Murnaghan', 'Vinet', 'Holzapfel')
    k0_double_prime : float, optional
        Second pressure derivative
    order : int
        Order of EoS (for BM: 2, 3, or 4)
    temperature : float, optional
        Temperature (K) - if provided, thermal expansion is applied
    alpha0 : float, optional
        Thermal expansion coefficient (K⁻¹)
    reference_temperature : float
        Reference temperature (K)
    n : int, optional
        Atoms per formula unit (for Holzapfel)
    Z : int, optional
        Atomic number (for Holzapfel)
    
    Returns:
    --------
    pressure : float
        Pressure in GPa
    """
    # Apply thermal expansion if temperature is specified
    if temperature is not None and temperature != reference_temperature:
        if alpha0 is None:
            raise ValueError("alpha0 required for thermal calculations")
        # Simple thermal expansion: V(T) = V0 * exp(alpha * (T - T0))
        v0_at_temp = v0 * np.exp(alpha0 * (temperature - reference_temperature))
    else:
        v0_at_temp = v0
    
    # Create Peritheos EoS object
    eos = _create_eos_object(
        v0_at_temp, k0, k0_prime, eos_type,
        k0_double_prime, order, n, Z
    )
    
    # Calculate pressure using Peritheos
    pressure = eos.pressure(volume)
    
    return float(pressure)


def calculate_volume_from_pressure(
    pressure: float,
    v0: float,
    k0: float,
    k0_prime: float,
    eos_type: str = "Birch-Murnaghan",
    k0_double_prime: Optional[float] = None,
    order: int = 3,
    temperature: Optional[float] = None,
    alpha0: Optional[float] = None,
    reference_temperature: float = 298.15,
    n: Optional[int] = None,
    Z: Optional[int] = None
) -> float:
    """
    Calculate volume at given pressure using Peritheos.
    
    Peritheos uses numerical optimization (scipy.optimize) to invert P(V).
    
    Parameters:
    -----------
    pressure : float
        Target pressure (GPa)
    v0, k0, k0_prime, etc.
        EoS parameters (same as calculate_pressure)
    
    Returns:
    --------
    volume : float
        Volume at target pressure (ų)
    """
    # Apply thermal expansion if needed
    if temperature is not None and temperature != reference_temperature:
        if alpha0 is None:
            raise ValueError("alpha0 required for thermal calculations")
        v0_at_temp = v0 * np.exp(alpha0 * (temperature - reference_temperature))
    else:
        v0_at_temp = v0
    
    # Create Peritheos EoS object
    eos = _create_eos_object(
        v0_at_temp, k0, k0_prime, eos_type,
        k0_double_prime, order, n, Z
    )
    
    # Use Peritheos built-in volume calculation
    # This uses scipy.optimize.minimize under the hood
    volume = eos.calculate_volume(pressure)
    
    return float(volume)


def calculate_bulk_modulus_at_pressure(
    pressure: float,
    v0: float,
    k0: float,
    k0_prime: float,
    eos_type: str = "Birch-Murnaghan",
    k0_double_prime: Optional[float] = None,
    order: int = 3,
    temperature: Optional[float] = None,
    alpha0: Optional[float] = None,
    reference_temperature: float = 298.15,
    n: Optional[int] = None,
    Z: Optional[int] = None
) -> tuple:
    """
    Calculate bulk modulus at given pressure using Peritheos.
    
    K(P) is calculated directly from the EoS at the volume corresponding to P.
    K'(P) is calculated numerically.
    
    Parameters:
    -----------
    pressure : float
        Pressure (GPa)
    v0, k0, k0_prime, etc.
        EoS parameters
    
    Returns:
    --------
    k_at_p : float
        Bulk modulus at pressure P (GPa)
    kprime_at_p : float
        dK/dP at pressure P
    """
    # Apply thermal expansion only if needed
    if temperature is not None and temperature != reference_temperature:
        if alpha0 is None:
            raise ValueError("alpha0 required for thermal calculations")
        v0_at_temp = v0 * np.exp(alpha0 * (temperature - reference_temperature))
    else:
        v0_at_temp = v0
    
    # Create Peritheos EoS object
    eos = _create_eos_object(
        v0_at_temp, k0, k0_prime, eos_type,
        k0_double_prime, order, n, Z
    )
    
    # First get volume at this pressure
    volume = eos.calculate_volume(pressure)
    
    # Calculate K at this volume using Peritheos
    k_at_p = eos.bulk_modulus(volume)
    
    # Calculate K'(P) numerically
    # K'(P) = dK/dP
    dp = 0.01  # Small pressure increment (0.01 GPa)
    
    if pressure > dp:
        v_minus = eos.calculate_volume(pressure - dp)
        k_minus = eos.bulk_modulus(v_minus)
    else:
        k_minus = k0
    
    v_plus = eos.calculate_volume(pressure + dp)
    k_plus = eos.bulk_modulus(v_plus)
    
    kprime_at_p = (k_plus - k_minus) / (2 * dp)
    
    return float(k_at_p), float(kprime_at_p)


# Additional helper functions for compatibility

def calculate_birch_murnaghan_pressure(
    volume: float,
    v0: float,
    k0: float,
    k0_prime: float,
    k0_double_prime: Optional[float] = None,
    order: int = 3
) -> float:
    """
    Calculate pressure using Birch-Murnaghan EoS (via Peritheos).
    
    This is a convenience wrapper that directly calls Peritheos BM classes.
    """
    return calculate_pressure(
        volume, v0, k0, k0_prime,
        eos_type="Birch-Murnaghan",
        k0_double_prime=k0_double_prime,
        order=order
    )


def calculate_vinet_pressure(
    volume: float,
    v0: float,
    k0: float,
    k0_prime: float
) -> float:
    """
    Calculate pressure using Vinet EoS (via Peritheos).
    """
    return calculate_pressure(
        volume, v0, k0, k0_prime,
        eos_type="Vinet"
    )


def calculate_holzapfel_pressure(
    volume: float,
    v0: float,
    k0: float,
    k0_prime: float,
    n: int = 1,
    Z: int = 1
) -> float:
    """
    Calculate pressure using Holzapfel EoS (via Peritheos).
    
    Parameters:
    -----------
    n : int
        Number of atoms per formula unit
    Z : int
        Atomic number (for elements) or effective Z
    """
    return calculate_pressure(
        volume, v0, k0, k0_prime,
        eos_type="Holzapfel",
        n=n, Z=Z
    )

