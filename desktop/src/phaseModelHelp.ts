export type ModelHelp = {
  title: string;
  description: string;
  url: string;
  equations?: { text: string; math: string }[];
  note?: string;
};
export const peritheosManual = "https://peritheos.readthedocs.io/en/latest/";
const equationUrl = (anchor: string) =>
  `${peritheosManual}equation-reference/#${anchor}`;
const escape = (s: string) =>
  s.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;");
const tag = (name: string, ...children: string[]) =>
  `<${name}>${children.join("")}</${name}>`;
const mi = (s: string) => tag("mi", escape(s));
const mo = (s: string) => tag("mo", escape(s));
const mn = (s: number) => tag("mn", String(s));
const row = (...s: string[]) => tag("mrow", ...s);
const sub = (s: string, n: string) => tag("msub", mi(s), mi(n));
const power = (s: string, n: string) => tag("msup", s, n);
const fraction = (a: string, b: string) => tag("mfrac", a, b);
const parens = (...s: string[]) => row(mo("("), ...s, mo(")"));
const brackets = (...s: string[]) => row(mo("["), ...s, mo("]"));
const exp = (...s: string[]) => row(mi("exp"), brackets(...s));
const eq = (text: string, ...s: string[]) => ({
  text,
  math: `<math xmlns="http://www.w3.org/1998/Math/MathML" display="block" aria-label="${escape(text)}">${row(...s)}</math>`,
});
const gamma0 = sub("γ", "0"),
  theta0 = sub("Θ", "0"),
  alpha0 = sub("α", "0"),
  alpha1 = sub("α", "1"),
  tr = sub("T", "r");
const x = mi("x"),
  q = mi("q"),
  dt = row(mi("Δ"), mi("T"));
const gamma = row(mi("γ"), parens(mi("V")));
const theta = row(mi("Θ"), parens(mi("V")));
const v0t = row(sub("V", "0"), parens(mi("T")));
const v0r = row(sub("V", "0"), parens(tr));
const k0t = row(sub("K", "0"), parens(mi("T")));
const k0r = row(sub("K", "0"), parens(tr));
const gammaEquation = eq("γ(V) = γ₀ x^q", gamma, mo("="), gamma0, power(x, q));
const volumeDefinition =
  "x = V/V₀; Θ is the characteristic lattice temperature (K), Θ₀ its value at V₀, and γ₀ and q are dimensionless.";
const thermalReference = "thermal-pressure-and-its-reference-state";
const referenceState = "temperature-dependent-reference-state";

const eosDescriptions: Record<string, [string, string]> = {
  BM2: [
    "birch-murnaghan-family",
    "Second-order Birch–Murnaghan finite strain; K₀′ is fixed at 4.",
  ],
  BM2Reference: [
    "finite-pressure-bm2-reference",
    "BM2 with a finite reference pressure P₀. V₀ and K₀ refer to P₀ rather than ambient pressure.",
  ],
  BM3: [
    "birch-murnaghan-family",
    "Third-order Birch–Murnaghan finite strain, with adjustable K₀′.",
  ],
  BM4: [
    "birch-murnaghan-family",
    "Fourth-order Birch–Murnaghan, including the curvature parameter K₀″.",
  ],
  Murnaghan: [
    "murnaghan",
    "Assumes the bulk modulus varies linearly with pressure: K(P) = K₀ + K₀′P.",
  ],
  Vinet: [
    "vinet",
    "Pressure–volume relation based on an interatomic-potential form.",
  ],
  ModifiedTait: [
    "modified-tait",
    "Analytically invertible modified Tait equation.",
  ],
  NaturalStrain2: [
    "natural-strain-family",
    "Second-order logarithmic strain; K₀′ is fixed at 2.",
  ],
  NaturalStrain3: [
    "natural-strain-family",
    "Third-order Poirier–Tarantola logarithmic strain.",
  ],
  NaturalStrain4: [
    "natural-strain-family",
    "Fourth-order logarithmic strain with K₀″.",
  ],
  Holzapfel: [
    "holzapfel",
    "High-compression equation with electron-count and molar-volume conventions.",
  ],
};
const thermalDescriptions: Record<string, [string, string]> = {
  none: [
    "thermal-equations",
    "Uses the reference EoS without a thermal correction.",
  ],
  alphakt: [
    referenceState,
    "Legacy Dioptas expansion and temperature-dependent elastic coefficients. These coefficients retain their legacy convention.",
  ],
  AlphaKT: [
    referenceState,
    "Shifts the reference volume and elastic parameters with temperature, using the laws selected below.",
  ],
  MieGruneisenDebye: [
    "mie-gruneisen-debye-and-einstein",
    "Debye vibrational energy produces thermal pressure through γ(V). The temperature law and pressure reference below are part of the model definition.",
  ],
  MieGruneisenEinstein: [
    "einstein-alternative",
    "Uses an Einstein oscillator with the integrated Grüneisen temperature law.",
  ],
  Sokolova2016: [
    "multi-oscillator-gruneisen-thermal-pressure",
    "Multi-oscillator Grüneisen model. This compatibility name follows the source workbook formulation; see the paper-versus-spreadsheet notes.",
  ],
  MultiOscillatorGruneisen: [
    "multi-oscillator-gruneisen-thermal-pressure",
    "Multiple vibrational modes with Grüneisen, anharmonic and electronic terms. The manual explains the source-workbook convention.",
  ],
  DoubleDebyeHelmholtz: [
    "double-debye-helmholtz",
    "Two Debye spectra constrained by an arithmetic phonon moment, with optional T² free-energy terms. Tr determines whether the thermal contribution is absolute or referenced.",
  ],
  DoubleDebyeLogMomentHelmholtz: [
    "logarithmic-moment-double-debye-variant",
    "Two Debye spectra constrained by a logarithmic phonon moment; distinct from the arithmetic-moment model.",
  ],
  ThermalModifiedTait: [
    "thermal-modified-tait",
    "Holland–Powell Einstein thermal pressure composed with a Modified Tait reference EoS.",
  ],
  HollandPowellThermalPressure: [
    "holland-powell-thermal-pressure",
    "Volume-independent Holland–Powell Einstein thermal pressure, referenced to Tr.",
  ],
  LinearThermalPressure: [
    "linear-thermal-pressure",
    "Adds αKₜ(T − Tr); αKₜ is one fitted product in GPa/K.",
  ],
  LogVolumeThermalPressure: [
    "logarithmic-volume-linear-thermal-pressure",
    "Linear thermal pressure whose temperature slope varies with ln(V₀/V).",
  ],
  SecondOrderTaylorThermalPressure: [
    "second-order-temperature-compression-thermal-pressure",
    "Adds an absolute second-order pressure polynomial to a cold curve. Tr is an expansion coordinate, not the reference-isotherm temperature.",
  ],
  AsymptoticPowerLawMieGruneisenDebye: [
    "tange-2009-mgo-thermal-model",
    "Tange volume dependence for γ and Θ, rather than a constant-q power law.",
  ],
  AsymptoticPowerLawMieGruneisenDebyeExcess: [
    "asymptotic-power-law-debye-with-t2-excess",
    "Tange Debye model with a volume-dependent T² excess term; both contributions are referenced to Tr.",
  ],
  Dewaele2006: [
    "dewaele-2006-hcp-fe-thermal-pressure-scale",
    "Volume-dependent Debye, anharmonic and electronic thermal-pressure terms, using the selected pressure reference.",
  ],
  DorogokupetsOganov2007: [
    "dorogokupets-oganov-2007-four-oscillator-model",
    "Complete four-oscillator Helmholtz formulation with anharmonic, electronic and defect terms.",
  ],
  DebyeQuadraticThermalPressure: [
    "debye-plus-quadratic-thermal-pressure",
    "Integrated-law Debye thermal pressure plus A(V/V₀)^m(T² − Tr²). This pressure model does not define caloric observables.",
  ],
  SoundVelocityDebyeHelmholtz: [
    "sound-velocity-quasi-debye-helmholtz-eos",
    "Derives the Debye temperature from longitudinal and shear sound velocities and density.",
  ],
};
export function modelHelp(kind: "eos" | "thermal", name: string): ModelHelp {
  const [anchor, description] = (kind === "eos"
    ? eosDescriptions
    : thermalDescriptions)[name] ?? [
    kind === "eos" ? "isothermal-equations" : "thermal-equations",
    "See the model definition, reference-state conventions and parameter units in the manual.",
  ];
  return {
    title:
      name === "none"
        ? "No thermal model"
        : name === "alphakt"
          ? "Legacy thermal correction"
          : name,
    description,
    url: equationUrl(anchor),
  };
}

export function choiceHelp(
  key: string,
  value: string,
  referenceVolumeLaw = "integrated_expansivity",
): ModelHelp | null {
  const help = (
    title: string,
    description: string,
    anchor: string,
    equations: ModelHelp["equations"],
    note?: string,
  ): ModelHelp => ({
    title,
    description,
    url: equationUrl(anchor),
    equations,
    note,
  });
  if (key === "debye_temperature_law") {
    if (value === "integrated_gruneisen")
      return help(
        "Integrated Grüneisen law",
        "Integrates γ(V) = −d ln Θ/d ln V. This is the default Debye temperature law.",
        "gruneisen-parameter-and-debye-temperature",
        [
          gammaEquation,
          eq(
            "Θ(V) = Θ₀ exp[−γ₀(x^q − 1)/q]",
            theta,
            mo("="),
            theta0,
            exp(
              mo("−"),
              fraction(gamma0, q),
              parens(power(x, q), mo("−"), mn(1)),
            ),
          ),
          eq(
            "q = 0: Θ(V) = Θ₀ x^(−γ₀)",
            q,
            mo("="),
            mn(0),
            mo(":"),
            theta,
            mo("="),
            theta0,
            power(x, row(mo("−"), gamma0)),
          ),
        ],
        `${volumeDefinition} The exponential form is for q ≠ 0; q = 0 uses the continuous limit shown.`,
      );
    if (value === "variable_exponent")
      return help(
        "Variable-exponent law",
        "Uses the Fei-style variable exponent directly, rather than integrating γ(V).",
        "variable-exponent-debye-temperature-law",
        [
          gammaEquation,
          eq(
            "Θ(V) = Θ₀ x^(−γ(V))",
            theta,
            mo("="),
            theta0,
            power(x, row(mo("−"), gamma)),
          ),
          eq(
            "−d ln Θ/d ln V = γ(V)[1 + q ln x]",
            mo("−"),
            fraction(
              row(mi("d"), mi("ln"), mi("Θ")),
              row(mi("d"), mi("ln"), mi("V")),
            ),
            mo("="),
            gamma,
            brackets(mn(1), mo("+"), q, mi("ln"), x),
          ),
        ],
        `${volumeDefinition} For q ≠ 0 away from V₀, γ used in pressure is not the logarithmic derivative of Θ. The two laws coincide at V₀ or when q = 0.`,
      );
  }
  if (key === "thermal_expansion_law") {
    if (referenceVolumeLaw !== "integrated_expansivity")
      return help(
        "Expansion coefficients in the volume law",
        "The selected reference-volume law controls V₀(T) directly. α₀ and α₁ refer to that relation; the standalone expansivity formula is not applied.",
        referenceState,
        undefined,
        "Use the equation under Reference volume law below.",
      );
    const alpha = row(mi("α"), parens(mi("T")));
    if (value === "constant")
      return help(
        "Constant expansivity",
        "The volumetric expansion coefficient is constant.",
        referenceState,
        [eq("α(T) = α₀", alpha, mo("="), alpha0)],
      );
    if (value === "linear_temperature")
      return help(
        "Linear in absolute temperature",
        "α₀ is the intercept at T = 0, rather than the value at Tr.",
        referenceState,
        [
          eq(
            "α(T) = α₀ + α₁T",
            alpha,
            mo("="),
            alpha0,
            mo("+"),
            alpha1,
            mi("T"),
          ),
        ],
      );
    if (value === "linear_reference_temperature")
      return help(
        "Linear from reference temperature",
        "α₀ is the volumetric expansivity at Tr.",
        referenceState,
        [
          eq(
            "α(T) = α₀ + α₁(T − Tr)",
            alpha,
            mo("="),
            alpha0,
            mo("+"),
            alpha1,
            parens(mi("T"), mo("−"), tr),
          ),
        ],
      );
  }
  if (key === "reference_volume_law") {
    if (value === "integrated_expansivity")
      return help(
        "Integrated expansivity",
        "Integrates the expansion law selected above.",
        referenceState,
        [
          eq(
            "V₀(T) = V₀(Tr) exp[∫ from Tr to T α(T′) dT′]",
            v0t,
            mo("="),
            v0r,
            exp(
              tag("msubsup", mo("∫"), tr, mi("T")),
              mi("α"),
              parens(mi("T′")),
              mi("dT′"),
            ),
          ),
        ],
      );
    if (value === "linear_temperature")
      return help(
        "Linear reference volume",
        "Direct volume relation. α₀ is the mean expansion coefficient in this relation.",
        referenceState,
        [
          eq(
            "V₀(T) = V₀(Tr)[1 + α₀ΔT]",
            v0t,
            mo("="),
            v0r,
            brackets(mn(1), mo("+"), alpha0, dt),
          ),
        ],
        "ΔT = T − Tr; this is not the exponential integral of constant expansivity.",
      );
    if (value === "berman")
      return help(
        "Berman reference volume",
        "Truncated polynomial expansion with α₀ defined at Tr. This choice requires the expansion setting linear temperature.",
        referenceState,
        [
          eq(
            "V₀(T) = V₀(Tr)[1 + α₀ΔT + α₁ΔT²/2]",
            v0t,
            mo("="),
            v0r,
            brackets(
              mn(1),
              mo("+"),
              alpha0,
              dt,
              mo("+"),
              fraction(alpha1, mn(2)),
              power(dt, mn(2)),
            ),
          ),
        ],
        "ΔT = T − Tr.",
      );
  }
  if (key === "bulk_modulus_law") {
    if (value === "linear_temperature")
      return help(
        "Linear bulk modulus",
        "Shifts the reference bulk modulus using its temperature slope.",
        referenceState,
        [
          eq(
            "K₀(T) = K₀(Tr) + (dK₀/dT)ΔT",
            k0t,
            mo("="),
            k0r,
            mo("+"),
            fraction(row(mi("d"), sub("K", "0")), mi("dT")),
            dt,
          ),
        ],
        "ΔT = T − Tr.",
      );
    if (value === "reciprocal_cubic")
      return help(
        "Cubic reciprocal bulk modulus",
        "Uses a cubic polynomial in absolute temperature for compressibility; dK/dT must be zero for this choice.",
        referenceState,
        [
          eq(
            "1/K₀(T) = 1/K₀(Tr) + β₁(T − Tr)",
            fraction(mn(1), k0t),
            mo("="),
            fraction(mn(1), k0r),
            mo("+"),
            sub("β", "1"),
            parens(mi("T"), mo("−"), tr),
          ),
          eq(
            "+ β₂(T² − Tr²) + β₃(T³ − Tr³)",
            mo("+"),
            sub("β", "2"),
            parens(power(mi("T"), mn(2)), mo("−"), power(tr, mn(2))),
            mo("+"),
            sub("β", "3"),
            parens(power(mi("T"), mn(3)), mo("−"), power(tr, mn(3))),
          ),
        ],
      );
  }
  if (key === "thermal_pressure_reference") {
    if (value === "reference_temperature")
      return help(
        "Reference-temperature isotherm",
        "Subtracts the thermal contribution at Tr, evaluated at the same volume. The correction vanishes at T = Tr.",
        thermalReference,
        undefined,
        "The selected mechanical EoS represents the isotherm at Tr.",
      );
    if (value === "absolute_zero")
      return help(
        "Absolute-zero cold curve",
        "Adds the absolute thermal pressure without subtracting a reference-temperature contribution.",
        thermalReference,
        undefined,
        "The mechanical EoS must be a 0 K cold curve in the source’s zero-point convention.",
      );
    if (value === "reference_isentrope")
      return help(
        "Reference isentrope",
        "Subtracts the thermal contribution along a constant-entropy reference path, rather than the full Tr isotherm.",
        thermalReference,
        [
          eq(
            "Tₛ(V) = Tr Θ(V)/Θ₀",
            sub("T", "S"),
            parens(mi("V")),
            mo("="),
            tr,
            fraction(theta, theta0),
          ),
        ],
        "The mechanical EoS must describe that reference isentrope. Not supported by every thermal model.",
      );
  }
  return null;
}

export function parameterHelp(key: string): ModelHelp | null {
  if (key !== "Cvmax") return null;
  const cv = sub("C", "V,max");
  return {
    title: "High-temperature heat-capacity limit",
    description:
      "Cᵥ,max sets the high-temperature limit of molar heat capacity at constant volume, in J mol⁻¹ K⁻¹. It scales Debye vibrational energy and thermal pressure.",
    url: equationUrl("debye-energy-and-heat-capacity"),
    equations: [
      eq("Default Cᵥ,max = 3nR", cv, mo("="), mn(3), mi("n"), mi("R")),
      eq(
        "E_D(V,T) = Cᵥ,max T D₃(Θ(V)/T)",
        sub("E", "D"),
        parens(mi("V"), mo(","), mi("T")),
        mo("="),
        cv,
        mi("T"),
        sub("D", "3"),
        parens(fraction(theta, mi("T"))),
      ),
    ],
    note: "Leave blank to use 3nR. n is atoms per formula unit; R is the molar gas constant (about 8.314 J mol⁻¹ K⁻¹). The molar basis must match the material’s formula-unit volume.",
  };
}
