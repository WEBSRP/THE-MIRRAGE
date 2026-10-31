import type { Vec3 } from './sceneMath';

export type NetworkNode = Vec3 & {
  id: string;
  label: string;
  type: string;
  ip: string;
  status: 'online' | 'watch' | 'quiet';
};

export const networkNodes: NetworkNode[] = [
  { id: 'gateway', label: 'edge-gateway', type: 'Network device', ip: '10.42.0.1', status: 'online', x: 0, y: 0, z: -0.24 },
  { id: 'proxy', label: 'quiet-proxy', type: 'Web service', ip: '10.42.0.11', status: 'watch', x: -0.94, y: -0.64, z: 0.48 },
  { id: 'ghost', label: 'ghost-subnet', type: 'Target host', ip: '10.42.0.18', status: 'online', x: 0.86, y: -0.69, z: -0.38 },
  { id: 'vault', label: 'artifact-vault', type: 'Storage node', ip: '10.42.0.32', status: 'quiet', x: -0.78, y: 0.7, z: -0.5 },
  { id: 'telemetry', label: 'telemetry', type: 'Observer', ip: '10.42.0.44', status: 'online', x: 0.92, y: 0.64, z: 0.48 },
];

export type NetworkEdge = readonly [string, string];
export const networkEdges: NetworkEdge[] = [
  ['gateway', 'proxy'],
  ['gateway', 'ghost'],
  ['gateway', 'vault'],
  ['gateway', 'telemetry'],
  ['proxy', 'vault'],
  ['ghost', 'telemetry'],
];

export const nodeById = new Map(networkNodes.map((node) => [node.id, node]));

export function isIncident(edge: NetworkEdge, selectedId: string) {
  return edge[0] === selectedId || edge[1] === selectedId;
}

export function neighborsOf(id: string) {
  return networkEdges
    .filter((edge) => isIncident(edge, id))
    .map(([from, to]) => nodeById.get(from === id ? to : from)!);
}
