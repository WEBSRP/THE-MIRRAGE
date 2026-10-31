import { rotate, TAU, type Vec3 } from './sceneMath';

export type CoreLayer = 'shell' | 'nucleus' | 'orbit';
export type CoreLine = { from: Vec3; to: Vec3; layer: CoreLayer };
export type CoreGeometry = { lines: CoreLine[]; dust: Vec3[] };

export function orbitalPoint(angle: number, orbit: number): Vec3 {
  return rotate(
    { x: Math.cos(angle) * 1.12, y: Math.sin(angle) * 1.12, z: 0 },
    { pitch: orbit === 0 ? 0.9 : -0.72, yaw: orbit === 0 ? -0.45 : 0.8 },
  );
}

function createGeometry(simple: boolean): CoreGeometry {
  const lines: CoreLine[] = [];
  const dust: Vec3[] = [];
  const trace = (count: number, sample: (angle: number) => Vec3, layer: CoreLayer) => {
    for (let index = 0; index < count; index += 1) {
      lines.push({ from: sample(index / count * TAU), to: sample((index + 1) / count * TAU), layer });
    }
  };

  const torus = (u: number, v: number) => rotate({
    x: (0.66 + 0.19 * Math.cos(v)) * Math.cos(u),
    y: (0.66 + 0.19 * Math.cos(v)) * Math.sin(u),
    z: 0.19 * Math.sin(v),
  }, { pitch: 0.65, yaw: -0.2 });

  const shellRings = simple ? 5 : 7;
  for (let index = 0; index < shellRings; index += 1) {
    trace(simple ? 40 : 56, (angle) => torus(angle, index / shellRings * TAU), 'shell');
  }
  const ribs = simple ? 8 : 12;
  for (let index = 0; index < ribs; index += 1) {
    trace(simple ? 12 : 16, (angle) => torus(index / ribs * TAU, angle), 'shell');
  }

  const meridians = simple ? 4 : 6;
  for (let index = 0; index < meridians; index += 1) {
    trace(simple ? 24 : 32, (angle) => ({
      x: Math.cos(angle) * Math.cos(index / meridians * Math.PI) * 0.33,
      y: Math.sin(angle) * 0.33,
      z: Math.cos(angle) * Math.sin(index / meridians * Math.PI) * 0.33,
    }), 'nucleus');
  }
  for (const latitude of [-0.55, 0, 0.55]) {
    trace(simple ? 24 : 32, (angle) => ({
      x: Math.cos(angle) * Math.cos(latitude) * 0.33,
      y: Math.sin(latitude) * 0.33,
      z: Math.sin(angle) * Math.cos(latitude) * 0.33,
    }), 'nucleus');
  }
  for (let orbit = 0; orbit < 2; orbit += 1) {
    trace(simple ? 56 : 80, (angle) => orbitalPoint(angle, orbit), 'orbit');
  }

  // Deterministic Fibonacci distribution: no random noise or hydration mismatch.
  const count = simple ? 22 : 42;
  for (let index = 0; index < count; index += 1) {
    const y = 1 - (index + 0.5) / count * 2;
    const radius = Math.sqrt(1 - y * y);
    const angle = index * 2.3999632297;
    dust.push({ x: Math.cos(angle) * radius * 1.03, y: y * 1.03, z: Math.sin(angle) * radius * 1.03 });
  }
  return { lines, dust };
}

// Geometry is shared between mounts and never rebuilt on animation frames.
export const coreGeometry = createGeometry(false);
export const simpleCoreGeometry = createGeometry(true);
