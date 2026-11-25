import { Vector3, MathUtils } from "three";

export function frameBounds(box, aspect, fov, top = false) {
  const center = box.getCenter(new Vector3());
  // Infime décalage au zénith pour conserver le nord local en haut et l'orbite Y.
  const eye = top ? new Vector3(0, 1, 0.00001) : new Vector3(0.66, 0.94, 1);
  eye.normalize();
  const right = new Vector3().crossVectors(new Vector3(0, 1, 0), eye).normalize();
  const up = new Vector3().crossVectors(eye, right);
  const tan = Math.tan(MathUtils.degToRad(fov / 2));
  let distance = 0;
  for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) {
    for (const z of [box.min.z, box.max.z]) {
      const corner = new Vector3(x, y, z).sub(center);
      const clearance = Math.max(Math.abs(corner.dot(up)), Math.abs(corner.dot(right)) / aspect);
      distance = Math.max(distance, corner.dot(eye) + 1.23 * clearance / tan);
    }
  }
  return {center, distance, position: eye.multiplyScalar(distance).add(center)};
}
