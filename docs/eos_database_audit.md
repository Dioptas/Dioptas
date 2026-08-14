# Equation-of-state database audit

This audit covers the 191 equation-of-state (EoS) records imported from the
beamline JCPDS collection in commit `710c3247`. JCPDS files are useful working
files, but their free-text references and parameter slots are not publication
metadata. Every import was therefore treated as unverified until its compound,
equation family, parameter convention, and reference could be reconciled.

Audit date: 2026-08-14.

## Experimental pressure-domain audit

Every EoS record now reports the pressure domain of the measurements used to
constrain that particular fit.  The interval is stored as
`experimental_pressure_range_gpa`; it is deliberately not a phase-stability
range.  All limits were checked against the cited primary publication's data
tables, figures, full text, or publisher abstract.  Phase-specific limits were
used where a paper spans a transition: for example CaO-B1 is 0--60 GPa while
CaO-B2 is 52.7--134.9 GPa, and the four high-pressure silicon polymorphs each
carry their own observed interval.

The legacy Pt and W records are dynamic-compression exceptions.  The Holmes
Pt model is tied to the 32--660 GPa shock data, while the Hixson--Fritz W
record is limited to the 0--380 GPa reduced-isotherm table derived from their
shock measurements.  These are not presented as static DAC fit ranges.

Sixteen records have no defensible numeric experimental interval and instead use
an explicit `pressure_range_status`: the Munoz--Kunc InN EoS is theoretical;
the Fei FeO and Anderson Au values are reference/compilation
parameterizations rather than fits to one bounded data set; the B1-ZnO paper
does not tabulate the exact fit interval; and the 1966 CoO
source reports its upper limit only qualitatively as "several hundred
kilobars" in the recoverable publication metadata. The eleven Sokolova et al.
thermal calibrants are likewise reference parameterizations, not fits to one
experimental pressure interval. The database UI displays
these statuses instead of leaving the fit-range column blank or inventing a
number.  A regression test requires every current and future EoS record to
contain exactly one of a numeric interval or an approved explicit status.

## Corrected from publications

| Material | Stored EoS | V0 (A^3/cell) | K0 (GPa) | K0' | Source and correction |
|---|---:|---:|---:|---:|---|
| Aragonite | BM3 | 227.14 | 65.4 | 2.7 | Martinez et al. (1996), [doi:10.2138/am-1996-5-608](https://doi.org/10.2138/am-1996-5-608). The measured 298 K ambient cell volume is combined with the paper's global high-temperature BM3 fit; alpha0=6.7e-5 K^-1 and dK0/dT=-0.013 GPa/K are retained. Two conflicting imported V0 records were consolidated. |
| hcp Ar | BM2 | 47.7648 | 6.5 | 4 fixed | Wittlinger et al. (1997), [doi:10.1107/S0108768197005739](https://doi.org/10.1107/S0108768197005739). The publication reports K0=6.5(1.3) GPa but no fitted derivative, so the imported BM3 record was changed to BM2. |
| c-BN | Vinet | 47.2496 | 395.0 | 3.62 | Datchi et al. (2007), [doi:10.1103/PhysRevB.75.214104](https://doi.org/10.1103/PhysRevB.75.214104). The paper gives 5.9062 A^3/atom; the database stores the 8-atom conventional cell. The imported BM3/K0=500 alternative was removed. |
| Diamond | Vinet | 45.3864 | 443.0 | 3.97 | Datchi et al. (2007), Table II, using the H2005 pressure scale. The paper gives 5.6733 A^3/atom. The dummy record and imported K0=800 record were replaced. |
| Diamond | Vinet | 45.3544 | 444.5 | 4.18 | Dewaele et al. (2008), [doi:10.1103/PhysRevB.77.094106](https://doi.org/10.1103/PhysRevB.77.094106). Independent 298 K single-crystal XRD in neon to 80 GPa; the fixed-K0 fit gives 5.6693 A^3/atom. |
| Graphite | Murnaghan | 35.12 | 33.8 | 8.9 | Hanfland et al. (1989), [doi:10.1103/PhysRevB.39.12598](https://doi.org/10.1103/PhysRevB.39.12598). The 300 K powder-XRD fit is phase-limited to below the transformation near 14 GPa. |
| epsilon-FeOOH | BM2 | 66.3 | 158.0 | 4 fixed | Gleason et al. (2008), [doi:10.2138/am.2008.2942](https://doi.org/10.2138/am.2008.2942). The import used the wrong V0 and labeled the second-order fit BM3. |
| FeH2 | Vinet | 67.8895 | 127.2 | 5.0 | Pepin et al. (2014), [doi:10.1103/PhysRevLett.113.265504](https://doi.org/10.1103/PhysRevLett.113.265504). The published 10.221 cm^3/mol was converted for the Z=4 cell. |
| FeH3 | Vinet | 18.5499 | 190.1 | 5.0 | Pepin et al. (2014), same source. The published 11.171 cm^3/mol was converted for the Z=1 cell; the import had K0=180.1 and the wrong equation family. |
| KCl B2 | BM3 | 53.53 | 23.7 | 4.4 | Walker et al. (2002), [doi:10.2138/am-2002-0701](https://doi.org/10.2138/am-2002-0701). The volumetric alpha0 was corrected from 4.26e-5 to 1.8e-4 K^-1. |
| Magnesite | BM3 | 279.28 | 117.0 | 2.3 | Ross (1997), [doi:10.2138/am-1997-7-805](https://doi.org/10.2138/am-1997-7-805). Three imported records with conflicting V0 values were replaced by the publication fit. |
| MgO | BM3 | 74.71 | 160.2 | 3.99 | Speziale et al. (2001), [doi:10.1029/2000JB900318](https://doi.org/10.1029/2000JB900318). The unsupported constant-alpha approximation was removed. |
| Rhenium | Vinet | 29.4666 | 352.6 | 4.56 | Anzellini et al. (2014), [doi:10.1063/1.4863300](https://doi.org/10.1063/1.4863300). Quasi-hydrostatic helium-medium XRD to 144 GPa; 8.8726 cm^3/mol was converted to the two-atom hcp cell. |
| Fe-bearing phase D | BM2 | 84.7321 | 134.0 | 4 fixed | Shieh et al. (2000), [doi:10.1016/S0012-821X(00)00033-9](https://doi.org/10.1016/S0012-821X(00)00033-9). The paper explicitly uses a second-order fit; the imported K0'=4.3 was removed. |
| W | Vinet | 31.724 | 295.2 | 4.32 | Dewaele et al. (2004), [doi:10.1103/PhysRevB.70.094112](https://doi.org/10.1103/PhysRevB.70.094112). The paper gives 15.862 A^3/atom. The import cited the wrong year, equation family, and fit parameters. |
| Zircon | BM2 | 260.803 | 227.0 | 4 fixed | Hazen and Finger (1979), American Mineralogist 64, 196-201. The paper reports K0=227(2) GPa; the unsupported imported K0'=6.5 was removed. |

The references for standard-cell Co (hcp), goethite, NaCl B2, PbS B1,
stishovite, and tantalum were also expanded to full citations/DOIs after their
static parameters were checked.
Generic thermal coefficients copied into PbS B1 and ten unrelated imported
records were removed; those records now represent only their cited static EoS.

## Shen and Smith 2026 extension

Table II of Shen and Smith, *Physical Review B* 113, 144113 (2026),
[doi:10.1103/fxgq-96sg](https://doi.org/10.1103/fxgq-96sg), was checked against
the complete paper supplied by the user. Ten Cu-referenced 300 K Vinet fits
were added as alternative records: Pt, Au, Ta, W, Mo, MgO, NaCl-B1, NaCl-B2,
bcc-Fe, and hcp-Fe. All stored V0 values are the crystallographic unit-cell
volumes printed in Table II, not the atomic or formula-unit volumes used in
Table I. The publication uncertainties, fixed-V0 status, run selection, and
phase-specific pressure limits are retained in each record's notes.

Molybdenum and NaCl-B1 were new material documents. Their phase identification
uses JCPDS 42-1120 and JCPDS 5-0628, respectively. The latter is also the
ambient-volume source explicitly identified by Shen and Smith. Copper was
not added from this paper: it is the primary pressure anchor, and its EOS
parameters are taken from another publication and explicitly not repeated in
Table II.

The eleven calibrant phases, including reference Cu, also store their
Hermann-Mauguin space group, International Tables number, and occupied
asymmetric-unit Wyckoff sites. Each site contains the element, fractional
coordinates, Wyckoff multiplicity/letter, and occupancy. PhaseSmith now uses
this representation for the phase lines; symmetry-equivalent atoms and the
derived reflection tables are deliberately not duplicated in the material
documents.

A subsequent database-wide structure pass extended this representation to 55
of the original 78 materials. Later literature additions and source-specific
refinements and the latest literature additions raised current coverage to 107
of 120 materials. The 13 remaining
complex, disordered, molecular, or ambiguously identified phases are listed
with their blocking reason in `docs/eos_structure_audit.md`; no atomic
coordinates were guessed for them.

## Literature expansion beyond the JCPDS import

Nine material documents absent from the imported collection were added from
primary high-pressure diffraction studies: fcc Al, Ag, Ni, Rh, Pd, and Ir;
bcc Cr; hcp Ru; and diamond-cubic Si-I. Each document contains a complete
asymmetric-unit structure, a reference cell consistent with its fitted V0,
a PhaseSmith-ready structure, and at least one experimental room-temperature
EoS.

The Al parameters are the revised-ruby Vinet fit of Dewaele et al. (2004),
[doi:10.1103/PhysRevB.70.094112](https://doi.org/10.1103/PhysRevB.70.094112).
Ag and Ni use the helium-medium Vinet fits of Dewaele et al. (2008),
[doi:10.1103/PhysRevB.78.104102](https://doi.org/10.1103/PhysRevB.78.104102).
The other additions use Anzellini et al. for Cr, Ru, Ir, and Si-I;
Rodrigo-Ramon et al. for Rh; and Baty et al. for Pd. Atomic reference volumes
printed for fcc or diamond cells were converted to conventional-cell V0.

## Pressure-marker and binary-compound extension

Seven additional phase documents were added from four experimental studies
and one openly archived pressure-marker report. Each has a complete ideal or
measured asymmetric-unit structure, PhaseSmith-calculated reflections, parameter
errors (or an explicit statement that the paper tabulates none), and the
pressure interval used for the fit.

| Phase | Stored EoS | V0 (A^3/cell) | K0 (GPa) | K0' | Experimental domain and source |
|---|---:|---:|---:|---:|---|
| LiF B1 | Vinet | 65.484 | 64.6(1.4) | 4.62(60) | 0--109 GPa; Dewaele (2019), [doi:10.3390/min9110684](https://doi.org/10.3390/min9110684). The Mao-scale column is used because it provides explicit 95% confidence intervals. |
| KBr B1 | Vinet | 287.56 | 14.2 | 5.5 fixed | 0--2.3 GPa; Dewaele et al. (2012), [doi:10.1103/PhysRevB.85.214105](https://doi.org/10.1103/PhysRevB.85.214105). |
| KBr B2 | Vinet | 63.4 fixed | 14.9 | 5.81 | 2.3--165 GPa; same source. B1 and B2 are separate phase documents because their cells, reflection conditions, stability ranges, and EoS parameterizations differ. |
| cubic BP | Vinet | 93.2061 fixed | 179(1) | 3.3(1) | 0--55 GPa; Le Godec et al. (2014), [doi:10.3103/S1063457614010092](https://doi.org/10.3103/S1063457614010092). |
| CeO2 fluorite | BM3 | 158.428242 | 220(9) | 4.4(4) | 0--20 GPa; Gerward et al. (2005), [doi:10.1016/j.jallcom.2005.04.008](https://doi.org/10.1016/j.jallcom.2005.04.008). |
| PrO2 fluorite | BM3 | 156.939703 | 187(8) | 4.8(5) | 0--35 GPa; same source. |
| Pb fcc | BM4 | 121.418(5) | 41.73(1) | 5.39(25) | 0--13 GPa, compression data at 295--788 K; Fortes, RAL-TR-2019-002 (2019). The database stores the 300 K slice, including K0''=-0.33(2) GPa^-1, because the source's polynomial temperature model is not representable by the present thermal schema. |

## Native Sokolova thermal calibrants

The eleven original Excel supplements to Sokolova, Dorogokupets, and Litasov,
*Computers & Geosciences* 94, 162--169 (2016),
[doi:10.1016/j.cageo.2016.06.002](https://doi.org/10.1016/j.cageo.2016.06.002),
were transcribed directly for Ag, Al, Au, diamond, Cu, MgO, Mo, Nb, Pt, Ta,
and W. These are native `Sokolova2016` thermal models composed with the
publication's Holzapfel room-temperature EoS, not McHardy or other later
refits. Workbook `Vo` values in J bar^-1 mol^-1 were converted to conventional
cell A^3 using each phase's crystallographic Z; workbook `Ko` values were
converted from kbar to GPa. All eleven full coefficient dictionaries survive
material loading and project save/load. The supplements do not report
individual parameter uncertainties, so every corresponding error is
explicitly `null` rather than zero.

The implementation was cross-checked against all 304 cached P--V--T rows in
the eleven original workbooks (up to 4000 K where supplied), with a maximum
relative volume difference of 1.54e-6. A separate literal port of the embedded
`xAP2` VBA routine agrees with Peritheos at 400 GPa and 3000 K to within
1.6e-5 A^3 for every material. These high-temperature reference points are
locked by regression tests.

## Additional phase-resolved EoS records

Fourteen further phase documents were added from primary publications. Each
has its own structure and fit domain: hcp and bcc Mg; alpha and omega Ti;
akimotoite and orthoenstatite MgSiO3; CaCl2-type silica and seifertite; pyrope
and almandine garnet; fayalite; hcp Os; alpha-Mn; and B1 KCl. KCl B1 and B2
are now explicitly named as separate material records, matching the existing
phase-per-polymorph treatment of CaO and KBr. Source-reported parameter errors
and fixed parameters are retained; absent published errors are stored as
`null`.

## ZnO, Zr, oxide, carbide, and carbonate extension

Nine phase documents and ten EoS records were added from primary literature:
wurtzite/B4 and rocksalt/B1 ZnO; alpha, omega, and beta Zr; rhombohedral NiO;
cementite Fe3C; orthorhombic Fe7C3; and post-aragonite CaCO3-Pmmn. Each phase
has an explicit crystallographic model and conventional-cell V0. The
post-aragonite document contains both the 300 K static BM3 fit and the paired
BM3--Mie-Gruneisen-Debye fit to 2200 K. Equivalent imported CaSiO3-perovskite
and FeO-B8 documents were consolidated rather than retained under ambiguous
duplicate names.

## Citation normalization

Every retained citation was reconciled against publisher or DOI metadata and
rewritten as `Authors, Journal volume, pages (year), doi:...`. Of the 147
current records, 144 include a DOI. The exceptions are the 1979 zircon and
1981 coesite papers in American Mineralogist, for which no registered DOI was
found, and the citable STFC report for fcc Pb. The Pb record includes the
open primary-report URL in its notes.

This pass also corrected a material identity: `naalsi2o6_2.json` came from
files explicitly named `NaAlSiO4 CaF phase` and cites the calcium-ferrite-type
NaAlSiO4 paper. It is now `naalsio4_calcium_ferrite.json`, with formula
NaAlSiO4 and Z=4, rather than being mislabeled as jadeite NaAlSi2O6.

## Removed EoS records

Of the 220 EoS records in the post-import database, 144 were removed, leaving
76 publication-supported EoS records at the end of the initial audit. Material
entries left with neither an EoS nor an independent phase reference were then
removed as well. After the Shen and Smith extension, the database contains 78
materials and 86 EoS records: 71 materials with EoS data and seven phase-only
entries identified by explicit JCPDS/PDF card numbers in their material notes.

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
entries were removed too. The subsequent literature expansions and
pressure-domain audit, native Sokolova parameterizations, and subsequent
phase expansion bring the current database to 120 materials and 147 EoS
records: 116 materials with EoS data and four phase-only entries.

## Retention rule

Absence of an EoS is preferable to a plausible-looking but untraceable pressure
compound/phase, equation form, V0 convention, K0, and any fitted derivatives.
A phase-only material is retained only when its notes contain an independent
phase reference, such as a JCPDS/PDF card number.
