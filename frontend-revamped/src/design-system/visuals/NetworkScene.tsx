import { useId, useRef, useState } from 'react';
import { isIncident, neighborsOf, networkEdges, networkNodes, nodeById } from './networkGeometry';
import { renderNetwork, type NetworkAnimation } from './renderNetwork';
import { hitTest } from './sceneMath';
import { useCanvasScene } from './useCanvasScene';
import { createSceneCamera, useSceneCamera } from './useSceneCamera';
import { useScenePreferences } from './useScenePreferences';

const INITIAL_CAMERA = { pitch: -0.16, yaw: 0.2 };

export function NetworkScene({ compact }: { compact: boolean }) {
  const preferences = useScenePreferences();
  const [spatial, setSpatial] = useState(true);
  const [paused, setPaused] = useState(false);
  const [inspecting, setInspecting] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [selectedId, setSelectedId] = useState('gateway');
  const helpId = useId();
  const detailId = useId();
  const titleId = useId();
  const cameraRef = useRef(createSceneCamera(INITIAL_CAMERA));
  const animation = useRef<NetworkAnimation>({ time: 0, hovered: null, targets: [] });
  const depth = preferences.depth && spatial;
  const moving = preferences.motion && depth && !paused && !inspecting;
  const selected = nodeById.get(selectedId)!;
  const neighbors = neighborsOf(selectedId);

  const { canvasRef, viewportRef, supported, invalidate } = useCanvasScene((frame) => {
    renderNetwork(frame, animation.current, {
      ...preferences,
      camera: cameraRef.current,
      depth,
      moving,
      zoom: zoom / 100,
      selectedId,
      compact,
    });
  }, { automatic: moving, compact });

  const navigation = useSceneCamera({
    cameraRef,
    initial: INITIAL_CAMERA,
    interactive: preferences.motion && depth && supported !== false,
    invalidate,
    yawLimit: 0.9,
    onTap: (x, y) => {
      if (supported === false) return;
      const id = hitTest(animation.current.targets, x, y);
      if (id) setSelectedId(id);
    },
    onHover: (x, y) => {
      if (supported === false) return;
      const id = hitTest(animation.current.targets, x, y);
      if (id !== animation.current.hovered) {
        animation.current.hovered = id;
        invalidate();
      }
    },
    onLeave: () => { animation.current.hovered = null; },
  });

  const reset = () => {
    animation.current.time = 0;
    animation.current.hovered = null;
    setZoom(100);
    setSelectedId('gateway');
    navigation.reset();
  };
  const unavailable = supported === false;
  const help = unavailable ? 'Canvas unavailable · select a node below to inspect the static topology.'
    : !depth ? 'Planar view · select a node to trace its connections.'
      : !preferences.motion ? `${preferences.motionReason} · select a node to inspect.`
        : paused ? 'Orbit paused · drag to rotate or select a node to inspect.'
          : 'Drag or use arrow keys to rotate · select a node to trace its connections.';

  return (
    <section className={`mxv-network${compact ? ' mxv-network--compact' : ''}`} aria-labelledby={titleId}>
      <header className="mxv-network-header">
        <div>
          <span className="mxv-eyebrow">Network topology / simulated</span>
          <h3 id={titleId}>{compact ? 'Trace the surface.' : 'Every signal has a source.'}</h3>
        </div>
        <fieldset className="mxv-controls" aria-label="Network view controls">
          <button
            type="button"
            className="mxv-button"
            onClick={reset}
            aria-label="Reset network camera and selection"
          >Reset</button>
          <button
            type="button"
            className="mxv-button mxv-button--square"
            disabled={zoom <= 75 || unavailable}
            onClick={() => setZoom((value) => Math.max(75, value - 10))}
            aria-label="Zoom network out"
          >−</button>
          <output className="mxv-zoom" aria-label="Network zoom">{zoom}%</output>
          <button
            type="button"
            className="mxv-button mxv-button--square"
            disabled={zoom >= 140 || unavailable}
            onClick={() => setZoom((value) => Math.min(140, value + 10))}
            aria-label="Zoom network in"
          >+</button>
          <button
            type="button"
            className="mxv-button"
            aria-label="3D network view"
            aria-pressed={depth && !unavailable}
            disabled={!preferences.depth || unavailable}
            title={!preferences.depth ? '3D disabled in Design Studio' : 'Switch between planar and spatial views'}
            onClick={() => setSpatial((value) => !value)}
          >{depth && !unavailable ? '3D' : '2D'}</button>
          <button
            type="button"
            className="mxv-button"
            aria-label={paused ? 'Resume network animation' : 'Pause network animation'}
            aria-pressed={paused}
            disabled={!preferences.motion || !depth || unavailable}
            title={preferences.motionReason || undefined}
            onClick={() => setPaused((value) => !value)}
          >{paused ? 'Resume' : 'Pause'}</button>
        </fieldset>
      </header>

      <div
        {...navigation.bindings}
        ref={viewportRef}
        className="mxv-viewport mxv-network-viewport"
        data-rotatable={preferences.motion && depth && !unavailable || undefined}
        role="group"
        aria-label={`${depth && !unavailable ? 'Spatial' : 'Planar'} network map. Five nodes and six connections.`}
        aria-describedby={helpId}
        tabIndex={unavailable ? -1 : 0}
      >
        <canvas ref={canvasRef} className="mxv-canvas" hidden={unavailable} aria-hidden="true" />
        {unavailable && <NetworkFallback selectedId={selectedId} />}
        <span className="mxv-map-caption" aria-hidden="true">
          {depth && !unavailable ? 'PERSPECTIVE' : 'ORTHOGRAPHIC'} / 05 NODES
        </span>
      </div>

      <p className="mxv-help" id={helpId}>{help}</p>
      <fieldset
        className="mxv-node-list"
        aria-label="Select a network node"
        onFocusCapture={() => setInspecting(true)}
        onBlurCapture={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setInspecting(false);
        }}
      >
        {networkNodes.map((node, index) => (
          <button
            key={node.id}
            type="button"
            className="mxv-node-button"
            aria-pressed={selectedId === node.id}
            aria-controls={detailId}
            aria-label={`Inspect ${node.label}, ${node.type}, ${node.status}`}
            onClick={() => setSelectedId(node.id)}
          >
            <span aria-hidden="true">0{index + 1}</span>{node.label}
          </button>
        ))}
      </fieldset>

      <div className="mxv-inspector" id={detailId} role="status" aria-live="polite" aria-atomic="true">
        <div className="mxv-inspector-title"><strong>{selected.label}</strong><span>{selected.status}</span></div>
        <dl className="mxv-details">
          <div><dt>Role</dt><dd>{selected.type}</dd></div>
          <div><dt>Address</dt><dd>{selected.ip}</dd></div>
          <div><dt>Links</dt><dd>{neighbors.length} direct</dd></div>
        </dl>
        <p className="mxv-connections">
          <span>Connected to</span> {neighbors.map((node) => node.label).join(' · ')}
        </p>
      </div>
    </section>
  );
}

function NetworkFallback({ selectedId }: { selectedId: string }) {
  const point = (id: string) => {
    const node = nodeById.get(id)!;
    return { x: 200 + node.x * 135, y: 130 + node.y * 110 };
  };
  return (
    <svg className="mxv-fallback" viewBox="0 0 400 260" aria-hidden="true">
      {networkEdges.map((edge) => {
        const from = point(edge[0]);
        const to = point(edge[1]);
        return (
          <line
            key={edge.join('-')}
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
            stroke="currentColor"
            opacity={isIncident(edge, selectedId) ? 0.8 : 0.16}
          />
        );
      })}
      {networkNodes.map((node) => {
        const position = point(node.id);
        return (
          <g key={node.id} transform={`translate(${position.x} ${position.y})`}>
            <circle r={node.id === selectedId ? 10 : 6} className="mxv-fallback-node" />
            <text y="26" textAnchor="middle" className="mxv-fallback-label">{node.label}</text>
          </g>
        );
      })}
    </svg>
  );
}
