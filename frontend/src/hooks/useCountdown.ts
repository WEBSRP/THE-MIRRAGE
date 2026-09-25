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
  const [isRunning, setIsRunning] = useState(autoStart);
  const [isComplete, setIsComplete] = useState(false);
  const intervalRef = useRef<number | null>(null);
  const onCompleteRef = useRef(onComplete);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const deadlineRef = useRef<number | null>(null);

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    if (!isComplete) {
      deadlineRef.current = Date.now() + timeLeft * 1000;
      setIsRunning(true);
    }
  }, [isComplete, timeLeft]);

  const pause = useCallback(() => {
    clearTimer();
    setIsRunning(false);
  }, [clearTimer]);

  const reset = useCallback(() => {
    clearTimer();
    deadlineRef.current = null;
    setTimeLeft(totalSeconds);
    setIsRunning(false);
    setIsComplete(false);
  }, [totalSeconds, clearTimer]);

  const timeLeftRef = useRef(timeLeft);
  useEffect(() => {
    timeLeftRef.current = timeLeft;
  }, [timeLeft]);

  useEffect(() => {
    if (isRunning) {
      if (!deadlineRef.current) {
        deadlineRef.current = Date.now() + timeLeftRef.current * 1000;
      }

      const update = () => {
        if (!deadlineRef.current) return;
        const remaining = Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000));
        setTimeLeft(remaining);

        if (remaining <= 0) {
          clearTimer();
          setIsRunning(false);
          setIsComplete(true);
          onCompleteRef.current?.();
        }
      };

      update();
      intervalRef.current = window.setInterval(update, 1000);
    }

    return clearTimer;
  }, [isRunning, clearTimer]);

  const minutes = String(Math.floor(timeLeft / 60)).padStart(2, '0');
  const seconds = String(timeLeft % 60).padStart(2, '0');
  const progress = 1 - timeLeft / totalSeconds;

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
