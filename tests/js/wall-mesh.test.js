import assert from "node:assert/strict";
import test from "node:test";
import { Mesh, MeshBasicMaterial, Raycaster, Vector3 } from "three";
import { solidBands } from "../../frontend/viewer/geometry.js";
import { wallMeshGeometry } from "../../frontend/viewer/wall-mesh.js";

test("rays pass through actual door and window triangles, hit sill, lintel and jamb",()=>{
  const holes=[{offset:.5,width:1,sill:0,height:2.1},{offset:2,width:1,sill:.9,height:1.2}];
  const mesh=new Mesh(wallMeshGeometry(solidBands(0,4,2.7,holes),.2),new MeshBasicMaterial());
  const hits=(origin,direction)=>new Raycaster(new Vector3(...origin),new Vector3(...direction)).intersectObject(mesh);
  for(const [x,h,solid] of [[.9,1,false],[2.3,1.3,false],[2.3,.8,true],[1,2.4,true],[2.7,2.3,true]]){
    assert.equal(hits([x,h,1],[0,0,-1]).length>0,solid);
    assert.equal(hits([x,h,-1],[0,0,1]).length>0,solid);
  }
  const jamb=hits([1,1,0],[1,0,0])[0];
  assert.ok(Math.abs(jamb.point.x-1.5)<1e-6);
  mesh.geometry.computeBoundingBox();
  assert.ok(Math.abs(mesh.geometry.boundingBox.max.z-.1)<1e-6);
  mesh.geometry.dispose(); mesh.material.dispose();
});
