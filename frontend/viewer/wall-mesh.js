import { BufferGeometry, Float32BufferAttribute } from "three";

// Parement fermé à partir des bandes solides. Aux jonctions de bandes,
// émettre seulement les portions de tableau qui donnent sur un vide.
export function wallMeshGeometry(bands, thickness) {
  const positions = [], d = thickness / 2;
  const left = new Map(), right = new Map();
  for (const band of bands) {
    for (const [map,key] of [[left,band.a],[right,band.b]]) {
      if (!map.has(key)) map.set(key,[]);
      map.get(key).push(band);
    }
  }
  function quad(a,b,c,e) { positions.push(...a,...b,...c, ...a,...c,...e); }
  function jamb(x, bottom, top, neighbors, end) {
    function face(lo, hi) {
      if (hi <= lo) return;
      const z = end ? d : -d;
      quad([x,lo,z],[x,lo,-z],[x,hi,-z],[x,hi,z]);
    }
    let cursor = bottom;
    for (const neighbor of neighbors ?? []) {
      if (neighbor.top <= cursor || neighbor.bottom >= top) continue;
      face(cursor,Math.min(neighbor.bottom,top));
      cursor = Math.max(cursor, neighbor.top);
    }
    face(cursor,top);
  }
  for (const {a,b,bottom:l,top:h} of bands) {
    quad([a,l,d],[b,l,d],[b,h,d],[a,h,d]);
    quad([b,l,-d],[a,l,-d],[a,h,-d],[b,h,-d]);
    quad([a,h,d],[b,h,d],[b,h,-d],[a,h,-d]);
    quad([a,l,-d],[b,l,-d],[b,l,d],[a,l,d]);
    jamb(a,l,h,right.get(a),false);
    jamb(b,l,h,left.get(b),true);
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute("position",new Float32BufferAttribute(positions,3));
  geometry.computeVertexNormals();
  return geometry;
}
