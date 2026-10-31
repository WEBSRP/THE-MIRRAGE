import { useState, useEffect, useCallback, useRef } from 'react';

interface UseCountdownOptions {
  totalSeconds: number;
  onComplete?: () => void;
  autoStart?: boolean;
}

interface UseCountdownReturn {
  timeLeft: number;
  isRunning: boolean;
  isComplete: boolean;
  minutes: string;
  seconds: string;
  progress: number; // 0 to 1
  start: () => void;
  pause: () => void;
  reset: () => void;
}

export function useCountdown({
  totalSeconds,
  onComplete,
  autoStart = false,
}: UseCountdownOptions): UseCountdownReturn {
  const [timeLeft, setTimeLeft] = useState(totalSeconds);
  const [isRunning, setIsRunning] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const intervalRef = useRef<number | null>(null);
  const onCompleteRef = useRef(onComplete);
  const onCompleteFiredRef = useRef(false);
  const deadlineRef = useRef<number | null>(null);

  // Keep onComplete ref up-to-date without triggering re-renders
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    if (isComplete) return;
    // Always set a fresh deadline from current timeLeft.
    // Use a ref to avoid stale closure — read the latest state via functional update pattern.
    setTimeLeft((currentTimeLeft) => {
      deadlineRef.current = Date.now() + currentTimeLeft * 1000;
      return currentTimeLeft;
    });
    onCompleteFiredRef.current = false;
    setIsRunning(true);
  }, [isComplete]);

  const pause = useCallback(() => {
    clearTimer();
    // Snapshot the remaining time from the deadline so resuming is accurate
    if (deadlineRef.current) {
      const remaining = Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000));
      setTimeLeft(remaining);
    }
    deadlineRef.current = null;
    setIsRunning(false);
  }, [clearTimer]);

  const reset = useCallback(() => {
    clearTimer();
    deadlineRef.current = null;
    onCompleteFiredRef.current = false;
    setTimeLeft(totalSeconds);
    setIsRunning(false);
    setIsComplete(false);
  }, [totalSeconds, clearTimer]);

  // Auto-start support (only on mount, not on re-renders)
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (autoStart && !autoStartedRef.current) {
      autoStartedRef.current = true;
      deadlineRef.current = Date.now() + totalSeconds * 1000;
      onCompleteFiredRef.current = false;
      setIsRunning(true);
    }
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Core tick effect: runs when isRunning changes
  useEffect(() => {
    if (!isRunning) {
      clearTimer();
      return;
    }

    // If no deadline was set (shouldn't happen but guard), create one from current timeLeft
    if (!deadlineRef.current) {
      deadlineRef.current = Date.now() + timeLeft * 1000;
    }

    const tick = () => {
      if (!deadlineRef.current) return;
      const remainingMs = deadlineRef.current - Date.now();
      const remaining = Math.max(0, Math.ceil(remainingMs / 1000));
      setTimeLeft(remaining);

      if (remaining <= 0) {
        clearTimer();
        setIsRunning(false);
        setIsComplete(true);
        // Fire onComplete exactly once
        if (!onCompleteFiredRef.current) {
          onCompleteFiredRef.current = true;
          onCompleteRef.current?.();
        }
      }
    };

    // Immediate first tick
    tick();
    // Guard: only create one interval
    if (intervalRef.current === null) {
      intervalRef.current = window.setInterval(tick, 1000);
    }

    return () => {
      clearTimer();
    };
    // Intentionally only depend on isRunning — deadline is stored in ref
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRunning, clearTimer]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearTimer();
    };
  }, [clearTimer]);

  const minutes = String(Math.floor(timeLeft / 60)).padStart(2, '0');
  const seconds = String(timeLeft % 60).padStart(2, '0');
  const progress = totalSeconds > 0 ? 1 - timeLeft / totalSeconds : 0;

  return {
    timeLeft,
    isRunning,
    isComplete,
    minutes,
    seconds,
    progress,
    start,
    pause,
    reset,
  };
}
