import assert from 'node:assert/strict';
import test from 'node:test';
import { hitTest, mixPoint, project } from './sceneMath.ts';
import { isIncident, neighborsOf, networkEdges } from './networkGeometry.ts';

const camera = { pitch: 0.35, yaw: 0.5 };

test('flat projection ignores source depth and every camera rotation', () => {
  const expected = { x: 320, y: 260, z: 0, scale: 1 };
  for (const z of [-100, -1, 0, 1, 100]) {
    assert.deepEqual(project({ x: 0.4, y: 0.2, z }, camera, false, 400, 400, 300), expected);
    assert.deepEqual(project({ x: 0.4, y: 0.2, z }, { pitch: -2, yaw: 9 }, false, 400, 400, 300), expected);
  }
});

test('perspective uses Z for both displacement and size', () => {
  const straight = { pitch: 0, yaw: 0 };
  const near = project({ x: 1, y: 0.5, z: -1 }, straight, true, 400, 400, 100);
  const far = project({ x: 1, y: 0.5, z: 1 }, straight, true, 400, 400, 100);
  assert.ok(near.scale > far.scale);
  assert.ok(near.x > far.x && near.y > far.y);
});

test('projected intermediate edge points stay on the line between projected endpoints', () => {
  const a = { x: -0.9, y: -0.6, z: 0.5 };
  const b = { x: 0.8, y: 0.7, z: -0.5 };
  const screen = (point) => project(point, camera, true, 600, 400, 140);
  const from = screen(a);
  const to = screen(b);
  for (const amount of [0, 0.1, 0.5, 0.9, 1]) {
    const point = screen(mixPoint(a, b, amount));
    const cross = (point.x - from.x) * (to.y - from.y) - (point.y - from.y) * (to.x - from.x);
    assert.ok(Math.abs(cross) < 1e-8);
  }
});

test('selecting gateway highlights exactly its four links, never the two lateral links', () => {
  assert.equal(networkEdges.filter((edge) => isIncident(edge, 'gateway')).length, 4);
  assert.equal(isIncident(['proxy', 'vault'], 'gateway'), false);
  assert.equal(isIncident(['ghost', 'telemetry'], 'gateway'), false);
  assert.deepEqual(neighborsOf('proxy').map((node) => node.id), ['gateway', 'vault']);
});

test('hit-testing has a touch-sized target, ignores empty space, and resolves overlapping depth', () => {
  const points = [
    { id: 'far', x: 100, y: 100, z: 1, scale: 0.8, radius: 6 },
    { id: 'near', x: 100, y: 100, z: -1, scale: 1.2, radius: 9 },
  ];
  assert.equal(hitTest(points, 100, 100), 'near');
  assert.equal(hitTest(points, 122, 100), 'near');
  assert.equal(hitTest(points, 130, 100), null);
});
