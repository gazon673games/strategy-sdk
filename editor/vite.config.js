import { cpSync } from "node:fs";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    { name: "litegraph-core", enforce: "pre", transform(code, id) {
      if (!id.replaceAll("\\", "/").endsWith("litegraph.js/build/litegraph.js")) return;
      const marker = code.indexOf("//basic nodes");
      if (marker === -1) throw new Error("Unsupported LiteGraph bundle: core boundary is missing");
      // The editor uses only canvas/nodes. Built-in script, network and media nodes are excluded.
      const core = code.slice(0, marker);
      if (!core.includes("v = eval(v);")) throw new Error("Unsupported LiteGraph number widget");
      return { code: core.replace("v = eval(v);", "v = Number(v);")
        .replaceAll("[H * 0.5]", "[4]"), map: null };
    } },
    { name: "blockly-media", closeBundle() {
      cpSync("node_modules/blockly/media", "dist/blockly-media", { recursive: true });
      for (const name of ["blockly", "litegraph.js"]) {
        cpSync(`node_modules/${name}/LICENSE`, `dist/${name}-LICENSE.txt`);
      }
    } },
  ],
  build: { chunkSizeWarningLimit: 1500 },
});
