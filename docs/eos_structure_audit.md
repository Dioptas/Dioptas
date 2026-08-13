# EoS material structure audit

Audit date: 2026-08-13.

This pass prepares the bundled EoS materials for a future Phase Smith
structure-factor calculation. A complete structure entry contains the
Hermann-Mauguin symbol, International Tables number, crystallographic `Z`,
and one occupied asymmetric-unit representative per Wyckoff site. The full
symmetry-expanded cell is deliberately not stored.

## Coverage

The database contains 87 material documents. Sixty-four now have complete
structure metadata and 23 remain intentionally unset. Every completed entry
passes an automated check that Wyckoff multiplicity times occupancy reproduces
the formula stoichiometry multiplied by `Z`.

The completed set is:

`alumina`, `aluminum`, `aragonite`, `argon_hcp`, `boron_nitride`, `ca_perovskite`,
`ca_perovskite_perovskite_pv`, `cao`, `cao_b2`, `casio3_perovskite`,
`chromium`, `cobalt_hcp`, `coesite`, `coo`, `copper`, `cscl`, `diamond`, `e_feooh`, `fe`, `fe2o3`, `fe3o4`,
`fe_fcc`, `feh3`, `feo`, `feo_b8`, `feo_b8_2`, `fes`, `fes_iii`, `geo2_rutile`, `goethite`,
`gold`, `graphite`, `indium_nitride`, `iridium`, `iron`, `kcl`, `li_bcc`, `magnesite`,
`mgo`, `molybdenum`, `molybenum_carbide_mo2c`, `naalsi2o6`, `naalsio4_calcium_ferrite`, `nacl_b1`, `nacl_b2`, `neon_fcc`, `nickel`, `nis`, `palladium`, `pbs_b1`,
`perovskite_cubic`, `platinum`, `rhenium`, `rhodium`, `ruthenium`, `silicon`, `silver`, `sio2_stv_andr`, `sno2`, `sro`,
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
| SiO2 coesite | C2/c (15) | Si 8f, Si 8f; O 4a, O 4e, O 8f, O 8f, O 8f | Levien and Prewitt, American Mineralogist 66, 324-333 (1981) |
| NaAlSi2O6 jadeite | C2/c (15) | Na 4e, Al 4e, Si 8f; O 8f, O 8f, O 8f | Prewitt and Burnham, American Mineralogist 51, 956-975 (1966) |
| NaAlSiO4 calcium ferrite | Pbnm (62) | Na 4c; two mixed Al/Si 4c sites; O 4c x4 | Yamada et al., Mineralogical Magazine 47, 177-181 (1983), doi:10.1180/minmag.1983.047.343.07; O4 correction from Finger and Hazen (1991), doi:10.1107/S0108768191004214 |
| FeS-III | P21/a (14) | Fe 4e x3; S 4e x3 | Nelmes et al., Physical Review B 59, 9048-9052 (1999), doi:10.1103/PhysRevB.59.9048 |
| FeS-VI | Pnma (62) | Fe 4c; S 4c | Ono et al., Earth and Planetary Science Letters 272, 481-487 (2008), doi:10.1016/j.epsl.2008.05.017 |
| Mo2C | Pbcn (60) | Mo 8d; C 4c | Chasvin et al., Molecular Catalysis 439, 163-170 (2017), doi:10.1016/j.mcat.2017.07.003 |
| epsilon-FeOOH | P21nm (31) | Fe 2a, O 2a x2, H 2a | 20 GPa static structure from Insixiengmay and Stixrude, American Mineralogist 108, 2209-2222 (2023), doi:10.2138/am-2022-8839 |

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
| `feh2`, `fe3s` | Hydrogen/iron-sulfide high-pressure structures need the experimental or calculated site table for the exact phase and pressure. |
| `iceviii`, `nitrogen_epsilon`, `o8` | Molecular positions and orientations cannot be reconstructed from lattice and powder peaks alone. |
| `majorite`, `mgsio3`, `mg7si2o8`, `phase_d` | Complex mantle phases; composition/site occupancy is missing or ambiguous in the imported document. |
| `perovskite_orthorhombic`, `mgfe60o` | The source filenames indicate solid solutions, but the imported formulas do not reliably encode their compositions or mixed-site occupancies. |
| `b4c` | Boron-carbide site occupancies depend on the polytype and carbon distribution; JCPDS/PDF 6-0555 and the cited 1934 phase paper do not define a modern, unique occupancy model. |

These blanks are deliberate. A plausible prototype with guessed coordinates
would produce plausible-looking but potentially wrong reflection intensities.
