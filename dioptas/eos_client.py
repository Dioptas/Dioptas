"""
Python client library for EoS Database API.

This client provides an easy-to-use interface for integrating the EoS database
with Dioptas or other Python applications.

Example usage:
    from eos_client import EoSClient
    
    client = EoSClient("http://localhost:8000")
    
    # Search for gold EoS
    results = client.search_material("gold")
    
    # Get specific EoS
    eos = client.get_eos_by_id(results[0]['id'])
    
    # Calculate pressure
    pressure = client.calculate_pressure(eos['id'], volume=67.5, temperature=300)
"""
import requests
from typing import List, Dict, Optional, Any
from uuid import UUID


class EoSClientError(Exception):
    """Exception raised for EoS client errors"""
    pass


class EoSClient:
    """
    Client for interacting with the Equation of State Database API.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        """
        Initialize the EoS client.
        
        Parameters:
        -----------
        base_url : str
            Base URL of the API (default: http://localhost:8000)
        timeout : int
            Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make HTTP request to API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            error_detail = e.response.json().get('detail', str(e)) if e.response else str(e)
            raise EoSClientError(f"HTTP {e.response.status_code}: {error_detail}")
        
        except requests.exceptions.RequestException as e:
            raise EoSClientError(f"Request failed: {str(e)}")
    
    # ========================================================================
    # Materials
    # ========================================================================
    
    def list_materials(self, search: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Dict]:
        """
        List materials with optional search.
        
        Parameters:
        -----------
        search : str, optional
            Search term for name or formula
        skip : int
            Number of records to skip
        limit : int
            Maximum number of records to return
        
        Returns:
        --------
        materials : list of dict
            List of material dictionaries
        """
        params = {'skip': skip, 'limit': limit}
        if search:
            params['search'] = search
        
        return self._request('GET', '/api/v1/materials', params=params)
    
    def get_material(self, material_id: UUID) -> Dict:
        """Get material by ID"""
        return self._request('GET', f'/api/v1/materials/{material_id}')
    
    def search_material(self, query: str) -> List[Dict]:
        """
        Search for materials by name or formula.
        
        This is a convenience wrapper around list_materials.
        """
        return self.list_materials(search=query)
    
    # ========================================================================
    # EoS Parameters
    # ========================================================================
    
    def list_eos(
        self,
        material_id: Optional[UUID] = None,
        eos_type: Optional[str] = None,
        reference: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict]:
        """
        List EoS parameters with filtering.
        
        Parameters:
        -----------
        material_id : UUID, optional
            Filter by material
        eos_type : str, optional
            Filter by EoS type
        reference : str, optional
            Filter by reference
        
        Returns:
        --------
        eos_list : list of dict
            List of EoS parameter dictionaries
        """
        params = {'skip': skip, 'limit': limit}
        if material_id:
            params['material_id'] = str(material_id)
        if eos_type:
            params['eos_type'] = eos_type
        if reference:
            params['reference'] = reference
        
        return self._request('GET', '/api/v1/eos', params=params)
    
    def get_eos_by_id(self, eos_id: UUID) -> Dict:
        """Get EoS parameters by ID"""
        return self._request('GET', f'/api/v1/eos/{eos_id}')
    
    def get_eos_by_material(self, material_formula: str, reference: Optional[str] = None) -> List[Dict]:
        """
        Get EoS parameters for a material.
        
        Parameters:
        -----------
        material_formula : str
            Chemical formula (e.g., 'Au', 'MgO')
        reference : str, optional
            Filter by reference author/year
        
        Returns:
        --------
        eos_list : list of dict
            List of matching EoS parameters
        """
        # First find the material
        materials = self.search_material(material_formula)
        
        if not materials:
            raise EoSClientError(f"Material '{material_formula}' not found")
        
        # Get EoS for first matching material
        material_id = materials[0]['id']
        return self.list_eos(material_id=material_id, reference=reference)
    
    # ========================================================================
    # Calculations
    # ========================================================================
    
    def calculate_pressure(
        self,
        eos_id: UUID,
        volume: float,
        temperature: float = 298.15
    ) -> float:
        """
        Calculate pressure from volume.
        
        Parameters:
        -----------
        eos_id : UUID
            ID of EoS parameters to use
        volume : float
            Volume in ų
        temperature : float
            Temperature in K (default: 298.15)
        
        Returns:
        --------
        pressure : float
            Calculated pressure in GPa
        """
        data = {
            'eos_id': str(eos_id),
            'volume': volume,
            'temperature': temperature
        }
        
        result = self._request('POST', '/api/v1/calculate/pressure', json=data)
        return result['value']
    
    def calculate_volume(
        self,
        eos_id: UUID,
        pressure: float,
        temperature: float = 298.15
    ) -> float:
        """
        Calculate volume from pressure.
        
        Parameters:
        -----------
        eos_id : UUID
            ID of EoS parameters to use
        pressure : float
            Pressure in GPa
        temperature : float
            Temperature in K (default: 298.15)
        
        Returns:
        --------
        volume : float
            Calculated volume in ų
        """
        data = {
            'eos_id': str(eos_id),
            'pressure': pressure,
            'temperature': temperature
        }
        
        result = self._request('POST', '/api/v1/calculate/volume', json=data)
        return result['value']
    
    def calculate_bulk_modulus(
        self,
        eos_id: UUID,
        pressure: float,
        temperature: float = 298.15
    ) -> Dict:
        """
        Calculate bulk modulus at pressure.
        
        Parameters:
        -----------
        eos_id : UUID
            ID of EoS parameters to use
        pressure : float
            Pressure in GPa
        temperature : float
            Temperature in K
        
        Returns:
        --------
        result : dict
            Dictionary with 'bulk_modulus' and 'k_prime' keys
        """
        data = {
            'eos_id': str(eos_id),
            'pressure': pressure,
            'temperature': temperature
        }
        
        return self._request('POST', '/api/v1/calculate/bulk_modulus', json=data)
    
    # ========================================================================
    # Search
    # ========================================================================
    
    def search(self, query: str, skip: int = 0, limit: int = 50) -> List[Dict]:
        """
        Search across all materials and EoS parameters.
        
        Parameters:
        -----------
        query : str
            Search query
        skip : int
            Records to skip
        limit : int
            Max records to return
        
        Returns:
        --------
        results : list of dict
            Search results with relevance scores
        """
        params = {'q': query, 'skip': skip, 'limit': limit}
        return self._request('GET', '/api/v1/search', params=params)
    
    # ========================================================================
    # Convenience methods for Dioptas integration (not implemented)
    # ========================================================================
    
    def get_gold_eos(self, reference: str = "Fei") -> Dict:
        """
        Get gold EoS parameters - commonly used pressure standard.
        
        Parameters:
        -----------
        reference : str
            Author/publication reference (default: 'Fei')
        
        Returns:
        --------
        eos : dict
            Gold EoS parameters
        """
        eos_list = self.get_eos_by_material("Au", reference=reference)
        
        if not eos_list:
            raise EoSClientError(f"Gold EoS (reference: {reference}) not found")
        
        return eos_list[0]
    
    def pressure_from_gold_volume(
        self,
        volume: float,
        temperature: float = 298.15,
        reference: str = "Fei"
    ) -> float:
        """
        Calculate pressure from gold unit cell volume.
        
        This is a common use case in high-pressure experiments where
        gold is used as a pressure calibrant.
        
        Parameters:
        -----------
        volume : float
            Gold unit cell volume in ų
        temperature : float
            Temperature in K
        reference : str
            Gold EoS reference to use
        
        Returns:
        --------
        pressure : float
            Pressure in GPa
        """
        gold_eos = self.get_gold_eos(reference=reference)
        return self.calculate_pressure(gold_eos['id'], volume, temperature)
    
    def close(self):
        """Close the session"""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# ============================================================================
# Example usage
# ============================================================================

if __name__ == "__main__":
    # Create client
    client = EoSClient("http://localhost:8000")
    
    try:
        # Search for materials
        print("Searching for gold...")
        materials = client.search_material("gold")
        print(f"Found {len(materials)} materials")
        
        if materials:
            print(f"\nMaterial: {materials[0]['name']}")
            print(f"Formula: {materials[0]['formula']}")
            
            # Get EoS parameters
            print("\nGetting EoS parameters...")
            eos_list = client.get_eos_by_material("Au")
            
            for eos in eos_list:
                print(f"\nEoS: {eos['eos_type']}")
                print(f"Reference: {eos['reference']}")
                print(f"K0: {eos['k0']} GPa")
                print(f"K0': {eos['k0_prime']}")
                print(f"V0: {eos['v0']:.2f} ų")
                
                # Calculate pressure at a given volume
                test_volume = eos['v0'] * 0.95  # 5% compression
                pressure = client.calculate_pressure(
                    eos['id'],
                    volume=test_volume,
                    temperature=300
                )
                print(f"\nPressure at V={test_volume:.2f} ų: {pressure:.2f} GPa")
    
    finally:
        client.close()
