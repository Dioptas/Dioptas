# Assumed diffraction models for tetragonal CaSiO3

The EOS browser offers **Use assumed tetragonal perovskite structure** for
the two tetragonal CaSiO3 entries that have no diffraction data. Checking it
enables **Load as Phase** for validated EOS records. Unchecking it restores
the original material. Selecting another material resets the option.

The approximation is constructed on a copy in Dioptas; the Peritheos catalog
and published EOS dictionaries are unchanged. The loaded phase name and
comments identify the assumed structure. Its assumptions, seed references,
and original structural metadata survive `.eosmat` export and `.dio` project
save/load in `source.assumed_structure`. Exporting with the option checked
includes the assumed model.

## Models and volume conventions

- `casio3_perovskite_tetragonal`: an ideal P4/mmm perovskite pseudocell with
  one CaSiO3 formula unit, Ca at (0,0,0), Si at (1/2,1/2,1/2), apical O at
  (1/2,1/2,0), and an equatorial O representative at (1/2,0,1/2). The fixed
  c/a=0.996 approximates the 0.4% c-axis contraction described in
  [Shim et al. (2002), paragraph 9 and Figure 2](https://duffy.princeton.edu/document/129).
  P4/mmm is an assumed diffraction model; the source's unresolved unique
  space-group assignment remains recorded in the original metadata.
- `ca_perovskite_tetragonal`: an I4/mcm perovskite model with four formula
  units. The shape c/a=6.9677/4.8896 and an 8-degree tilt are seeded from
  [Chen et al. (2018), Table 1, first I4/mcm row at 28.824 GPa](https://doi.org/10.2138/am-2018-6087).
  Ca occupies (0,1/2,1/4), Si (0,0,0), apical O (0,0,1/4), and equatorial
  O (x,x+1/2,0), with x=(1-tan(8 degrees))/4. These coordinates are
  constructed from perovskite geometry, rather than transcribed as refined
  coordinates. The prototype uses the conventional a0a0c-minus tilt topology.

For each selected EOS, a=(V0/(c/a))^(1/3), b=a, and c=a*(c/a). Thus a^2*c
equals that record's reference volume, including after reference switching.
PhaseSmith generates hkl and approximate intensities from the assumed model;
Dioptas moves the reflections with the selected EOS volume. Cell shape and
fractional coordinates remain fixed with pressure and temperature. This
provides approximate phase-identification lines, without modelling evolving
distortion, phase transitions, or a refined intensity pattern.

Tests cover symmetry-expanded stoichiometry, systematic absences, tetragonal
peak splitting, all seven EOS choices and volume conventions, reference
switching, export, project persistence, and extension of reflection coverage.
