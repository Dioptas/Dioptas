import type { EditorField } from "./phaseEditorTypes";
import {
  modelHelp,
  parameterHelp as heatCapacityHelp,
  peritheosManual,
  type ModelHelp,
} from "./phaseModelHelp";

type Context = {
  eosType: string;
  thermalType: string;
  fields: EditorField[];
  blankAllowed: boolean;
};
type Definition = [title: string, description: string, unit?: string];
const definitions: Record<string, Definition> = {
  k0: [
    "Reference bulk modulus",
    "Resistance to volume compression: Kₜ = −V(∂P/∂V)ₜ. A larger K₀ gives a less compressible reference state. For BM2Reference it is defined at P₀; otherwise the model's usual reference pressure applies.",
    "GPa",
  ],
  k0p0: [
    "Pressure derivative of bulk modulus",
    "K₀′ = (∂Kₜ/∂P) at the reference state. It controls how rapidly the material stiffens or softens under compression.",
    "dimensionless",
  ],
  k0pp0: [
    "Second pressure derivative of bulk modulus",
    "K₀″ = ∂²Kₜ/∂P² at the reference state. It controls the curvature of Kₜ(P) in fourth-order and Modified Tait models.",
    "GPa⁻¹",
  ],
  p0: [
    "Reference pressure",
    "Pressure at which this record defines V₀ and K₀. BM2Reference adds its BM2 pressure increment to P₀.",
    "GPa",
  ],
  n: [
    "Atoms per formula unit",
    "Number of atoms in the formula unit used by the EoS. It sets vibrational normalization, including the usual 3nR high-temperature heat capacity. Use the same formula basis for molar volume and molar mass.",
    "atoms/formula",
  ],
  zc: [
    "Formula units per crystallographic cell",
    "Z cell converts crystallographic cell volume to volume per formula unit before molar normalization. For a cell with Z formula units, the formula-unit volume is Vcell/Z.",
    "formula/cell",
  ],
  z: [
    "Electronic normalization parameter",
    "Electron/atomic-number parameter retained by the material. For Holzapfel, use the atomic-number or effective Z specified by the source parameterization; it enters the free-electron pressure through Zn. This is distinct from the crystallographic Z cell.",
    "source-defined electron/atomic-number parameter",
  ],
  theta0: [
    "Reference characteristic temperature",
    "Characteristic vibrational temperature at V₀. It sets the energy scale of the selected Debye or Einstein spectrum; the temperature law determines how it changes with volume.",
    "K",
  ],
  theta: [
    "Einstein characteristic temperature",
    "Fixed oscillator temperature in the Holland–Powell thermal-pressure term. It controls the thermal occupation energy and heat capacity used to normalize thermal pressure.",
    "K",
  ],
  gamma0: [
    "Reference Grüneisen parameter",
    "Value of γ at V₀. It couples vibrational energy to thermal pressure and controls the volume dependence of characteristic temperatures. The selected model or Debye law defines the precise relation.",
    "dimensionless",
  ],
  gamma_inf: [
    "Limiting Grüneisen parameter",
    "Value approached by γ at infinite compression (V/V₀ → 0) in the selected asymptotic Grüneisen law.",
    "dimensionless",
  ],
  q: [
    "Volume dependence of the Grüneisen parameter",
    "Exponent in γ(V) = γ₀(V/V₀)^q; for positive γ, q = d ln γ/d ln V. q = 0 gives constant γ. The selected Debye temperature law determines how γ is used to obtain Θ(V).",
    "dimensionless",
  ],
  dK_dT: [
    "Temperature slope of reference bulk modulus",
    "Changes the reference bulk modulus by (dK₀/dT)(T − Tr). A negative slope softens the reference material on heating. The reciprocal-cubic bulk-modulus law requires this slope to be zero.",
    "GPa/K",
  ],
  alpha1: [
    "Temperature dependence of expansion",
    "Coefficient controlling the temperature dependence of the expansion or direct reference-volume law. The selected law specifies whether the temperature coordinate is T or T − Tr.",
    "K⁻²",
  ],
  dKprime_dT: [
    "Temperature slope of K₀′",
    "Adds (dK₀′/dT)(T − Tr) to the reference pressure derivative. This changes the pressure dependence of stiffness with temperature in supported reference families.",
    "K⁻¹",
  ],
  kprime_log_coefficient: [
    "Logarithmic temperature term in K₀′",
    "Coefficient multiplying (T − Tr) ln(T/Tr) in K₀′(T). This term adds to the optional linear slope and vanishes at Tr.",
    "K⁻¹",
  ],
  beta1: [
    "Linear compressibility coefficient",
    "Coefficient β₁ of (T − Tr) in 1/K₀(T). It is active with the reciprocal-cubic bulk-modulus law.",
    "GPa⁻¹ K⁻¹",
  ],
  beta2: [
    "Quadratic compressibility coefficient",
    "Coefficient β₂ of (T² − Tr²) in 1/K₀(T). It is active with the reciprocal-cubic bulk-modulus law.",
    "GPa⁻¹ K⁻²",
  ],
  beta3: [
    "Cubic compressibility coefficient",
    "Coefficient β₃ of (T³ − Tr³) in 1/K₀(T). It is active with the reciprocal-cubic bulk-modulus law.",
    "GPa⁻¹ K⁻³",
  ],
  alpha_KT: [
    "Linear thermal-pressure slope",
    "The fitted product αKₜ gives the pressure increase per kelvin: ΔP = αKₜ(T − Tr). It is a single coefficient rather than independently fitted α and Kₜ.",
    "GPa/K",
  ],
  alpha_KT_ref: [
    "Reference thermal-pressure slope",
    "Value of the αKₜ product at V₀. The logarithmic-volume term changes this slope away from the reference volume.",
    "GPa/K",
  ],
  dK_dT_V: [
    "Constant-volume modulus temperature slope",
    "Coefficient multiplying ln(V₀/V)(T − Tr) in logarithmic-volume thermal pressure. The derivative is at fixed volume, unlike a constant-pressure temperature slope.",
    "GPa/K",
  ],
  a: [
    "Amplitude of Grüneisen volume dependence",
    "Controls the departure from constant γ in γ(V) = γ₀{1 + a[(V/V₀)^b − 1]}. Its combination with b determines the Tange temperature law.",
    "dimensionless",
  ],
  b: [
    "Exponent of Grüneisen volume dependence",
    "Exponent of V/V₀ in the Tange Grüneisen law. The temperature law integrates that same γ(V), including its continuous b = 0 limit.",
    "dimensionless",
  ],
  beta0: [
    "Excess free-energy coefficient",
    "Sets the T² excess free energy Fex = −β₀(V/V₀)^m T²/2. Its volume derivative contributes pressure; the reference-temperature contribution is subtracted.",
    "J mol⁻¹ K⁻²",
  ],
  A: [
    "Quadratic thermal-pressure coefficient",
    "Amplitude of the added pressure A(V/V₀)^m(T² − Tr²). A = 0 removes this excess contribution and leaves the integrated-law Debye model.",
    "GPa/K²",
  ],
  eta0: [
    "Reference compression coordinate",
    "Center of the Taylor expansion in compression. The model uses η = 1 − V/V₀ and Δη = η − η₀.",
    "dimensionless",
  ],
  c0: [
    "Constant Taylor pressure term",
    "Absolute thermal-pressure offset c₀. Unlike a referenced heating correction, it can remain nonzero at Tr.",
    "GPa",
  ],
  c1: [
    "Linear compression term",
    "Coefficient of Δη in the absolute Taylor thermal pressure, where Δη = 1 − V/V₀ − η₀.",
    "GPa",
  ],
  c2: [
    "Linear temperature term",
    "Coefficient of ΔT = T − Tr in the absolute Taylor thermal pressure.",
    "GPa/K",
  ],
  c3: [
    "Quadratic compression term",
    "Coefficient of Δη²/2 in the absolute Taylor thermal pressure.",
    "GPa",
  ],
  c4: [
    "Quadratic temperature term",
    "Coefficient of ΔT²/2 in the absolute Taylor thermal pressure.",
    "GPa/K²",
  ],
  c5: [
    "Mixed compression–temperature term",
    "Coefficient of Δη ΔT/2 in this model's published Taylor convention. It makes the thermal-pressure slope depend on compression.",
    "GPa/K",
  ],
  delta: [
    "Grüneisen normalization offset",
    "Additive offset δ in the multi-oscillator Grüneisen function. It shifts γ derived from the reference pressure, bulk modulus and its pressure derivative.",
    "dimensionless",
  ],
  t: [
    "Generalized Grüneisen coefficient",
    "Reference coefficient t in the generalized parameter t̃(x) = t − βx^(1/3), with x = V/V₀. It enters the multi-oscillator Grüneisen function.",
    "dimensionless",
  ],
  Vp: [
    "Reference volume of the phonon law",
    "Molar reference volume for each double-Debye characteristic-temperature law: θᵢ(V) = θᵢ₀(V/Vp)^(−bᵢ) exp[aᵢ(Vp − V)]. It need not equal the cold curve's V₀.",
    "J bar⁻¹ mol⁻¹",
  ],
  Ve: [
    "Reference volume of anharmonicity",
    "Volume normalizing α(V) = α₀(V/Ve)^κ in the double-Debye anharmonic term. Keep its molar basis consistent with Vp and the reference curve.",
    "J bar⁻¹ mol⁻¹",
  ],
  kappa: [
    "Anharmonic volume exponent",
    "Exponent κ in α(V) = α₀(V/Ve)^κ. It controls the volume derivative and hence the pressure contribution of the T² free energy; κ = 0 makes that term independent of volume.",
    "dimensionless",
  ],
  phi0: [
    "Reference energy zero",
    "Additive molar energy constant of the reference curve. It shifts absolute energy but does not change pressure; pressure-only measurements cannot determine it.",
    "J/mol",
  ],
  anharmonic_m: [
    "Anharmonic volume exponent",
    "Controls the volume dependence of the selected model's intrinsic-anharmonic term. Its precise free-energy convention is shown in the model equations.",
    "dimensionless",
  ],
  electronic_g: [
    "Electronic volume exponent",
    "Controls the volume dependence of the electronic coefficient and its pressure contribution.",
    "dimensionless",
  ],
  g: [
    "Electronic volume exponent",
    "Exponent g of x = V/V₀ in the multi-oscillator electronic term. It also appears in the pressure obtained from that term's volume dependence.",
    "dimensionless",
  ],
  defect_H: [
    "Defect enthalpy scale",
    "Defect enthalpy expressed as a temperature. It enters the exponential as −H/[T(V/V₀)²], so H is supplied in kelvin rather than joules per mole.",
    "K",
  ],
  defect_S: [
    "Defect entropy parameter",
    "Dimensionless entropy coefficient in exp[S/(V/V₀) − H/{T(V/V₀)²}]. It controls the amplitude of the defect free-energy contribution.",
    "dimensionless",
  ],
  molar_mass_g_mol: [
    "Formula-unit molar mass",
    "Mass per mole of the same formula unit used by n and molar volume. The sound-velocity model uses it to calculate density.",
    "g/mol",
  ],
  longitudinal_intercept: [
    "Longitudinal velocity intercept",
    "Intercept aₗ of the source regression Cₗᶠⁱᵗ = aₗ + bₗρ. The longitudinal/shear regression ratio is used to infer the elastic Poisson ratio.",
    "km/s",
  ],
  longitudinal_slope: [
    "Longitudinal velocity–density slope",
    "Coefficient bₗ multiplying density ρ in the longitudinal velocity regression. Density is in g/cm³ and velocity in km/s.",
    "(km/s)/(g/cm³)",
  ],
  shear_intercept: [
    "Shear velocity intercept",
    "Intercept aₛ of the source regression Cₛᶠⁱᵗ = aₛ + bₛρ. It combines with the longitudinal regression to determine the elastic Poisson ratio.",
    "km/s",
  ],
  shear_slope: [
    "Shear velocity–density slope",
    "Coefficient bₛ multiplying density ρ in the shear velocity regression. Density is in g/cm³ and velocity in km/s.",
    "(km/s)/(g/cm³)",
  ],
  alpha_t0: [
    "Legacy reference expansivity",
    "Volumetric expansion coefficient in the legacy Dioptas correction anchored at 298 K. Together with dα/dT it sets α = α(T₀) + (dα/dT)(T − 298 K).",
    "K⁻¹",
  ],
  d_alpha_dt: [
    "Legacy expansivity temperature slope",
    "Temperature coefficient of α in the legacy Dioptas correction, with its 298 K reference. This convention is separate from the selectable AlphaKT reference-volume laws.",
    "K⁻²",
  ],
  dk0dt: [
    "Legacy bulk-modulus temperature slope",
    "Adds (dK₀/dT)(T − 298 K) to the legacy bulk modulus before the corrected pressure is inverted.",
    "GPa/K",
  ],
  dk0pdt: [
    "Legacy K₀′ temperature slope",
    "Adds (dK₀′/dT)(T − 298 K) to the legacy BM3 pressure derivative.",
    "K⁻¹",
  ],
};

function definition(
  field: EditorField,
  context: Context,
): Definition | undefined {
  const key = field.key,
    model = context.thermalType;
  if (key === "Tr")
    return [
      "Reference temperature",
      model.startsWith("DoubleDebye")
        ? "A supplied Tr rebases the simulated non-cold free energy to a reference isotherm at that temperature. Leaving Tr blank selects the absolute free-energy convention with a motionless-lattice 0 K reference curve."
        : model === "SecondOrderTaylorThermalPressure"
          ? "Temperature coordinate about which the absolute thermal-pressure polynomial is expanded. The correction need not vanish at Tr; its mechanical reference is a cold curve."
          : "Temperature anchoring the thermal model. The pressure-reference choice determines whether this is a reference isotherm, an isentropic anchor, or an anchor used only for temperature increments.",
      "K",
    ];
  if (key === "alpha0" && model === "AlphaKT") {
    const selected = (key: string, fallback: string) =>
      String(
        context.fields.find((field) => field.key === key)?.value ?? fallback,
      );
    const volume = selected("reference_volume_law", "integrated_expansivity");
    const expansion = selected("thermal_expansion_law", "constant");
    const description =
      volume === "berman"
        ? "Volumetric expansion coefficient at Tr in the selected Berman reference-volume polynomial. It multiplies T − Tr in V₀(T)/V₀(Tr)."
        : volume === "linear_temperature"
          ? "Mean expansion coefficient in the selected direct relation V₀(T) = V₀(Tr)[1 + α₀(T − Tr)]."
          : expansion === "linear_temperature"
            ? "T = 0 intercept in the selected law α(T) = α₀ + α₁T. Its value at Tr is α₀ + α₁Tr."
            : expansion === "linear_reference_temperature"
              ? "Volumetric expansion coefficient at Tr in the selected law α(T) = α₀ + α₁(T − Tr)."
              : "Constant volumetric thermal-expansion coefficient in the selected integrated law V₀(T) = V₀(Tr) exp[α₀(T − Tr)].";
    return ["Reference thermal-expansion coefficient", description, "K⁻¹"];
  }
  if (key === "alpha0")
    return model === "DoubleDebyeHelmholtz"
      ? [
          "Double-Debye anharmonic coefficient",
          "Sets Fanh = −nRα(V)T²/2 with α(V) = α₀(V/Ve)^κ. This is an anharmonic energy coefficient, separate from volumetric thermal expansivity.",
          "K⁻¹",
        ]
      : [
          "Reference thermal-expansion coefficient",
          model === "AlphaKT"
            ? "Volumetric expansion coefficient in the selected law. For linear absolute-temperature expansion it is the T = 0 intercept; for expansion from Tr and the Berman volume law it is defined at Tr. The direct linear-volume law uses it as a mean expansion coefficient."
            : "Volumetric expansion coefficient at Tr, used with K₀ and the Einstein heat capacity to normalize Holland–Powell thermal pressure.",
          "K⁻¹",
        ];
  if (key === "beta")
    return [
      "Volume-dependence coefficient",
      model === "MultiOscillatorGruneisen" || model === "Sokolova2016"
        ? "Coefficient β in t̃(x) = t − βx^(1/3), which modifies the generalized Grüneisen function. β = 0 recovers its reduced form."
        : "Exponent β in γ(x) = γ∞ + (γ₀ − γ∞)x^β, with x = V/V₀. It controls the approach to the limiting Grüneisen parameter.",
      "dimensionless",
    ];
  if (key === "m")
    return [
      "Volume exponent",
      model === "DebyeQuadraticThermalPressure"
        ? "Exponent m in A(V/V₀)^m(T² − Tr²), controlling how the quadratic thermal pressure varies with volume."
        : model === "AsymptoticPowerLawMieGruneisenDebyeExcess"
          ? "Exponent m in the excess free energy −β₀(V/V₀)^m T²/2. The pressure follows its volume derivative."
          : "Exponent m of V/V₀ in the multi-oscillator anharmonic coefficient; it also enters the corresponding pressure term.",
      "dimensionless",
    ];
  if (model.startsWith("DoubleDebye") && /^theta_(a0|b0|1_0|0_0)$/.test(key))
    return [
      "Reference phonon temperature",
      key === "theta_1_0"
        ? "Arithmetic phonon-moment temperature at Vp. Together with the two cutoffs it determines the double-Debye weights."
        : key === "theta_0_0"
          ? "Logarithmic phonon-moment temperature at Vp. It determines the logarithmic-moment double-Debye weights."
          : "Debye cutoff temperature of this spectrum at Vp. Each cutoff has its own volume-law coefficients.",
      "K",
    ];
  if (model.startsWith("DoubleDebye") && /^a_[ab10]$/.test(key))
    return [
      "Phonon-law inverse-volume coefficient",
      "Coefficient aᵢ in θᵢ(V) = θᵢ₀(V/Vp)^(−bᵢ) exp[aᵢ(Vp − V)]. The corresponding mode Grüneisen parameter is aᵢV + bᵢ.",
      "bar mol/J",
    ];
  if (model.startsWith("DoubleDebye") && /^b_[ab10]$/.test(key))
    return [
      "Phonon-law power exponent",
      "Coefficient bᵢ in θᵢ(V) = θᵢ₀(V/Vp)^(−bᵢ) exp[aᵢ(Vp − V)]. It contributes bᵢ to the mode Grüneisen parameter aᵢV + bᵢ.",
      "dimensionless",
    ];
  if (/^(QE1o|QE2o|QBo|QB1o|theta_[BE][12])$/.test(key))
    return [
      "Reference oscillator temperature",
      "Characteristic temperature of this Einstein or generalized Bose mode at V₀. The selected Grüneisen law supplies its volume dependence.",
      "K",
    ];
  if (/^(mE[12]|mb1?|m_[BE][12])$/.test(key))
    return [
      "Oscillator multiplicity",
      "Weight of this vibrational mode in the summed energy and pressure. A zero optional multiplicity disables that mode; retain the source model's mode-count normalization.",
      "dimensionless",
    ];
  if (/^(d|d1|d_B[12])$/.test(key))
    return [
      "Bose-mode dispersion parameter",
      "Shape parameter d in the generalized Bose occupation-energy function. It changes that mode's thermal energy versus temperature; it is separate from the mode multiplicity.",
      "dimensionless",
    ];
  if (["a_0", "anharmonic_a"].includes(key))
    return [
      "Intrinsic-anharmonic coefficient",
      model === "DoubleDebyeLogMomentHelmholtz"
        ? "Coefficient a in the volume-independent free energy Fanh = −nRaT². This term changes energy and heat capacity but has zero pressure contribution."
        : "Amplitude of the selected model's intrinsic-anharmonic free-energy contribution. Use the units shown: micro-K⁻¹ coefficients are entered in multiples of 10⁻⁶, whereas K⁻¹ coefficients are entered directly.",
      field.unit,
    ];
  if (["e_0", "electronic_e"].includes(key))
    return [
      "Electronic energy coefficient",
      "Amplitude of the model's electronic T² contribution. Its volume exponent sets the pressure contribution. Enter the coefficient in the displayed units, including any 10⁻⁶ scale factor.",
      field.unit,
    ];
  if (key === "zero_point_pressure")
    return [
      "Zero-point pressure convention",
      "Specifies whether the chosen formulation includes the pressure associated with zero-point vibrational energy. Preserve the convention required by the source's cold/reference curve.",
      "convention",
    ];
  return definitions[key];
}

export function phaseParameterHelp(
  field: EditorField,
  context: Context,
): ModelHelp {
  const capacity = heatCapacityHelp(field.key);
  const info = definition(field, context);
  const unit =
    field.key === "z" && context.eosType === "Holzapfel"
      ? "dimensionless, using the source effective-Z convention"
      : field.unit || info?.[2] || "dimensionless";
  const eosKey = ["k0", "k0p0", "k0pp0", "p0", "z"].includes(field.key);
  const normalization = ["n", "zc"].includes(field.key);
  const model = modelHelp(
    eosKey ? "eos" : "thermal",
    eosKey ? context.eosType : context.thermalType,
  );
  let defaults =
    typeof field.value === "string" || typeof field.default === "string"
      ? "This convention is retained by the selected model."
      : "A numerical value is required.";
  if (context.blankAllowed) {
    if (field.key === "Cvmax") defaults = "Blank uses 3nR.";
    else if (field.default != null)
      defaults = `Blank uses the model default ${field.default}.`;
    else if (
      field.key === "Tr" &&
      context.thermalType.startsWith("DoubleDebye")
    )
      defaults = "Blank selects the absolute free-energy convention.";
    else if (field.key === "Ve")
      defaults =
        "Blank uses the model's anharmonic reference-volume convention; see the selected model definition.";
    else
      defaults =
        "Blank leaves this optional value to the selected model's default convention.";
  }
  return {
    ...(capacity ?? {}),
    title: capacity?.title ?? info?.[0] ?? field.description ?? field.label,
    description:
      capacity?.description ??
      info?.[1] ??
      field.description ??
      `Coefficient used by ${model.title}; see the selected model definition.`,
    url:
      capacity?.url ??
      (normalization
        ? `${peritheosManual}units/#atom-count-and-molar-volume-basis`
        : model.url),
    note: [capacity?.note, `Units: ${unit}.`, defaults]
      .filter(Boolean)
      .join(" "),
  };
}
