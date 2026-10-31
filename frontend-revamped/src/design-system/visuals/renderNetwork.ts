import type { Palette } from '../types';
import { isIncident, networkEdges, networkNodes, nodeById, type NetworkNode } from './networkGeometry';
import { clamp, mixPoint, project, type Camera, type HitTarget, type ProjectedPoint } from './sceneMath';
import type { SceneFrame } from './useCanvasScene';

export type NetworkAnimation = { time: number; hovered: string | null; targets: HitTarget[] };
type NetworkOptions = {
  camera: Camera & { parallaxX: number; parallaxY: number; dragging: boolean };
  palette: Palette;
  mono: string;
  depth: boolean;
  moving: boolean;
  intensity: number;
  zoom: number;
  selectedId: string;
  compact: boolean;
};
type EdgePrimitive = { kind: 'edge'; from: ProjectedPoint; to: ProjectedPoint; z: number; selected: boolean };
type NodePrimitive = { kind: 'node'; point: HitTarget; z: number; node: NetworkNode };
type PacketPrimitive = { kind: 'packet'; point: ProjectedPoint; z: number };

export function renderNetwork(frame: SceneFrame, animation: NetworkAnimation, options: NetworkOptions) {
  const { context: ctx, width, height, delta } = frame;
  const { palette, depth, moving, camera, intensity, selectedId, zoom, compact, mono } = options;
  if (moving && !camera.dragging) animation.time += delta * intensity;
  const view = {
    pitch: camera.pitch + Math.sin(animation.time * 0.2) * 0.035 + (moving ? camera.parallaxY * intensity : 0),
    yaw: camera.yaw + Math.sin(animation.time * 0.13) * 0.1 + (moving ? camera.parallaxX * intensity : 0),
  };
  const unit = Math.min(width * 0.29, height * 0.36) * zoom;
  const toScreen = (point: { x: number; y: number; z: number }) => project(point, view, depth, width, height, unit);
  const primitives: Array<EdgePrimitive | NodePrimitive | PacketPrimitive> = [];

  // Quiet projected reference plane. Flat mode uses XY exclusively, never a fake CSS tilt.
  ctx.strokeStyle = palette.blue;
  ctx.lineWidth = 0.6;
  ctx.globalAlpha = 0.07;
  for (let index = -3; index <= 3; index += 1) {
    const offset = index * 0.42;
    const lines = depth ? [
      [{ x: offset, y: 0.87, z: -1.26 }, { x: offset, y: 0.87, z: 1.26 }],
      [{ x: -1.26, y: 0.87, z: offset }, { x: 1.26, y: 0.87, z: offset }],
    ] : [
      [{ x: offset, y: -1.1, z: 0 }, { x: offset, y: 1.1, z: 0 }],
      [{ x: -1.26, y: offset, z: 0 }, { x: 1.26, y: offset, z: 0 }],
    ];
    for (const [a, b] of lines) {
      const from = toScreen(a);
      const to = toScreen(b);
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.stroke();
    }
  }

  for (let index = 0; index < networkEdges.length; index += 1) {
    const edge = networkEdges[index];
    const from = nodeById.get(edge[0])!;
    const to = nodeById.get(edge[1])!;
    // Selection is an edge predicate, not membership in the set of adjacent vertices.
    const selected = isIncident(edge, selectedId);
    for (let segment = 0; segment < 12; segment += 1) {
      const start = toScreen(mixPoint(from, to, segment / 12));
      const end = toScreen(mixPoint(from, to, (segment + 1) / 12));
      primitives.push({ kind: 'edge', from: start, to: end, z: (start.z + end.z) / 2, selected });
    }
    if (selected) {
      // Interpolate in world space, then project; screen-space interpolation loses Z speed.
      const point = toScreen(mixPoint(from, to, (animation.time * 0.15 + index * 0.19) % 1));
      primitives.push({ kind: 'packet', point, z: point.z });
    }
  }

  animation.targets = networkNodes.map((node) => {
    const projected = toScreen(node);
    const point = { ...projected, id: node.id, radius: (node.id === 'gateway' ? 12 : 8) * projected.scale };
    primitives.push({ kind: 'node', point, z: point.z, node });
    return point;
  });
  primitives.sort((a, b) => b.z - a.z);

  for (const primitive of primitives) {
    const front = depth ? clamp((1 - primitive.z) / 2, 0, 1) : 0.6;
    if (primitive.kind === 'edge') {
      ctx.strokeStyle = primitive.selected ? palette.lime : palette.blue;
      ctx.globalAlpha = primitive.selected ? 0.3 + front * 0.4 : 0.13;
      ctx.lineWidth = primitive.selected ? 1.2 : 0.7;
      ctx.beginPath();
      ctx.moveTo(primitive.from.x, primitive.from.y);
      ctx.lineTo(primitive.to.x, primitive.to.y);
      ctx.stroke();
    } else if (primitive.kind === 'packet') {
      ctx.fillStyle = palette.lime;
      ctx.globalAlpha = 0.85;
      ctx.beginPath();
      ctx.arc(primitive.point.x, primitive.point.y, 2 * primitive.point.scale, 0, Math.PI * 2);
      ctx.fill();
    } else {
      const { point, node } = primitive;
      const selected = node.id === selectedId;
      const highlighted = selected || node.id === animation.hovered;
      ctx.strokeStyle = highlighted ? palette.lime : palette.blue;
      ctx.fillStyle = palette.ink;
      ctx.globalAlpha = 1;
      ctx.lineWidth = selected ? 1.6 : 1;
      ctx.beginPath();
      ctx.arc(point.x, point.y, point.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      if (highlighted) {
        ctx.globalAlpha = 0.35;
        ctx.lineWidth = 0.75;
        ctx.beginPath();
        ctx.arc(point.x, point.y, point.radius + 5, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.globalAlpha = 0.9;
      ctx.fillStyle = selected ? palette.lime : palette.blue;
      ctx.beginPath();
      ctx.arc(point.x, point.y, selected ? 3 : 2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Labels are a legible screen-space annotation layer, not depth-bearing geometry.
  ctx.font = `${compact || width < 400 ? 9 : 11}px ${mono}`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (const point of animation.targets) {
    const label = nodeById.get(point.id)!.label;
    const halfWidth = ctx.measureText(label).width / 2;
    const x = clamp(point.x, halfWidth + 6, width - halfWidth - 6);
    const y = clamp(point.y + point.radius + 10, 4, height - 16);
    ctx.fillStyle = palette.ink;
    ctx.globalAlpha = 0.8;
    ctx.fillRect(x - halfWidth - 4, y - 2, halfWidth * 2 + 8, compact ? 13 : 16);
    ctx.fillStyle = point.id === selectedId ? palette.lime : palette.mutedLight;
    ctx.globalAlpha = 1;
    ctx.fillText(label, x, y);
  }
}
