# EoS material structure audit

Audit date: 2026-08-13.

This pass prepares the bundled EoS materials for a future Phase Smith
structure-factor calculation. A complete structure entry contains the
Hermann-Mauguin symbol, International Tables number, crystallographic `Z`,
and one occupied asymmetric-unit representative per Wyckoff site. The full
symmetry-expanded cell is deliberately not stored.

## Coverage

The database contains 78 material documents. Forty-eight now have complete
structure metadata and 30 remain intentionally unset. Every completed entry
passes an automated check that Wyckoff multiplicity times occupancy reproduces
the formula stoichiometry multiplied by `Z`.

The completed set is:

`alumina`, `aragonite`, `argon_hcp`, `boron_nitride`, `ca_perovskite`,
`ca_perovskite_perovskite_pv`, `cao`, `cao_b2`, `casio3_perovskite`,
`cobalt_hcp`, `coo`, `copper`, `cscl`, `diamond`, `fe`, `fe2o3`, `fe3o4`,
`fe_fcc`, `feh3`, `feo`, `feo_b8`, `feo_b8_2`, `geo2_rutile`, `goethite`,
`gold`, `graphite`, `indium_nitride`, `iron`, `kcl`, `li_bcc`, `magnesite`,
`mgo`, `molybdenum`, `nacl_b1`, `nacl_b2`, `neon_fcc`, `nis`, `pbs_b1`,
`perovskite_cubic`, `platinum`, `rhenium`, `sio2_stv_andr`, `sno2`, `sro`,
`sro_b2`, `tantalum`, `tungsten`, and `zircon`.

Fixed-coordinate prototypes were assigned only where the phase identity and
cell setting are unambiguous: fcc, bcc, hcp, diamond, graphite, zinc blende,
rocksalt/B1, CsCl/B2, NiAs/B8, cubic perovskite, and simple-cubic FeH3.

## Refined internal coordinates

Structures with free positional parameters were checked against published
crystallographic refinements or the phase card identified by the material.
The stored coordinates use the same setting as the material cell.

| Material | Space group | Stored asymmetric-unit coordinates | Structure source |
|---|---|---|---|
| Al2O3 | R-3c (167) | Al 12c z=0.3522; O 18e x=0.3061 | JCPDS 0-173 |
| Fe2O3 | R-3c (167) | Fe 12c z=0.14783; O 18e x=0.30618 | JCPDS 33-664 |
| Fe3O4 | Fd-3m (227) | Fe 8a, Fe 16d; O 32e u=0.2549 | Fleet, Acta Cryst. B37, 917-920 (1981), doi:10.1107/S0567740881004597 |
| MgCO3 | R-3c (167) | Mg 6b, C 6a; O 18e x=0.2778 | Markgraf and Reeder, American Mineralogist 70, 590-600 (1985) |
| GeO2 rutile | P42/mnm (136) | Ge 2a; O 4f u=0.306 | Haines et al., Physics and Chemistry of Minerals 27, 575-582 (2000) |
| SiO2 stishovite | P42/mnm (136) | Si 2a; O 4f u=0.3062 | Baur and Khan, Acta Cryst. B27, 2133-2139 (1971) |
| SnO2 cassiterite | P42/mnm (136) | Sn 2a; O 4f u=0.307 | Baur, Acta Cryst. 9, 515-520 (1956) |
| InN wurtzite | P63mc (186) | In 2b; N 2b u=0.3769 | Paszkowicz et al., Powder Diffraction 18, 114-121 (2003), doi:10.1154/1.1566957 |
| CaCO3 aragonite | Pmcn (62) | Ca 4c, C 4c, O 4c, O 8d | Ye et al., American Mineralogist 97, 707-712 (2012) |
| FeOOH goethite | Pbnm (62) | Fe 4c, O 4c, O 4c, H 4c | Yang et al., Acta Cryst. E62, i250-i252 (2006), doi:10.1107/S1600536806047258 |
| ZrSiO4 zircon | I41/amd (141) | Zr 4a, Si 4b; O 16h y=0.066, z=0.195 | Hazen and Finger, American Mineralogist 64, 196-201 (1979) |

The material JSON notes retain these structure references where they differ
from the EoS reference.

## Deferred structures

The remaining entries were not populated from a generic prototype. Their
intensities depend on phase-specific internal coordinates, site disorder,
hydrogen positions, molecular orientation, or a material identity that must
first be reconciled.

| Files | Reason for deferral |
|---|---|
| `alpha_ca2sio5`, `alphah_ca2sio5`, `alphal_ca2sio5`, `gamma_ca2sio5`, `k2nif4_ca2sio5`, `larnite` | The imported names/formulas are inconsistent with the Ca2SiO4 polymorph nomenclature; identity, setting, and source structure must be reconciled together. |
| `casi2o5`, `casi2o5_2` | Complex mono-/triclinic CaSi2O5 structures; the EoS paper does not provide an unambiguous ambient asymmetric unit for these imported settings. |
| `ca_perovskite_tetragonal`, `sno2_cubic_27gpa`, `sno2_pa_3_at_48gpa` | High-pressure polymorphs whose internal coordinates and, for the 27 GPa SnO2 entry, exact structure model must be taken at the stated pressure. |
| `feh2`, `e_feooh`, `fe3s`, `fes`, `fes_iii` | Hydrogen/iron-sulfide high-pressure structures need the experimental or calculated site table for the exact phase and pressure. |
| `coesite`, `naalsi2o6`, `naalsio4_calcium_ferrite`, `molybenum_carbide_mo2c` | Multi-site structures require a complete primary-source CIF/table and setting conversion. |
| `iceviii`, `nitrogen_epsilon`, `o8` | Molecular positions and orientations cannot be reconstructed from lattice and powder peaks alone. |
| `majorite`, `mgsio3`, `mg7si2o8`, `phase_d` | Complex mantle phases; composition/site occupancy is missing or ambiguous in the imported document. |
| `perovskite_orthorhombic`, `mgfe60o` | The source filenames indicate solid solutions, but the imported formulas do not reliably encode their compositions or mixed-site occupancies. |
| `b4c` | Boron-carbide site occupancies depend on the polytype and carbon distribution; JCPDS/PDF 6-0555 and the cited 1934 phase paper do not define a modern, unique occupancy model. |

These blanks are deliberate. A plausible prototype with guessed coordinates
would produce plausible-looking but potentially wrong reflection intensities.
