// Start FastAPI first. Use BROWSER_CHANNEL=chrome or BROWSER_EXECUTABLE for another Chromium.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright-core";

const baseURL = process.env.ARCHIGEN_URL || "http://127.0.0.1:8000";
const output = ".local-review/screenshots";
await mkdir(output, { recursive:true });
const browser = await chromium.launch({ headless:true,
  channel:process.env.BROWSER_CHANNEL || "msedge", executablePath:process.env.BROWSER_EXECUTABLE,
  args:["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"] });
try {
  const page = await browser.newPage({baseURL,viewport:{width:1360,height:920},deviceScaleFactor:1});
  const errors = [], missing = [], external = [];
  page.on("console", msg => {if(msg.type()==="error") errors.push(msg.text());});
  page.on("pageerror", err => errors.push(err.message));
  page.on("response", res => {if(res.status()>=400) missing.push([res.status(),res.url()]);});
  page.on("request", req => { if (/^https?:/.test(req.url()) && new URL(req.url()).origin !== new URL(baseURL).origin) external.push(req.url()); });
  const viewer = page.locator("#view3d");
  const canvas = viewer.locator("canvas");
  const sceneReady = () => page.waitForSelector('#view3d[data-state="ready"] canvas');
  const paint = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const shot = async name => {await paint(); await viewer.screenshot({path:output+"/"+name+".png"});};
  async function load(key,rooms) {
    await page.selectOption("#viewer-example",key);
    await page.waitForFunction(n => document.querySelectorAll("#plan-view rect").length===n,rooms);
    await sceneReady(); await paint();
    assert.equal(await canvas.count(),1);
  }
  await page.goto("/");
  assert.equal(await viewer.getAttribute("data-state"),"empty");
  await load("simple",2);
  const firstCanvas = await canvas.elementHandle();
  assert.equal(await canvas.evaluate(c=>!!c.getContext("webgl2")),true);
  await shot("01-simple-oblique");
  await page.click('[data-view="top"]');
  await shot("02-simple-dessus");
  await page.click('[data-view="reset"]');
  async function changed(action) {
    const prior=await canvas.screenshot();
    await action(); await paint();
    assert.ok(!prior.equals(await canvas.screenshot()),"Canvas pixels must change after interaction");
  }
  async function drag(button,dx,dy) {
    const b=await canvas.boundingBox(), x=b.x+b.width/2, y=b.y+b.height/2;
    await page.mouse.move(x,y);
    await page.mouse.down({button}); await page.mouse.move(x+dx,y+dy,{steps:8}); await page.mouse.up({button});
  }
  await changed(()=>drag("left",110,24));
  await changed(()=>drag("right",70,-15));
  await changed(()=>page.mouse.wheel(0,-150));
  await changed(()=>page.click('[data-view="reset"]'));
  for(const layer of ["exterior","interior","floors","grid","cut"]) {
    await changed(()=>page.locator('[data-layer="'+layer+'"]').click());
    await page.locator('[data-layer="'+layer+'"]').click();
  }
  await load("residential",6);
  await shot("03-residentiel-oblique");
  await page.click('[data-view="top"]'); await shot("04-residentiel-dessus");
  await page.click('[data-view="iso"]');
  await page.check('[data-layer="cut"]'); await shot("07-residentiel-coupe");
  await page.uncheck('[data-layer="cut"]');
  await load("historical",5);
  await drag("left",38,-28);
  await canvas.hover();
  await page.mouse.wheel(0,-1000); await paint();
  await shot("05-baies-detail");
  await page.click('[data-tab="thermal"]');
  await page.click("#btn-thermal-plan");
  await page.waitForSelector("#thermal-result .warnings li");
  assert.equal(await page.locator("#thermal-result .warnings li").count(),4);
  await page.click('[data-tab="quality"]'); await page.waitForSelector("#metrics table");
  await page.click('[data-tab="manual"]'); await page.click("#btn-manual");
  await page.waitForSelector("#manual-result .metric");
  await page.click('[data-tab="design"]');
  await load("simple",2); await load("residential",6); await load("simple",2);
  assert.ok(await firstCanvas.evaluate(el=>el===document.querySelector("#view3d canvas")));
  await page.screenshot({path:output+"/06-interface.png",fullPage:true});
  await page.setViewportSize({width:390,height:844}); await paint();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth));
  await shot("08-mobile");
  const raw={rooms:[{id:"solo",x:100,y:90,w:4,h:3}]};
  await page.fill("#plan-json",JSON.stringify(raw)); await page.click("#btn-validate");
  await page.waitForSelector('#view3d[data-state=ready] [role=status]:not(:empty)');
  assert.match(await viewer.locator("[role=status]").innerText(),/Aucun mur/);
  await page.evaluate(()=>document.dispatchEvent(new CustomEvent("plan-changed",{detail:{rooms:[]}})));
  assert.equal(await viewer.getAttribute("data-state"),"error");
  assert.equal(await canvas.count(),0);
  await load("simple",2);
  // Les producteurs futurs utilisent les handlers existants. Seule leur réponse HTTP est simulée.
  const candidate = await (await page.request.get("/assets/examples/residential_floorplan.json")).json();
  await page.route("**/api/plan/generate", route => route.fulfill({json:{plan:{...candidate,source:"generated"},seconds:0}}));
  await page.fill("#nl-text","Maison résidentielle"); await page.click("#btn-generate");
  await page.waitForFunction(()=>document.querySelectorAll("#plan-view rect").length===6);
  await sceneReady();
  const imported = { ...candidate, source:"imported", plan_id:"calibrated-fixture", import_metadata:{
    image_width_px:1200,image_height_px:900,meters_per_pixel:.01,scale_status:"calibrated",scale_provenance:"Cote de test"} };
  await page.route("**/api/plan/import", route => route.fulfill({json:{plan:imported,seconds:0}}));
  await page.locator("#img-file").setInputFiles({name:"fixture.png",mimeType:"image/png",buffer:Buffer.from("fixture")});
  await page.click("#btn-import");
  await page.waitForFunction(()=>JSON.parse(document.querySelector("#plan-json").value).plan_id==="calibrated-fixture");
  await sceneReady();
  assert.equal(await canvas.count(),1);
  assert.deepEqual(errors,[]); assert.deepEqual(missing,[]); assert.deepEqual(external,[]);
  assert.equal((await page.request.get("/api/health")).status(),200);
  assert.equal((await page.request.get("/api/thermal/domain")).status(),200);
  const unavailable=await browser.newPage({baseURL});
  await unavailable.addInitScript(()=>{
    const get=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==="webgl2"?null:get.call(this,type,...args);};
  });
  await unavailable.goto("/?exemple=simple");
  await unavailable.waitForSelector('#view3d[data-state="error"]');
  assert.match(await unavailable.locator("#view3d [role=status]").innerText(),/WebGL/);
  assert.equal(await unavailable.locator("#plan-view rect").count(),2);
  console.log("Desktop/mobile, 3 references, orbit/pan/zoom, presets, 5 layers, reloads, errors, WebGL fallback, thermal and local assets passed.");
} finally { await browser.close(); }
