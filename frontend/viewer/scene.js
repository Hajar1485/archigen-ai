import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { buildModel, disposeTree } from "./model.js";
import { frameBounds } from "./camera.js";

export class PlanScene {
  constructor(host, onRoom, onContextLoss) {
    this.host = host;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    const renderer = this.renderer;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.domElement.setAttribute("aria-label", "Maquette 3D interactive du plan");
    host.append(renderer.domElement);
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xecefe9);
    this.camera = new THREE.PerspectiveCamera(37, 1, 0.02, 500);
    this.controls = new OrbitControls(this.camera, renderer.domElement);
    this.controls.maxPolarAngle = Math.PI / 2 - 0.035;
    this.controls.addEventListener("change", () => this.invalidate());
    this.scene.add(new THREE.HemisphereLight(0xf3f7ff, 0xc0b7a7, 1.9));
    this.sun = new THREE.DirectionalLight(0xfff8ea, 2.6);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(1024, 1024);
    this.sun.shadow.normalBias = 0.012;
    this.scene.add(this.sun, this.sun.target);
    this.abort = new AbortController();
    const options = {signal: this.abort.signal};
    const canvas = renderer.domElement;
    canvas.addEventListener("webglcontextlost", e => { e.preventDefault(); onContextLoss(); }, options);
    let start;
    canvas.addEventListener("pointerdown", e => { start = [e.clientX, e.clientY]; }, options);
    canvas.addEventListener("pointerup", e => {
      if (!start || Math.hypot(e.clientX-start[0], e.clientY-start[1]) > 4 || e.button !== 0) return;
      const rect = canvas.getBoundingClientRect(), ray = new THREE.Raycaster();
      ray.setFromCamera(new THREE.Vector2(2*(e.clientX-rect.left)/rect.width-1, 1-2*(e.clientY-rect.top)/rect.height), this.camera);
      const groups = Object.values(this.model.layers).filter(g => g.visible);
      const hit = ray.intersectObjects(groups, true)[0]?.object.userData;
      onRoom(hit?.roomId ? hit : null);
    },options);
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(host);
    this.resize();
  }

  resize() {
    const {clientWidth:w, clientHeight:h} = this.host;
    if (!w || !h || (this.width === w && this.height === h)) return;
    this.width = w;
    this.height = h;
    this.renderer.setSize(w,h,false);
    this.camera.aspect = w/h;
    this.camera.updateProjectionMatrix();
    if (this.bounds) this.view(this.preset);
    this.invalidate();
  }

  invalidate() {
    if (this.frame || this.disposed) return;
    this.frame = requestAnimationFrame(() => {
      this.frame = 0;
      if (this.host.clientWidth && this.host.clientHeight) this.renderer.render(this.scene,this.camera);
    });
  }

  load(plan, state) {
    if (this.model) disposeTree(this.model.root);
    if (this.reference) disposeTree(this.reference);
    this.plan = plan;
    this.model = buildModel(plan);
    this.scene.add(this.model.root);
    this.bounds = new THREE.Box3().setFromObject(this.model.root);
    const center = this.bounds.getCenter(new THREE.Vector3());
    const span = Math.max(1, this.bounds.getSize(new THREE.Vector3()).length());
    this.reference = new THREE.Group();
    const gridSize = Math.max(12, 2 * Math.ceil(span));
    this.grid = new THREE.GridHelper(gridSize, Math.min(100, gridSize), 0xc7cfc4, 0xd7ddd3);
    this.grid.material.toneMapped = false;
    this.grid.position.set(Math.round(center.x),this.bounds.min.y - 0.003,Math.round(center.z));
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(span*12,span*12), new THREE.ShadowMaterial({opacity:0.18}));
    ground.rotation.x = -Math.PI/2;
    ground.position.set(center.x,this.bounds.min.y - 0.009,center.z);
    ground.receiveShadow = true;
    this.reference.add(ground,this.grid);
    this.scene.add(this.reference);
    this.sun.target.position.copy(center);
    this.sun.position.copy(center).add(new THREE.Vector3(-0.6,1.5,0.7).multiplyScalar(span));
    Object.assign(this.sun.shadow.camera,{left:-span,right:span,top:span,bottom:-span,near:0.02,far:span*5});
    this.sun.shadow.camera.updateProjectionMatrix();
    this.camera.near = Math.max(0.002,span/4000);
    this.camera.far = span*100;
    this.controls.minDistance = span*0.065;
    this.controls.maxDistance = span*18;
    this.cut = false;
    this.display(state);
    this.view("iso");
  }

  display(state) {
    if (this.cut !== state.cut) {
      disposeTree(this.model.root);
      this.model = buildModel(this.plan, state.cut);
      this.scene.add(this.model.root);
      this.cut = state.cut;
    }
    for (const [key,layer] of Object.entries(this.model.layers)) layer.visible = state[key];
    this.grid.visible = state.grid;
    this.invalidate();
  }

  view(preset = "iso") {
    this.preset = preset;
    const fit = frameBounds(this.bounds,this.camera.aspect,this.camera.fov,preset === "top");
    this.camera.position.copy(fit.position);
    this.controls.target.copy(fit.center);
    this.camera.updateProjectionMatrix();
    this.controls.update();
    this.invalidate();
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.frame);
    this.observer.disconnect();
    this.abort.abort();
    this.controls.dispose();
    if (this.model) disposeTree(this.model.root);
    if (this.reference) disposeTree(this.reference);
    this.sun.shadow.dispose();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
    this.renderer.domElement.remove();
  }
}
