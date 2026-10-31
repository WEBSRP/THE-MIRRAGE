import { useRef, type KeyboardEvent, type PointerEvent, type RefObject } from 'react';
import { clamp, type Camera } from './sceneMath';

export type SceneCamera = Camera & { parallaxX: number; parallaxY: number; dragging: boolean };

export function createSceneCamera(initial: Camera): SceneCamera {
  return { ...initial, parallaxX: 0, parallaxY: 0, dragging: false };
}

type Gesture = {
  id: number;
  x: number;
  y: number;
  pitch: number;
  yaw: number;
  moved: boolean;
  touch: boolean;
};

type CameraOptions = {
  cameraRef: RefObject<SceneCamera>;
  initial: Camera;
  interactive: boolean;
  invalidate: () => void;
  onTap?: (x: number, y: number) => void;
  onHover?: (x: number, y: number) => void;
  onLeave?: () => void;
  yawLimit?: number;
};

/** Touch locks only after a horizontal intent; native vertical scroll and pinch stay available. */
export function useSceneCamera(options: CameraOptions) {
  const { cameraRef, initial, interactive, invalidate, onTap, onHover, onLeave, yawLimit = Infinity } = options;
  const gesture = useRef<Gesture | null>(null);

  const reset = () => {
    Object.assign(cameraRef.current, initial, { parallaxX: 0, parallaxY: 0, dragging: false });
    gesture.current = null;
    invalidate();
  };

  const localPoint = (event: PointerEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top, bounds };
  };

  const release = (event: PointerEvent<HTMLDivElement>) => {
    if (gesture.current && gesture.current.id !== event.pointerId) return;
    gesture.current = null;
    cameraRef.current.dragging = false;
    delete event.currentTarget.dataset.dragging;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    invalidate();
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (!event.isPrimary || event.button !== 0 || gesture.current) return;
    gesture.current = {
      id: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      pitch: cameraRef.current.pitch,
      yaw: cameraRef.current.yaw,
      moved: false,
      touch: event.pointerType === 'touch',
    };
    if (event.pointerType !== 'touch' && interactive) event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const current = gesture.current;
    if (current && current.id !== event.pointerId) return;
    if (current) {
      const dx = event.clientX - current.x;
      const dy = event.clientY - current.y;
      if (!current.moved && Math.hypot(dx, dy) < 7) return;
      if (current.touch && !current.moved && Math.abs(dy) > Math.abs(dx)) {
        release(event);
        return;
      }
      current.moved = true;
      if (!interactive) return;
      if (!event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.setPointerCapture(event.pointerId);
      cameraRef.current.dragging = true;
      event.currentTarget.dataset.dragging = 'true';
      cameraRef.current.yaw = clamp(current.yaw + dx * 0.006, -yawLimit, yawLimit);
      cameraRef.current.pitch = clamp(current.pitch + (current.touch ? 0 : dy * 0.005), -0.85, 0.85);
      cameraRef.current.parallaxX = 0;
      cameraRef.current.parallaxY = 0;
      invalidate();
      return;
    }

    if (event.pointerType !== 'touch') {
      const { x, y, bounds } = localPoint(event);
      onHover?.(x, y);
      if (interactive) {
        cameraRef.current.parallaxX = (x / Math.max(1, bounds.width) - 0.5) * 0.12;
        cameraRef.current.parallaxY = (y / Math.max(1, bounds.height) - 0.5) * 0.09;
        invalidate();
      }
    }
  };

  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    const current = gesture.current;
    if (current?.id !== event.pointerId) return;
    // Also check release distance: a browser can coalesce all intermediate moves.
    if (!current.moved && Math.hypot(event.clientX - current.x, event.clientY - current.y) < 7) {
      const point = localPoint(event);
      onTap?.(point.x, point.y);
    }
    release(event);
  };

  const onPointerLeave = (event: PointerEvent<HTMLDivElement>) => {
    cameraRef.current.parallaxX = 0;
    cameraRef.current.parallaxY = 0;
    onLeave?.();
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) release(event);
    invalidate();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Home') {
      event.preventDefault();
      reset();
    } else if (interactive && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
      event.preventDefault();
      const yawStep = event.key === 'ArrowLeft' ? -0.12 : event.key === 'ArrowRight' ? 0.12 : 0;
      const pitchStep = event.key === 'ArrowUp' ? -0.1 : event.key === 'ArrowDown' ? 0.1 : 0;
      cameraRef.current.yaw = clamp(cameraRef.current.yaw + yawStep, -yawLimit, yawLimit);
      cameraRef.current.pitch = clamp(cameraRef.current.pitch + pitchStep, -0.85, 0.85);
      invalidate();
    }
  };

  return {
    reset,
    bindings: {
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel: release,
      onLostPointerCapture: release,
      onPointerLeave,
      onKeyDown,
    },
  };
}
