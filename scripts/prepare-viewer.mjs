// Only these static files are exposed by FastAPI. Sources and lockfile stay outside frontend/.
import { copyFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const assets = path.join(root, "frontend/assets");
await mkdir(path.join(assets, "three"), { recursive: true });
await mkdir(path.join(assets, "examples"), { recursive: true });
for (const file of ["build/three.module.js", "build/three.core.js", "examples/jsm/controls/OrbitControls.js", "LICENSE"]) {
  await copyFile(path.join(root, "node_modules/three", file), path.join(assets, "three", path.basename(file)));
}
for (const file of ["simple_floorplan.json", "residential_floorplan.json"]) {
  await copyFile(path.join(root, "data/examples", file), path.join(assets, "examples", file));
}
console.log("Ressources locales du visualiseur préparées.");
