import type { Palette } from '../types';
import { coreGeometry, orbitalPoint, simpleCoreGeometry, type CoreLayer } from './coreGeometry';
import { clamp, project, scalePoint, type Camera, type ProjectedPoint } from './sceneMath';
import type { SceneFrame } from './useCanvasScene';

export type CoreAnimation = { time: number; expansion: number; pulse: number };
type CoreOptions = {
  camera: Camera & { parallaxX: number; parallaxY: number; dragging: boolean };
  palette: Palette;
  depth: boolean;
  motion: boolean;
  paused: boolean;
  active: boolean;
  intensity: number;
};
type Stroke = { kind: 'line'; from: ProjectedPoint; to: ProjectedPoint; z: number; layer: CoreLayer };
type Particle = { kind: 'particle'; point: ProjectedPoint; z: number; bright: boolean };

export function renderCore(frame: SceneFrame, animation: CoreAnimation, options: CoreOptions) {
  const { context: ctx, width, height, delta, lowPower } = frame;
  const { palette, camera, depth, motion, paused, active, intensity } = options;
  const moving = motion && !paused;
  const step = delta * intensity;
  if (moving && !camera.dragging) animation.time += step;
  if (moving) {
    animation.expansion += ((active ? 1 : 0) - animation.expansion) * (1 - Math.exp(-step * 5));
    animation.pulse = Math.max(0, animation.pulse - step * 0.75);
  } else {
    animation.expansion = active ? 1 : 0;
    animation.pulse = 0;
  }

  const view = {
    pitch: camera.pitch + Math.sin(animation.time * 0.19) * 0.07 + (moving ? camera.parallaxY * intensity : 0),
    yaw: camera.yaw + animation.time * 0.085 + (moving ? camera.parallaxX * intensity : 0),
  };
  const unit = Math.min(width, height) * 0.335;
  const toScreen = (point: { x: number; y: number; z: number }) => project(point, view, depth, width, height, unit);
  const geometry = lowPower ? simpleCoreGeometry : coreGeometry;
  const expansion: Record<CoreLayer, number> = {
    nucleus: 1 + animation.expansion * 0.08,
    shell: 1 + animation.expansion * 0.23,
    orbit: 1 + animation.expansion * 0.12,
  };
  const primitives: Array<Stroke | Particle> = [];

  for (const line of geometry.lines) {
    const from = toScreen(scalePoint(line.from, expansion[line.layer]));
    const to = toScreen(scalePoint(line.to, expansion[line.layer]));
    primitives.push({ kind: 'line', from, to, z: (from.z + to.z) / 2, layer: line.layer });
  }
  for (const point of geometry.dust) {
    const screen = toScreen(scalePoint(point, 1 + animation.expansion * 0.3));
    primitives.push({ kind: 'particle', point: screen, z: screen.z, bright: false });
  }
  for (let orbit = 0; orbit < 2; orbit += 1) {
    for (let index = 0; index < 3; index += 1) {
      const point = toScreen(scalePoint(
        orbitalPoint(animation.time * (orbit === 0 ? 0.22 : -0.16) + index * 2.094 + orbit, orbit),
        expansion.orbit,
      ));
      primitives.push({ kind: 'particle', point, z: point.z, bright: true });
    }
  }

  const glow = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, unit * 1.4);
  glow.addColorStop(0, palette.lime);
  glow.addColorStop(1, 'transparent');
  ctx.globalAlpha = active ? 0.065 : 0.035;
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  // Painter's algorithm applies to both mesh segments and orbiting particles.
  primitives.sort((a, b) => b.z - a.z);
  ctx.lineCap = 'round';
  for (const primitive of primitives) {
    const front = depth ? clamp((1.35 - primitive.z) / 2.7, 0, 1) : 0.55;
    if (primitive.kind === 'line') {
      const { from, to, layer } = primitive;
      ctx.strokeStyle = layer === 'orbit' ? palette.blue : layer === 'nucleus' ? palette.white : palette.lime;
      ctx.globalAlpha = layer === 'orbit' ? 0.12 + front * 0.43 : layer === 'nucleus' ? 0.1 + front * 0.28 : 0.08 + front * 0.52;
      ctx.lineWidth = layer === 'orbit' ? 0.8 + front * 0.45 : 0.55 + front * 0.4;
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.stroke();
    } else {
      const { point, bright } = primitive;
      ctx.fillStyle = bright ? palette.blue : palette.lime;
      if (bright) {
        ctx.globalAlpha = 0.08 + front * 0.06;
        ctx.beginPath();
        ctx.arc(point.x, point.y, 6 * point.scale, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = bright ? 0.9 : 0.18 + front * 0.55;
      ctx.beginPath();
      ctx.arc(point.x, point.y, (bright ? 1.9 : 0.9) * point.scale, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  if (moving && animation.pulse > 0) {
    ctx.strokeStyle = palette.lime;
    ctx.globalAlpha = animation.pulse * 0.23;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(width / 2, height / 2, unit * (1.1 + (1 - animation.pulse) * 0.35),
      unit * (0.65 + (1 - animation.pulse) * 0.35), -0.3, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}
