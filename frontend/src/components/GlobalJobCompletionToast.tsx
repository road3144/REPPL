import { useEffect, useRef, useState } from 'react';
import { getJobs, initSession } from '../services/api';
import { useWorkspaceSettings } from '../services/workspaceSettings';

type ToastEntry = {
  jobId: string;
};

function CheckCircleIcon({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12 2.3 2.3 4.7-4.8" />
    </svg>
  );
}

function isCompletionTransition(prevStatus: string | undefined, nextStatus: string) {
  return (prevStatus === 'RUNNING' || prevStatus === 'QUEUED') && nextStatus === 'COMPLETED';
}

function playCompletionSound() {
  try {
    const AudioCtx = window.AudioContext || (window as Window & typeof globalThis & {
      webkitAudioContext?: typeof AudioContext;
    }).webkitAudioContext;

    if (!AudioCtx) return;

    const context = new AudioCtx();
    const oscillator = context.createOscillator();
    const gainNode = context.createGain();

    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(880, context.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(1320, context.currentTime + 0.12);

    gainNode.gain.setValueAtTime(0.0001, context.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.12, context.currentTime + 0.02);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.18);

    oscillator.connect(gainNode);
    gainNode.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.18);

    window.setTimeout(() => {
      void context.close();
    }, 260);
  } catch {
    // Ignore browser audio policy failures.
  }
}

export function GlobalJobCompletionToast() {
  const { settings } = useWorkspaceSettings();
  const [toast, setToast] = useState<ToastEntry | null>(null);

  const prevStatusByJobRef = useRef<Map<string, string>>(new Map());
  const notifiedJobIdsRef = useRef<Set<string>>(new Set());
  const queueRef = useRef<ToastEntry[]>([]);
  const settingsRef = useRef(settings);
  const initializedRef = useRef(false);
  const sessionReadyRef = useRef(false);
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const shiftToastQueue = () => {
    setToast(queueRef.current.shift() ?? null);
  };

  const enqueueToast = (entry: ToastEntry) => {
    setToast((current) => {
      if (!current) return entry;
      queueRef.current.push(entry);
      return current;
    });
  };

  useEffect(() => {
    settingsRef.current = settings;
    if (settings.notifications.toastEnabled) {
      return;
    }

    setToast(null);
    queueRef.current = [];
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current);
    }
  }, [settings]);

  useEffect(() => {
    if (!toast) return;

    dismissTimerRef.current = setTimeout(() => {
      shiftToastQueue();
    }, 5000);

    return () => {
      if (dismissTimerRef.current) {
        clearTimeout(dismissTimerRef.current);
      }
    };
  }, [toast]);

  useEffect(() => {
    let active = true;

    const syncJobs = async () => {
      try {
        if (!sessionReadyRef.current) {
          await initSession();
          sessionReadyRef.current = true;
        }

        const data = await getJobs(0, 50);
        if (!active) return;

        const nextStatusByJob = new Map<string, string>();

        for (const job of data.items) {
          const prevStatus = prevStatusByJobRef.current.get(job.jobId);
          nextStatusByJob.set(job.jobId, job.status);

          if (!initializedRef.current) continue;
          if (!isCompletionTransition(prevStatus, job.status)) continue;
          if (notifiedJobIdsRef.current.has(job.jobId)) continue;

          notifiedJobIdsRef.current.add(job.jobId);
          const currentSettings = settingsRef.current;

          if (currentSettings.notifications.toastEnabled) {
            enqueueToast({ jobId: job.jobId });
          }

          if (currentSettings.notifications.soundEnabled) {
            playCompletionSound();
          }

          if (
            currentSettings.notifications.browserEnabled &&
            typeof Notification !== 'undefined' &&
            Notification.permission === 'granted'
          ) {
            try {
              new Notification('합성 작업 완료', {
                body: `완료 작업: ${job.jobId}`,
              });
            } catch {
              // Ignore notification API failures.
            }
          }
        }

        prevStatusByJobRef.current = nextStatusByJob;
        initializedRef.current = true;
      } catch {
        // Ignore transient errors in global notifier.
      }
    };

    void syncJobs();
    const timer = window.setInterval(() => {
      void syncJobs();
    }, 3000);

    return () => {
      active = false;
      window.clearInterval(timer);
      if (dismissTimerRef.current) {
        clearTimeout(dismissTimerRef.current);
      }
      queueRef.current = [];
    };
  }, []);

  if (!toast) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 28,
        right: 28,
        zIndex: 500,
        background: '#1e1e2e',
        color: '#fff',
        borderRadius: 16,
        padding: '14px 18px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        boxShadow: '0 8px 32px rgba(0,0,0,0.35), 0 0 0 1px rgba(74,108,247,0.2)',
        minWidth: 300,
        maxWidth: 340,
        overflow: 'hidden',
        animation: 'slideUpToast 0.3s ease',
      }}
      role="status"
      aria-live="polite"
    >
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          height: 3,
          background: '#4a6cf7',
          borderRadius: '0 3px 3px 0',
          animation: 'shrinkBar 5s linear forwards',
        }}
      />

      <div
        style={{
          width: 38,
          height: 38,
          borderRadius: 10,
          background: '#4a6cf7',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          color: '#fff',
        }}
      >
        <CheckCircleIcon />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 700 }}>합성이 완료되었습니다!</div>
        <div
          style={{
            fontSize: 11,
            color: 'rgba(255,255,255,0.55)',
            marginTop: 2,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={toast.jobId}
        >
          완료 작업: {toast.jobId}
        </div>
      </div>

      <button
        type="button"
        onClick={() => {
          if (dismissTimerRef.current) {
            clearTimeout(dismissTimerRef.current);
          }
          shiftToastQueue();
        }}
        style={{
          background: 'none',
          border: 'none',
          color: 'rgba(255,255,255,0.35)',
          fontSize: 20,
          cursor: 'pointer',
          flexShrink: 0,
          lineHeight: 1,
        }}
        aria-label="알림 닫기"
      >
        ×
      </button>
    </div>
  );
}
