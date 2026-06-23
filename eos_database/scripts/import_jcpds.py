
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal, init_db
from app import crud, schemas, models
from refit_eos_types import refit_from_bm3

# Common-name -> chemical formula lookup. The JCPDS COMMENT field holds a
# human-readable name (e.g. "Gold (04-0783, shock wave)"), not a formula —
# this table maps known names to their real formula so 'formula' isn't
# just a duplicate of 'name'. Extend as new materials are imported.
KNOWN_FORMULAS = {
    "alumina": "Al2O3", "diamond": "C", "graphite": "C",
    "gold": "Au", "silver": "Ag", "platinum": "Pt", "rhenium": "Re",
    "tungsten": "W", "copper": "Cu", "iron": "Fe", "argon": "Ar",
    "neon": "Ne", "fcc neon": "Ne",
}


def parse_jcpds_file(filepath: Path) -> Dict:
    """
    Parse a JCPDS file and extract material and EoS parameters.
    
    JCPDS files can have two formats:
    1. Old format (like mgo.jcpds): starts with material name, followed by parameters on line 2
    2. New format (like au_Fei.jcpds): VERSION: 4 format with labeled fields
    
    Parameters:
    -----------
    filepath : Path
        Path to JCPDS file
    
    Returns:
    --------
    data : dict
        Parsed data containing material and EoS information
    """
    with open(filepath, 'r') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    
    data = {
        'filename': filepath.stem,
        'material_name': None,
        'formula': None,
        'symmetry': None,
        'lattice': {},
        'eos': {},
        'peaks': [],
        'comment': None
    }
    
    # Check format version
    if lines[0].startswith('VERSION'):
        data.update(parse_new_format(lines))
    else:
        data.update(parse_old_format(lines))
    
    # Extract material name from filename if not in file
    if not data['material_name']:
        # Clean up filename: au_Fei -> Au (Fei)
        name_parts = filepath.stem.split('_')
        if len(name_parts) > 1:
            material = name_parts[0].capitalize()
            reference = ' '.join(name_parts[1:]).capitalize()
            data['material_name'] = f"{material} ({reference})"
            data['eos']['reference'] = reference
        else:
            data['material_name'] = filepath.stem.replace('-', ' ').capitalize()
    
    return data


def parse_new_format(lines: List[str]) -> Dict:
    """Parse new JCPDS format (VERSION: 4)"""
    data = {
        'lattice': {},
        'eos': {},
        'peaks': []
    }
    
    for line in lines:
        if line.startswith('COMMENT:'):
            data['comment'] = line.replace('COMMENT:', '').strip()
            # Extract material name from comment (first word, or up to a
            # hyphen so "Ca-perovskite" -> "Ca-perovskite" not just "Ca")
            match = re.match(r'([A-Za-z0-9 ]+?)(?:\s*[\(\-]|$)', data['comment'])
            if match:
                name = match.group(1).strip()
                data['material_name'] = name
                data['formula'] = KNOWN_FORMULAS.get(name.lower(), name)
        
        elif line.startswith('K0:'):
            data['eos']['k0'] = float(line.split(':')[1].strip())
        
        elif line.startswith('K0P:'):
            data['eos']['k0_prime'] = float(line.split(':')[1].strip())
        
        elif line.startswith('SYMMETRY:'):
            data['symmetry'] = line.split(':')[1].strip()
        
        elif line.startswith('A:'):
            data['lattice']['a'] = float(line.split(':')[1].strip())
        
        elif line.startswith('B:'):
            data['lattice']['b'] = float(line.split(':')[1].strip())
        
        elif line.startswith('C:'):
            data['lattice']['c'] = float(line.split(':')[1].strip())
        
        elif line.startswith('ALPHA:'):
            data['lattice']['alpha'] = float(line.split(':')[1].strip())
        
        elif line.startswith('BETA:'):
            data['lattice']['beta'] = float(line.split(':')[1].strip())
        
        elif line.startswith('GAMMA:'):
            data['lattice']['gamma'] = float(line.split(':')[1].strip())
        
        elif line.startswith('ALPHAT:'):
            alpha = float(line.split(':')[1].strip())
            if alpha != 0:
                data['eos']['alpha0'] = alpha
        
        elif line.startswith('DIHKL:'):
            # Parse diffraction peak
            parts = line.replace('DIHKL:', '').split()
            if len(parts) >= 5:
                peak = {
                    'd_spacing': float(parts[0]),
                    'intensity': float(parts[1]),
                    'h': int(float(parts[2])),
                    'k': int(float(parts[3])),
                    'l': int(float(parts[4]))
                }
                data['peaks'].append(peak)
    
    return data


def parse_old_format(lines: List[str]) -> Dict:
    """Parse old JCPDS format"""
    data = {
        'lattice': {},
        'eos': {},
        'peaks': []
    }
    
    # First line is material name/comment
    data['comment'] = lines[0]
    data['material_name'] = lines[0].split('(')[0].strip()
    
    # Look up the real chemical formula; fall back to the first word of
    # the name only if it isn't a known common name (better than nothing,
    # but should be added to KNOWN_FORMULAS once identified).
    first_word = re.match(r'([A-Za-z0-9]+)', data['material_name'])
    fallback = first_word.group(1) if first_word else data['material_name']
    data['formula'] = KNOWN_FORMULAS.get(data['material_name'].lower(), fallback)
    
    # Second line has parameters: symmetry_code, a, k0, k0_prime, scaling
    if len(lines) > 1:
        parts = lines[1].replace(',', ' ').split()
        if len(parts) >= 4:
            symmetry_code = int(parts[0])
            # Map symmetry codes (common JCPDS convention)
            symmetry_map = {
                1: 'CUBIC',
                2: 'TETRAGONAL',
                3: 'HEXAGONAL',
                4: 'ORTHORHOMBIC',
                5: 'MONOCLINIC',
                6: 'TRICLINIC'
            }
            data['symmetry'] = symmetry_map.get(symmetry_code, 'UNKNOWN')
            
            data['lattice']['a'] = float(parts[1])
            data['eos']['k0'] = float(parts[2])
            data['eos']['k0_prime'] = float(parts[3])
    
    # Find peaks section
    peak_start = None
    for i, line in enumerate(lines):
        if 'd (A)' in line or 'd(A)' in line:
            peak_start = i + 1
            break
    
    # Parse peaks
    if peak_start:
        for line in lines[peak_start:]:
            parts = line.split()
            if len(parts) >= 5:
                try:
                    peak = {
                        'd_spacing': float(parts[0]),
                        'intensity': float(parts[1]),
                        'h': int(parts[2]),
                        'k': int(parts[3]),
                        'l': int(parts[4])
                    }
                    data['peaks'].append(peak)
                except (ValueError, IndexError):
                    continue
    
    return data


def calculate_volume(a: float, b: Optional[float] = None, c: Optional[float] = None,
                     alpha: float = 90, beta: float = 90, gamma: float = 90,
                     symmetry: str = 'CUBIC') -> float:
    """
    Calculate unit cell volume from lattice parameters.
    
    For cubic: V = a³
    For general: V = abc√(1 - cos²α - cos²β - cos²γ + 2cosαcosβcosγ)
    """
    import numpy as np
    
    if symmetry == 'CUBIC':
        return a ** 3
    
    if b is None:
        b = a
    if c is None:
        c = a
    
    # Convert angles to radians
    alpha_rad = np.radians(alpha)
    beta_rad = np.radians(beta)
    gamma_rad = np.radians(gamma)
    
    # General volume formula
    volume = a * b * c * np.sqrt(
        1 - np.cos(alpha_rad)**2 - np.cos(beta_rad)**2 - np.cos(gamma_rad)**2 +
        2 * np.cos(alpha_rad) * np.cos(beta_rad) * np.cos(gamma_rad)
    )
    
    return volume


def import_jcpds_file(db: Session, filepath: Path, verbose: bool = True):
    """Import a single JCPDS file into the database"""
    if verbose:
        print(f"Importing {filepath.name}...")
    
    try:
        # Parse file
        data = parse_jcpds_file(filepath)
        
        if verbose:
            print(f"  Material: {data['material_name']}")
            print(f"  Formula: {data.get('formula', 'N/A')}")
        
        # Check if material exists
        formula = data.get('formula') or data['filename']
        existing_material = crud.get_material_by_formula(db, formula)
        
        if existing_material:
            if verbose:
                print(f"  Material already exists, updating...")
            material = existing_material
        else:
            # Create material
            lattice = data['lattice']
            material_create = schemas.MaterialCreate(
                name=data['material_name'] or data['filename'],
                formula=formula,
                symmetry=data.get('symmetry'),
                a=lattice.get('a'),
                b=lattice.get('b'),
                c=lattice.get('c'),
                alpha=lattice.get('alpha', 90.0),
                beta=lattice.get('beta', 90.0),
                gamma=lattice.get('gamma', 90.0),
                notes=data.get('comment'),
                diffraction_peaks=[
                    schemas.DiffractionPeakCreate(**peak)
                    for peak in data['peaks']
                ]
            )
            material = crud.create_material(db, material_create)
            if verbose:
                print(f"  Created material with ID: {material.id}")
        
        # Create EoS parameters if available
        if data['eos'] and 'k0' in data['eos']:
            # Calculate V0 from lattice parameters
            lattice = data['lattice']
            if 'a' in lattice:
                v0 = calculate_volume(
                    a=lattice['a'],
                    b=lattice.get('b'),
                    c=lattice.get('c'),
                    alpha=lattice.get('alpha', 90),
                    beta=lattice.get('beta', 90),
                    gamma=lattice.get('gamma', 90),
                    symmetry=data.get('symmetry', 'CUBIC')
                )
            else:
                v0 = None
            
            if v0:
                # Extract reference from comment or filename
                reference = data['eos'].get('reference') or data.get('comment') or f"From {filepath.name}"
                bm3_k0 = data['eos']['k0']
                bm3_k0_prime = data['eos']['k0_prime']

                # JCPDS only ever gives us one (K0, K0') pair, explicitly fit
                # for 3rd-order Birch-Murnaghan. Rather than copying those
                # numbers into BM2/Vinet rows (which would misrepresent them
                # as independent fits), re-fit each form against the P-V
                # curve the BM3 parameters imply.
                fits = refit_from_bm3(v0, bm3_k0, bm3_k0_prime)
                eos_specs = [
                    ('Birch-Murnaghan', 2, fits['BM2'][0], 4.0),
                    ('Birch-Murnaghan', 3, bm3_k0, bm3_k0_prime),
                    ('Vinet', None, fits['Vinet'][0], fits['Vinet'][1]),
                ]

                import_note = f"Imported from {filepath.name}"
                created_eos = []
                for eos_type, order, k0, k0_prime in eos_specs:
                    # Idempotency: re-running the import on the same file
                    # must not create duplicate rows.
                    already_exists = (
                        db.query(models.EoSParameters)
                        .filter(
                            models.EoSParameters.material_id == material.id,
                            models.EoSParameters.eos_type == eos_type,
                            models.EoSParameters.eos_order == order,
                            models.EoSParameters.notes == import_note,
                        )
                        .first()
                    )
                    if already_exists:
                        if verbose:
                            print(f"  Skipping {eos_type} (order={order}): already imported")
                        continue

                    eos_create = schemas.EoSParametersCreate(
                        material_id=material.id,
                        eos_type=eos_type,
                        eos_order=order,
                        reference=reference,
                        v0=v0,
                        k0=k0,
                        k0_prime=k0_prime,
                        alpha0=data['eos'].get('alpha0'),
                        notes=import_note
                    )

                    eos = crud.create_eos(db, eos_create)
                    created_eos.append(eos)
                
                if verbose:
                    print(f"  Created {len(created_eos)} EoS types:")
                    for eos in created_eos:
                        eos_label = f"{eos.eos_type}"
                        if eos.eos_order:
                            eos_label += f" (Order {eos.eos_order})"
                        print(f"    - {eos_label}: K0={eos.k0} GPa, K0'={eos.k0_prime}, V0={eos.v0:.2f} Å³")
        
        if verbose:
            print(f"  ✓ Success\n")
        
        return True
        
    except Exception as e:
        if verbose:
            print(f"  ✗ Error: {e}\n")
        return False


def import_jcpds_directory(directory: str, verbose: bool = True):
    """Import all JCPDS files from a directory"""
    directory_path = Path(directory)
    
    if not directory_path.exists():
        print(f"Error: Directory '{directory}' does not exist")
        return
    
    # Find all .jcpds files
    jcpds_files = list(directory_path.glob('*.jcpds'))
    
    if not jcpds_files:
        print(f"No .jcpds files found in {directory}")
        return
    
    print(f"Found {len(jcpds_files)} JCPDS files\n")
    print("=" * 60)
    
    # Initialize database
    init_db()
    
    # Create session
    db = SessionLocal()
    
    success_count = 0
    try:
        for filepath in sorted(jcpds_files):
            if import_jcpds_file(db, filepath, verbose=verbose):
                success_count += 1
    finally:
        db.close()
    
    print("=" * 60)
    print(f"\nImport complete: {success_count}/{len(jcpds_files)} files imported successfully")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python import_jcpds.py <directory>")
        print("\nExample:")
        print("  python import_jcpds.py /path/to/jcpds/files/")
        sys.exit(1)
    
    directory = sys.argv[1]
    import_jcpds_directory(directory, verbose=True)
