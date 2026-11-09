import { transformWithOxc } from "vite";

/** Vite skips React Refresh signatures in .ts modules without JSX imports.
 * Propagate their updates to component importers, with signatures attached so
 * React can remount only when the hook layout actually changes.
 */
export function reactHookRefresh() {
  let base;
  let enabled;
  return {
    name: "dioptas-react-hook-refresh",
    apply: "serve",
    enforce: "pre",
    configResolved(config) {
      base = config.base;
      enabled = !config.isProduction && config.server.hmr !== false;
    },
    async transform(code, id) {
      if (
        !enabled ||
        !id.endsWith(".ts") ||
        id.includes("/node_modules/") ||
        !/export\s+(?:function\s+use[A-Z]|const\s+use[A-Z])/.test(code)
      )
        return;
      const result = await transformWithOxc(code, id, {
        jsx: { runtime: "automatic", refresh: true },
        sourcemap: true,
      });
      if (!result.code.includes("$RefreshSig$")) return;
      // A hook-only module has no component registration and thus no wrapper
      // from plugin-react. Import the real signature factory explicitly.
      result.code += `\nimport { createSignatureFunctionForTransform as $RefreshSig$ } from ${JSON.stringify(`${base}@react-refresh`)};\n`;
      return result;
    },
  };
}
