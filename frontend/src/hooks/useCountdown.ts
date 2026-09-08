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

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    if (!isComplete) {
      setIsRunning(true);
    }
  }, [isComplete]);

  const pause = useCallback(() => {
    setIsRunning(false);
  }, []);

  const reset = useCallback(() => {
    clearTimer();
    setTimeLeft(totalSeconds);
    setIsRunning(false);
    setIsComplete(false);
  }, [totalSeconds, clearTimer]);

  useEffect(() => {
    if (isRunning && timeLeft > 0) {
      intervalRef.current = window.setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            clearTimer();
            setIsRunning(false);
            setIsComplete(true);
            onCompleteRef.current?.();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return clearTimer;
  }, [isRunning, timeLeft, clearTimer]);

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
