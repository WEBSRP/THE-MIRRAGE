import { useId, useRef, useState } from 'react';
import { renderCore, type CoreAnimation } from './renderCore';
import { useCanvasScene } from './useCanvasScene';
import { createSceneCamera, useSceneCamera } from './useSceneCamera';
import { useScenePreferences } from './useScenePreferences';

const INITIAL_CAMERA = { pitch: -0.25, yaw: 0.35 };

export function SignalCore({ compact }: { compact: boolean }) {
  const preferences = useScenePreferences();
  const [paused, setPaused] = useState(false);
  const [active, setActive] = useState(false);
  const helpId = useId();
  const cameraRef = useRef(createSceneCamera(INITIAL_CAMERA));
  const animation = useRef<CoreAnimation>({ time: 0, expansion: 0, pulse: 0 });
  const moving = preferences.motion && !paused;

  const { canvasRef, viewportRef, supported, invalidate } = useCanvasScene((frame) => {
    renderCore(frame, animation.current, {
      ...preferences,
      camera: cameraRef.current,
      paused,
      active,
    });
  }, { automatic: moving, compact });

  const activate = () => {
    animation.current.pulse = 1;
    setActive((value) => !value);
    invalidate();
  };
  const navigation = useSceneCamera({
    cameraRef,
    initial: INITIAL_CAMERA,
    interactive: preferences.motion && supported !== false,
    invalidate,
    onTap: activate,
  });

  const reset = () => {
    animation.current = { time: 0, expansion: 0, pulse: 0 };
    setActive(false);
    navigation.reset();
  };
  const status = supported === false ? 'Static fallback' : !preferences.depth ? 'Planar study'
    : !preferences.motion ? 'Still study' : paused ? 'Orbit paused' : active ? 'Field expanded' : 'Signal in orbit';

  return (
    <section className={`mxv-core${compact ? ' mxv-core--compact' : ''}`} aria-label="Interactive signal core">
      <div className="mxv-core-meta" aria-hidden="true">
        <span>MRG / FIELD 01</span><span>{preferences.depth ? 'SPATIAL SIGNAL' : 'PLANAR SIGNAL'}</span>
      </div>
      <div
        {...navigation.bindings}
        ref={viewportRef}
        className="mxv-viewport mxv-core-viewport"
        data-rotatable={preferences.motion && supported !== false || undefined}
        role="button"
        aria-label="Expand signal core"
        aria-pressed={active}
        aria-describedby={helpId}
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            if (!event.repeat) activate();
          } else navigation.bindings.onKeyDown(event);
        }}
      >
        <canvas ref={canvasRef} className="mxv-canvas" hidden={supported === false} aria-hidden="true" />
        {supported === false && <CoreFallback expanded={active} />}
      </div>
      <div className="mxv-core-footer">
        <output className="mxv-status"><i aria-hidden="true" />{status}</output>
        <fieldset className="mxv-controls" aria-label="Signal controls">
          <button type="button" className="mxv-button mxv-button--accent" aria-pressed={active} onClick={activate}>
            {active ? 'Collapse' : 'Activate'}
          </button>
          <button
            type="button"
            className="mxv-button"
            aria-label={paused ? 'Resume signal animation' : 'Pause signal animation'}
            aria-pressed={paused}
            disabled={!preferences.motion || supported === false}
            title={preferences.motionReason || undefined}
            onClick={() => setPaused((value) => !value)}
          >
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button type="button" className="mxv-button" onClick={reset} aria-label="Reset signal core">Reset</button>
        </fieldset>
      </div>
      <p id={helpId} className="mxv-help">
        {supported === false ? 'Canvas unavailable · static signal illustration.' : !preferences.motion
          ? `${preferences.motionReason} · activate for a still expanded view.`
          : paused ? 'Orbit paused · drag or use arrow keys to rotate.' : 'Drag or use arrow keys to rotate · tap to activate.'}
      </p>
    </section>
  );
}

function CoreFallback({ expanded }: { expanded: boolean }) {
  return (
    <svg className="mxv-fallback" viewBox="0 0 400 320" aria-hidden="true">
      <g transform={`translate(200 160) scale(${expanded ? 1.13 : 1})`} fill="none" stroke="currentColor">
        <circle r="42" opacity=".65" />
        <ellipse rx="18" ry="42" opacity=".4" />
        <ellipse rx="42" ry="16" opacity=".4" />
        {[65, 74, 83, 92].map((radius) => <ellipse key={radius} rx={radius + 24} ry={radius * 0.62} transform="rotate(-24)" opacity=".45" />)}
        <ellipse className="mxv-fallback-orbit" rx="140" ry="100" transform="rotate(24)" opacity=".6" />
        <ellipse className="mxv-fallback-orbit" rx="140" ry="70" transform="rotate(-40)" opacity=".45" />
        <circle cx="128" cy="40" r="3" fill="currentColor" stroke="none" />
      </g>
    </svg>
  );
}
