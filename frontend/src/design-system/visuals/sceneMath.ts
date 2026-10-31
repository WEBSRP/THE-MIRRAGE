export type Vec3 = { x: number; y: number; z: number };
export type ProjectedPoint = Vec3 & { scale: number };
export type Camera = { pitch: number; yaw: number };

export const TAU = Math.PI * 2;
export const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

export function rotate(point: Vec3, camera: Camera): Vec3 {
  const cy = Math.cos(camera.yaw);
  const sy = Math.sin(camera.yaw);
  const cx = Math.cos(camera.pitch);
  const sx = Math.sin(camera.pitch);
  const x = point.x * cy + point.z * sy;
  const z = point.z * cy - point.x * sy;
  return { x, y: point.y * cx - z * sx, z: point.y * sx + z * cx };
}

/** Flat mode deliberately ignores both the camera and source Z, including perspective scale. */
export function project(
  point: Vec3,
  camera: Camera,
  depth: boolean,
  width: number,
  height: number,
  unit: number,
): ProjectedPoint {
  const view = depth ? rotate(point, camera) : { x: point.x, y: point.y, z: 0 };
  const scale = depth ? 4.5 / Math.max(1, 4.5 + view.z) : 1;
  return {
    x: width / 2 + view.x * unit * scale,
    y: height / 2 + view.y * unit * scale,
    z: view.z,
    scale,
  };
}

export function mixPoint(a: Vec3, b: Vec3, amount: number): Vec3 {
  return {
    x: a.x + (b.x - a.x) * amount,
    y: a.y + (b.y - a.y) * amount,
    z: a.z + (b.z - a.z) * amount,
  };
}

export function scalePoint(point: Vec3, amount: number): Vec3 {
  return { x: point.x * amount, y: point.y * amount, z: point.z * amount };
}

export type HitTarget = ProjectedPoint & { id: string; radius: number };

/** Choose the nearest screen-space target; use depth to break overlapping ties. */
export function hitTest(points: HitTarget[], x: number, y: number): string | null {
  const hits = points
    .map((point) => ({ point, distance: Math.hypot(point.x - x, point.y - y) }))
    .filter(({ point, distance }) => distance <= Math.max(24, point.radius + 8))
    .sort((a, b) => a.distance - b.distance || a.point.z - b.point.z);
  return hits[0]?.point.id ?? null;
}
