import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Box3, Vector3, PerspectiveCamera } from "three";
import { preparePlan, boxOnWall, solidBands, wallFrame, toWorld, SLAB } from "../../frontend/viewer/geometry.js";
import { frameBounds } from "../../frontend/viewer/camera.js";

const read = name => JSON.parse(readFileSync(new URL("../../data/"+name,import.meta.url)));
const simple=read("examples/simple_floorplan.json");
const room={id:"r",x:2,y:-3,w:4,h:3};
const wall={id:"w",x1:3,y1:2,x2:7,y2:2,thickness:.15};
const approx = (a,b) => assert.ok(Math.abs(a-b)<1e-8, a+" ≠ "+b);
test("coordinate order and southwest origin",()=>assert.deepEqual(toWorld(-2,3,1.75),[-2,1.75,-3]));
test("room footprint, finished floor and reference dimensions",()=>{
  const plan=preparePlan(simple);
  assert.equal(plan.floors.length,2);
  for(const floor of plan.floors){
    assert.deepEqual(floor.size,[3.84,SLAB,3.8]);
    approx(floor.position[1]+SLAB/2,0);
    approx(floor.area,14.592);
  }
  approx(plan.floors[0].position[0],3.02);
  approx(plan.floors[1].position[0],6.98);
  approx(plan.floors[0].position[2],-3);
  assert.equal(plan.height,2.7);
  for(const w of plan.walls) assert.equal(w.thickness,w.exterior?.20:.12);
});
test("arbitrary straight axes and reversed endpoints retain signed orientation",()=>{
  for(const [x2,y2] of [[6,6],[0,-2],[3,7],[-1,2]]){
    const w={...wall,x2,y2}, f=wallFrame(w);
    approx(f.length,Math.hypot(x2-3,y2-2));
    approx(Math.cos(f.angle),f.ux); approx(Math.sin(f.angle),f.uy);
    const box=boxOnWall({...w,...f},0,f.length,0,3.2);
    assert.deepEqual(box.size,[f.length,3.2,.15]);
    approx(box.position[0],(3+x2)/2); approx(box.position[2],-(2+y2)/2);
  }
});
test("simple house entrance, partition and reversed north window intervals",()=>{
  const {walls}=preparePlan(simple);
  const centers=walls.flatMap(w=>w.openings.map(o=>{
    const box=boxOnWall(w,o.offset,o.offset+o.width,o.sill,o.sill+o.height);
    return [o.id,...box.position];
  }));
  const expected=[["entrance",2.25,1.05,-1],["bed-window",7.25,1.5,-5],
    ["living-window",3.25,1.5,-5],["interior",5,1.05,-2.825]];
  for(const [i,center] of centers.entries()){
    assert.equal(center[0],expected[i][0]);
    center.slice(1).forEach((v,j)=>approx(v,expected[i][j+1]));
  }
});
test("corner and T junction faces meet without moving the aperture offsets",()=>{
  const {walls}=preparePlan(simple);
  const [south,east,,,partition]=walls;
  approx(south.start,-.1); approx(south.end,8.1);
  approx(east.start,.1); approx(east.end,3.9);
  approx(partition.start,.1); approx(partition.end,3.9);
  approx(partition.openings[0].offset,1.4);
});

function verifyWall(w,height) {
  const solids=solidBands(w.start,w.end,height,w.openings);
  let volume=0;
  for(const {a,b,bottom,top} of solids){
    assert.ok(b>a && top>bottom && a>=w.start && b<=w.end && bottom>=0 && top<=height);
    volume+=(b-a)*(top-bottom)*w.thickness;
    for(const o of w.openings){
      const along=Math.min(b,o.offset+o.width)-Math.max(a,o.offset);
      const up=Math.min(top,o.sill+o.height)-Math.max(bottom,o.sill);
      assert.ok(Math.min(along,up)<1e-8,"Solid occupies "+o.id);
    }
  }
  const empty=w.openings.reduce((s,o)=>s+o.width*Math.max(0,Math.min(height,o.sill+o.height)-o.sill),0);
  approx(volume,((w.end-w.start)*height-empty)*w.thickness);
}
for(const name of ["examples/simple_floorplan.json","examples/residential_floorplan.json","example_plan.json"]){
  test("voids and remaining wall volume, full height and cutaway: "+name,()=>{
    const raw=read(name), snapshot=JSON.stringify(raw);
    const plan=preparePlan(raw);
    for(const w of plan.walls) for(const cap of [plan.height,.85]) verifyWall(w,cap);
    assert.equal(JSON.stringify(raw),snapshot);
  });
}
test("door, window sill and lintel intervals plus stacked openings",()=>{
  const holes=[{id:"door",offset:.3,width:.8,sill:0,height:2.0},
    {id:"window",offset:2,width:1,sill:.7,height:.8},{id:"transom",offset:2,width:1,sill:1.9,height:.5}];
  const pieces=solidBands(0,4,3,holes);
  assert.deepEqual(pieces.filter(p=>p.a===2&&p.b===3).map(p=>[p.bottom,p.top]),[[0,.7],[1.5,1.9],[2.4,3]]);
  assert.deepEqual(pieces.filter(p=>p.a===.3).map(p=>[p.bottom,p.top]),[[2,3]]);
  verifyWall({start:0,end:4,thickness:.3,openings:holes},3);
});
test("floor-only legacy plan and walls without openings",()=>{
  const legacy=preparePlan({rooms:[room]});
  assert.equal(legacy.walls.length,0);
  assert.deepEqual(legacy.floors[0].position,[4,-SLAB/2,1.5]);
  const w=preparePlan({rooms:[room],walls:[wall],wall_height:4}).walls[0];
  assert.deepEqual(solidBands(0,w.length,4,[]),[{a:0,b:4,bottom:0,top:4}]);
});
test("bad coordinates, references, unknown scale, out-of-wall heights and offsets are rejected",()=>{
  for(const plan of [{rooms:[]},{rooms:[{...room,x:NaN}]},{rooms:[room],unit:"px"},
    {rooms:[room],source:"imported"},{rooms:[room],walls:[{...wall,x2:3}]},
    ...[{wall_id:"unknown"},{offset:4},{sill:2.5}].map(change=>({rooms:[room],walls:[wall],
      openings:[{kind:"door",id:"d",wall_id:"w",width:1,offset:0,...change}]}))]){
    assert.throws(()=>preparePlan(plan));
  }
});
test("perspective camera includes every corner at desktop and phone aspect ratios",()=>{
  for(const box of [new Box3(new Vector3(-3,-SLAB,-8),new Vector3(12,2.7,-2)),
    new Box3(new Vector3(132,-SLAB,67),new Vector3(134,4,101))]){
    for(const aspect of [.62,1.6,3]) for(const top of [true,false]){
      const fit=frameBounds(box,aspect,37,top);
      const camera=new PerspectiveCamera(37,aspect,.001,2000);
      camera.position.copy(fit.position); camera.lookAt(fit.center); camera.updateMatrixWorld();
      for(const x of [box.min.x,box.max.x]) for(const y of [box.min.y,box.max.y]) for(const z of [box.min.z,box.max.z]){
        const p=new Vector3(x,y,z).project(camera);
        assert.ok(Math.abs(p.x)<.82 && Math.abs(p.y)<.82 && Math.abs(p.z)<1);
      }
    }
  }
});
