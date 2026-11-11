// Structural DTO source shared by the existing Tauri and stdio boundaries.
// No runtime dependency or compiler is needed to check committed generation.
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const desktop = new URL("../", import.meta.url);
const schema = JSON.parse(await readFile(new URL("command_payload_schema.json", desktop), "utf8"));
if (schema.version !== 1) throw Error("Unsupported native contract schema version");
if (process.argv.slice(2).some((arg) => arg !== "--check"))
  throw Error("Use generate_native_contracts.mjs [--check]");
const checking = process.argv.includes("--check");
const banner = "Generated from command_payload_schema.json; do not edit by hand.";
const rustName = (name) => name === "RequestedProducts" ? name : `${name}Fields`;
const borrows = (name) => Object.values(schema.records[name].fields)
  .some((field) => field.validate !== false && field.type === "string");
const rustReference = (name) => `${rustName(name)}${borrows(name) ? "<'_>" : ""}`;
const tsType = (field) => `${field.type}${field.nullable ? " | null" : ""}`;
const rsType = (field) => {
  const primitive = { number: "f64", boolean: "bool", string: "&'a str" };
  return primitive[field.type] ?? (schema.enums[field.type] ? field.type : rustName(field.type));
};
let ts = `// ${banner}\n\n`;
let rs = `// ${banner}\n\nuse serde::Deserialize;\nuse serde_json::Value;\n\nuse super::PayloadCoverage;\n\n`;
for (const [name, values] of Object.entries(schema.enums)) {
  ts += `export type ${name} = ${values.map(JSON.stringify).join(" | ")};\n\n`;
  rs += `#[derive(Clone, Copy, Debug, Deserialize, serde::Serialize, PartialEq, Eq)]\n#[serde(rename_all = "snake_case")]\n#[allow(dead_code)]\npub enum ${name} {\n`;
  for (const value of values) rs += `    ${value.split("_").map((word) => word[0].toUpperCase() + word.slice(1)).join("")},\n`;
  rs += "}\n\n";
}
for (const [name, record] of Object.entries(schema.records)) {
  ts += `export interface ${name} {\n`;
  for (const [key, field] of Object.entries(record.fields))
    ts += `  ${key}${field.optional ? "?" : ""}: ${tsType(field)};\n`;
  ts += "}\n\n";
  rs += `#[derive(Debug, Deserialize)]\n`;
  if (record.strict) rs += "#[serde(deny_unknown_fields)]\n";
  rs += `#[allow(dead_code)]\npub struct ${rustName(name)}${borrows(name) ? "<'a>" : ""} {${Object.values(record.fields).some((field) => field.validate !== false) ? "\n" : ""}`;
  for (const [key, field] of Object.entries(record.fields)) {
    if (field.validate === false) continue;
    const partial = record.partialRust !== false || field.optional;
    rs += `    pub ${key}: ${partial ? `Option<${rsType(field)}>` : rsType(field)},\n`;
  }
  rs += "}\n\n";
}
ts += "export interface NativePayloadContracts {\n";
for (const [command, spec] of Object.entries(schema.commands)) {
  const body = spec.record ?? Object.entries(spec.variants).map(([operation, record]) =>
    `(${record} & { ${spec.selector}${operation === spec.default ? "?" : ""}: ${JSON.stringify(operation)} })`,
  ).join(" | ");
  ts += `  ${command}: ${body};\n`;
}
ts += "}\n\nexport type NativeCoveredCommand = keyof NativePayloadContracts;\n";
rs += `fn fields<'a, T: Deserialize<'a>>(payload: &'a Value) -> Result<(), String> {\n    T::deserialize(payload)\n        .map(|_| ())\n        .map_err(|error| error.to_string())\n}\n\n`;
rs += "pub fn validate_fields(action: &str, payload: &Value) -> Result<PayloadCoverage, String> {\n    match action {\n";
for (const [command, spec] of Object.entries(schema.commands)) {
  if (spec.record) rs += `        ${JSON.stringify(command)} => fields::<${rustReference(spec.record)}>(payload)?,\n`;
  else {
    rs += `        ${JSON.stringify(command)} => {\n            match payload[${JSON.stringify(spec.selector)}].as_str().unwrap_or(${JSON.stringify(spec.default)}) {\n`;
    for (const [operation, record] of Object.entries(spec.variants))
      rs += `                ${JSON.stringify(operation)} => fields::<${rustReference(record)}>(payload)?,\n`;
    rs += "                _ => (), // Preserve the handler's unsupported-operation error.\n            }\n        }\n";
  }
}
rs += "        _ => return Ok(PayloadCoverage::Legacy),\n    }\n    Ok(PayloadCoverage::TypedFields)\n}\n";
for (const [relative, output] of [
  ["src/nativePayloadContracts.generated.ts", ts],
  ["native_payload_contracts.generated.rs", rs],
]) {
  const destination = new URL(relative, desktop);
  if (checking) {
    if (await readFile(destination, "utf8").catch(() => "") !== output)
      throw Error(`${fileURLToPath(destination)} is stale; run node scripts/generate_native_contracts.mjs`);
  } else await writeFile(destination, output);
}
console.log(`Native structural contracts: ${Object.keys(schema.commands).length} covered commands; ${checking ? "generation checked" : "generated"}.`);
