# Equation-of-state database audit

This audit covers the 191 equation-of-state (EoS) records imported from the
beamline JCPDS collection in commit `710c3247`. JCPDS files are useful working
files, but their free-text references and parameter slots are not publication
metadata. Every import was therefore treated as unverified until its compound,
equation family, parameter convention, and reference could be reconciled.

Audit date: 2026-08-13.

## Corrected from publications

| Material | Stored EoS | V0 (A^3/cell) | K0 (GPa) | K0' | Source and correction |
|---|---:|---:|---:|---:|---|
| Aragonite | BM3 | 227.14 | 65.4 | 2.7 | Martinez et al. (1996), [doi:10.2138/am-1996-5-608](https://doi.org/10.2138/am-1996-5-608). The measured 298 K ambient cell volume is combined with the paper's global high-temperature BM3 fit; alpha0=6.7e-5 K^-1 and dK0/dT=-0.013 GPa/K are retained. Two conflicting imported V0 records were consolidated. |
| hcp Ar | BM2 | 47.7648 | 6.5 | 4 fixed | Wittlinger et al. (1997), [doi:10.1107/S0108768197005739](https://doi.org/10.1107/S0108768197005739). The publication reports K0=6.5(1.3) GPa but no fitted derivative, so the imported BM3 record was changed to BM2. |
| c-BN | Vinet | 47.2496 | 395.0 | 3.62 | Datchi et al. (2007), [doi:10.1103/PhysRevB.75.214104](https://doi.org/10.1103/PhysRevB.75.214104). The paper gives 5.9062 A^3/atom; the database stores the 8-atom conventional cell. The imported BM3/K0=500 alternative was removed. |
| Diamond | Vinet | 45.3864 | 443.0 | 3.97 | Datchi et al. (2007), Table II, using the H2005 pressure scale. The paper gives 5.6733 A^3/atom. The dummy record and imported K0=800 record were replaced. |
| epsilon-FeOOH | BM2 | 66.3 | 158.0 | 4 fixed | Gleason et al. (2008), [doi:10.2138/am.2008.2942](https://doi.org/10.2138/am.2008.2942). The import used the wrong V0 and labeled the second-order fit BM3. |
| FeH2 | Vinet | 67.8895 | 127.2 | 5.0 | Pepin et al. (2014), [doi:10.1103/PhysRevLett.113.265504](https://doi.org/10.1103/PhysRevLett.113.265504). The published 10.221 cm^3/mol was converted for the Z=4 cell. |
| FeH3 | Vinet | 18.5499 | 190.1 | 5.0 | Pepin et al. (2014), same source. The published 11.171 cm^3/mol was converted for the Z=1 cell; the import had K0=180.1 and the wrong equation family. |
| KCl B2 | BM3 | 53.53 | 23.7 | 4.4 | Walker et al. (2002), [doi:10.2138/am-2002-0701](https://doi.org/10.2138/am-2002-0701). The volumetric alpha0 was corrected from 4.26e-5 to 1.8e-4 K^-1. |
| Magnesite | BM3 | 279.28 | 117.0 | 2.3 | Ross (1997), [doi:10.2138/am-1997-7-805](https://doi.org/10.2138/am-1997-7-805). Three imported records with conflicting V0 values were replaced by the publication fit. |
| MgO | BM3 | 74.71 | 160.2 | 3.99 | Speziale et al. (2001), [doi:10.1029/2000JB900318](https://doi.org/10.1029/2000JB900318). The unsupported constant-alpha approximation was removed. |
| Fe-bearing phase D | BM2 | 84.7321 | 134.0 | 4 fixed | Shieh et al. (2000), [doi:10.1016/S0012-821X(00)00033-9](https://doi.org/10.1016/S0012-821X(00)00033-9). The paper explicitly uses a second-order fit; the imported K0'=4.3 was removed. |
| W | Vinet | 31.724 | 295.2 | 4.32 | Dewaele et al. (2004), [doi:10.1103/PhysRevB.70.094112](https://doi.org/10.1103/PhysRevB.70.094112). The paper gives 15.862 A^3/atom. The import cited the wrong year, equation family, and fit parameters. |
| Zircon | BM2 | 260.803 | 227.0 | 4 fixed | Hazen and Finger (1979), American Mineralogist 64, 196-201. The paper reports K0=227(2) GPa; the unsupported imported K0'=6.5 was removed. |

The references for standard-cell Co (hcp), goethite, NaCl B2, PbS B1,
stishovite, and tantalum were also expanded to full citations/DOIs after their
static parameters were checked.
Generic thermal coefficients copied into PbS B1 and ten unrelated imported
records were removed; those records now represent only their cited static EoS.

## Citation normalization

Every retained citation was reconciled against publisher or DOI metadata and
rewritten as `Authors, Journal volume, pages (year), doi:...`. Of the 76
retained records, 74 now include a DOI. The two exceptions are the 1979 zircon
and 1981 coesite papers in American Mineralogist; both have complete
author/volume/page/year metadata, but no registered DOI was found.

This pass also corrected a material identity: `naalsi2o6_2.json` came from
files explicitly named `NaAlSiO4 CaF phase` and cites the calcium-ferrite-type
NaAlSiO4 paper. It is now `naalsio4_calcium_ferrite.json`, with formula
NaAlSiO4 and Z=4, rather than being mislabeled as jadeite NaAlSi2O6.

## Removed EoS records

Of the 220 EoS records in the post-import database, 144 were removed, leaving
76 publication-supported EoS records. Material entries left with neither an
EoS nor an independent phase reference were then removed as well. The final
database contains 76 materials: 68 with EoS data and eight phase-only entries
identified by explicit JCPDS/PDF card numbers in their material notes.

The removed records fall into four reproducible categories:

- Explicit placeholders: references containing `guess`, `unknown`, `n/a`,
  `estimated`, `need found`, or `EOS from ?`.
- Wrong-material transplants: for example Fe-bcc parameters attached to FeP,
  CoO parameters attached to Co2O3/Co3O4, FeO-B8 parameters attached to PbF2,
  magnesite parameters attached to siderite, and a jadeite EoS attached to
  NaAlSi3O8 hollandite.
- Irreconcilable alternatives: arbitrary parameter series under one citation
  (fcc Fe and NaMgF3), duplicate values with no way to identify the publication
  fit, and the orthorhombic PbS transition-referenced fit that the current
  zero-pressure EoS schema cannot represent.
- Powder-card or structure-only provenance: a JCPDS/PDF card or a crystal
  structure paper was the only reference, with no traceable source for K0 and
  K0'. This includes the Cd-Sb and Fe-C phase groups and several elemental
  entries. The citation-normalization pass additionally removed structure-only
  records for helium, methane hydrate, forsterite, NiO, SiC, and TiB2.
- Non-public provenance: private communications, personal-name shorthand,
  `dcal` calculations, and locally fitted values attributed only to a beamline
  user were removed even when the numbers looked physically plausible.
- Unpublished alternatives under a real citation: a beamline BM3 refit of the
  published Fei gold Vinet scale and an internally volume-inconsistent hcp-iron
  alternative were removed while their publication-supported counterparts
  were retained.
- Material/composition mismatches found while resolving citations: Mg2SiO4
  entries citing the (Mg,Fe)SiO3 perovskite paper, pure siderite citing a
  magnesian-siderite experiment, and an unidentified FeGeO3 entry were removed.

The imported `TiBr` file was deleted because its source, lattice, and card all
identify TiB2. Two files labeled as molybdenum were identified as `MoC
(Fm-3m)` and `Mo2C (hexagonal)` from their source filenames; after their
molybdenum-metal EoS records were rejected, the now-unreferenced material
entries were removed too.

## Retention rule

Absence of an EoS is preferable to a plausible-looking but untraceable pressure
compound/phase, equation form, V0 convention, K0, and any fitted derivatives.
A phase-only material is retained only when its notes contain an independent
phase reference, such as a JCPDS/PDF card number.
