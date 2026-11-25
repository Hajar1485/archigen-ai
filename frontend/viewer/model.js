import * as THREE from "three";
import { boxOnWall, solidBands } from "./geometry.js";
import { wallMeshGeometry } from "./wall-mesh.js";

function floorMaterial(room) {
  const tiled = ["bathroom", "kitchen"].includes(room.type);
  const color = { bathroom: "#b0c5c4", kitchen: "#d4cbbb", corridor: "#cabda7", bedroom: "#dbbf9f" }[room.type] || "#ddc7a8";
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, 128, 128);
  ctx.strokeStyle = "rgba(71,57,36,0.18)";
  ctx.lineWidth = 1;
  const rows = tiled ? 2 : 5;
  for (let i = 0; i < rows; i++) {
    const y = i * 128 / rows, x = tiled ? 64 : (i * 49) % 128;
    ctx.beginPath();
    ctx.moveTo(0, y); ctx.lineTo(128, y);
    ctx.moveTo(x, y); ctx.lineTo(x, y + 128 / rows);
    ctx.stroke();
  }
  const map = new THREE.CanvasTexture(canvas);
  map.colorSpace = THREE.SRGBColorSpace;
  map.wrapS = map.wrapT = THREE.RepeatWrapping;
  map.repeat.set(room.size[0] / 1.35, room.size[2] / 1.35);
  return new THREE.MeshStandardMaterial({ map, roughness: 0.94 });
}

export function disposeTree(root) {
  const geometries = new Set(), materials = new Set(), textures = new Set();
  root.traverse(obj => {
    if (obj.geometry) geometries.add(obj.geometry);
    if (obj.material) for (const m of [obj.material].flat()) {
      materials.add(m);
      if (m.map) textures.add(m.map);
    }
  });
  for (const resource of [...textures, ...materials, ...geometries]) resource.dispose();
  root.removeFromParent();
}

export function buildModel(plan, cutaway = false) {
  const root = new THREE.Group();
  const layers = {};
  for (const key of ["exterior", "interior", "floors"]) {
    layers[key] = new THREE.Group();
    root.add(layers[key]);
  }
  const cube = new THREE.BoxGeometry();
  function addBox(group, spec, material, meta) {
    const mesh = new THREE.Mesh(cube, material);
    mesh.scale.fromArray(spec.size);
    mesh.position.fromArray(spec.position);
    mesh.rotation.y = spec.angle ?? 0;
    mesh.castShadow = mesh.receiveShadow = true;
    mesh.userData = meta;
    group.add(mesh);
    return mesh;
  }
  for (const room of plan.floors) {
    addBox(layers.floors, room, floorMaterial(room), { roomId: room.id, name: room.name, area: room.area });
  }
  const materials = new Map();
  function surface(key) {
    if (!materials.has(key)) {
      const settings = key === "glass" ? {color: 0x68aaa9, transparent: true, opacity: 0.28, depthWrite: false} :
        {color: key === "frame" ? 0x627d7c : key === "exterior" ? 0xf3ede1 : 0xe5dbca};
      materials.set(key, new THREE.MeshStandardMaterial({ ...settings, roughness: 0.78 }));
    }
    return materials.get(key);
  }
  const cap = cutaway ? Math.min(0.85, plan.height) : plan.height;
  for (const wall of plan.walls) {
    const key = wall.exterior ? "exterior" : "interior";
    const group = layers[key];
    const bands = solidBands(wall.start, wall.end, cap, wall.openings);
    if (bands.length) {
      const mesh = new THREE.Mesh(wallMeshGeometry(bands,wall.thickness),surface(key));
      mesh.position.set(wall.x1,0,-wall.y1);
      mesh.rotation.y = wall.angle;
      mesh.castShadow = mesh.receiveShadow = true;
      mesh.userData = { wallId:wall.id, exterior:wall.exterior, adjacent:wall.adjacent_room_ids };
      group.add(mesh);
    }
    for (const o of wall.openings.filter(o => o.kind === "window" && o.sill < cap)) {
      const a = o.offset, b = a + o.width, lo = o.sill, head = lo + o.height, hi = Math.min(head, cap);
      const trim = Math.min(0.035, o.width / 4, o.height / 4);
      const depth = Math.min(0.04, wall.thickness / 2);
      const meta = { wallId: wall.id, openingId: o.id };
      const pane = addBox(group, boxOnWall(wall, a, b, lo, hi, depth / 4), surface("glass"), meta);
      pane.castShadow = false;
      // Cadre de présentation dans la baie, sans division ni sens d'ouvrant supposé.
      for (const [s, t, z, h] of [[a,a+trim,lo,hi], [b-trim,b,lo,hi],
        [a+trim,b-trim,lo,Math.min(lo+trim,hi)], [a+trim,b-trim,head-trim,hi]]) {
        if (h > z) addBox(group, boxOnWall(wall,s,t,z,h,depth),surface("frame"),meta);
      }
    }
  }
  return {root, layers};
}
