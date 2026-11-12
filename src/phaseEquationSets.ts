import generated from "./phaseEquations.generated.json";
import type { ModelHelp } from "./phaseModelHelp";
const sets: Record<string, NonNullable<ModelHelp["equations"]>> = generated;

export function phaseModelEquations(
  kind: "eos" | "thermal",
  name: string,
  configuration: Record<string, unknown>,
) {
  if (kind === "thermal" && name === "SoundVelocityDebyeHelmholtz") return [];
  const keys = [`${kind}:${name}`];
  if (kind === "thermal") {
    if (name === "MieGruneisenDebye") {
      keys.unshift("common:debye");
      keys.push(
        `pressure:${configuration.thermal_pressure_reference ?? "reference_temperature"}`,
      );
    } else if (name === "MieGruneisenEinstein") {
      keys.unshift("common:einstein", "common:integrated-law");
      keys.push("pressure:reference_temperature");
    } else if (name.startsWith("AsymptoticPowerLawMieGruneisenDebye")) {
      keys.unshift("common:fixed-debye", "increment:debye");
      if (!name.endsWith("Excess")) keys.push("total:debye");
    } else if (name === "DebyeQuadraticThermalPressure") {
      keys.unshift(
        "common:fixed-debye",
        "common:integrated-law",
        "increment:debye",
      );
    } else if (name.startsWith("DoubleDebye")) {
      keys.unshift("common:reference-energy", "function:debye");
      keys.push("double:coincident");
      keys.push(
        configuration.Tr == null ? "double:absolute" : "double:relative",
      );
    } else if (name === "Dewaele2006") {
      keys.unshift("function:debye");
      keys.push(
        configuration.thermal_pressure_reference === "absolute_zero"
          ? configuration.zero_point_pressure === "included"
            ? "dewaele:zero-point"
            : "dewaele:absolute"
          : "dewaele:relative",
      );
    }
  }
  return keys.flatMap((key) => sets[key] ?? []);
}

export function phaseEquationNote(
  kind: "eos" | "thermal",
  name: string,
): string | undefined {
  if (kind === "eos")
    return name === "Holzapfel"
      ? "V and V₀ are model volumes after the record’s volume conversion. The Holzapfel coefficient 1003.6 assumes J bar⁻¹ mol⁻¹; a standalone isothermal record needs an explicit molar-volume scale. Pressure is in GPa. Use the source’s n and effective Z convention."
      : "Pressure and bulk modulus are in GPa. V and V₀ use the same volume basis. The strain variable is defined in the displayed equations.";
  if (name === "none") return undefined;
  if (name === "alphakt")
    return "Legacy Dioptas correction anchored at 298 K. At positive pressure it inverts the selected EoS with shifted K₀ and, when present, K₀′. Records without an EoS use BM3. The zero- and negative-pressure branches are separate legacy rules.";
  if (name === "AlphaKT")
    return "The selected laws below define V₀(T), K₀(T), and expansion. Temperature is in kelvin.";
  if (
    [
      "LinearThermalPressure",
      "LogVolumeThermalPressure",
      "SecondOrderTaylorThermalPressure",
    ].includes(name)
  )
    return "Pressure is in GPa and temperature in kelvin. V/V₀ is dimensionless; this correction inherits the reference curve's volume basis.";
  if (["HollandPowellThermalPressure", "ThermalModifiedTait"].includes(name))
    return "Oscillator energy is in J/mol, heat capacity in J mol⁻¹ K⁻¹, temperature in kelvin and pressure in GPa. n is atoms per formula unit.";
  if (name === "SoundVelocityDebyeHelmholtz")
    return "Unavailable in the linked PeriTheos Rust 0.18.0 engine. This model cannot be selected for calculation.";
  const basis =
    "Energy-based thermal equations use molar V in J bar⁻¹ mol⁻¹, energy in J/mol and pressure in GPa. The material normalization converts crystallographic cell volumes to this molar basis. R is the molar gas constant; n is atoms per formula unit. x = V/V₀ unless otherwise defined.";
  if (name.startsWith("DoubleDebye"))
    return (
      basis +
      " When |θB − θA| ≤ 10⁻¹⁰ max(θA, θB, θ₁) (arithmetic), or |ln(θB/θA)| ≤ 10⁻¹⁰ (logarithmic), the engine uses the limiting-weight branch shown with j = 1 or j = 0, respectively, and sets dwA/dV = 0."
    );
  if (["Dewaele2006", "DorogokupetsOganov2007"].includes(name))
    return basis + " β must be positive; this engine does not accept β = 0.";
  return basis;
}
