import { useEffect, useState } from 'react';

export const WORKSPACE_SETTINGS_STORAGE_KEY = 'reppl.workspace.settings.v1';
export const WORKSPACE_SETTINGS_EVENT = 'reppl:workspace-settings-updated';

export type DownloadFilenamePattern = 'job-id' | 'job-id-timestamp';

export type WorkspaceSettings = {
  notifications: {
    toastEnabled: boolean;
    soundEnabled: boolean;
    browserEnabled: boolean;
  };
  download: {
    filenamePattern: DownloadFilenamePattern;
  };
  defaults: {
    placementPrompt: string;
  };
};

export const DEFAULT_WORKSPACE_SETTINGS: WorkspaceSettings = {
  notifications: {
    toastEnabled: true,
    soundEnabled: false,
    browserEnabled: false,
  },
  download: {
    filenamePattern: 'job-id',
  },
  defaults: {
    placementPrompt: '',
  },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function asFilenamePattern(value: unknown): DownloadFilenamePattern {
  if (value === 'job-id-timestamp') {
    return 'job-id-timestamp';
  }
  return 'job-id';
}

function asString(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

function normalizeWorkspaceSettings(value: unknown): WorkspaceSettings {
  if (!isRecord(value)) {
    return DEFAULT_WORKSPACE_SETTINGS;
  }

  const notifications = isRecord(value.notifications) ? value.notifications : {};
  const download = isRecord(value.download) ? value.download : {};
  const defaults = isRecord(value.defaults) ? value.defaults : {};

  return {
    notifications: {
      toastEnabled: asBoolean(
        notifications.toastEnabled,
        DEFAULT_WORKSPACE_SETTINGS.notifications.toastEnabled
      ),
      soundEnabled: asBoolean(
        notifications.soundEnabled,
        DEFAULT_WORKSPACE_SETTINGS.notifications.soundEnabled
      ),
      browserEnabled: asBoolean(
        notifications.browserEnabled,
        DEFAULT_WORKSPACE_SETTINGS.notifications.browserEnabled
      ),
    },
    download: {
      filenamePattern: asFilenamePattern(download.filenamePattern),
    },
    defaults: {
      placementPrompt: asString(
        defaults.placementPrompt,
        DEFAULT_WORKSPACE_SETTINGS.defaults.placementPrompt
      ),
    },
  };
}

export function readWorkspaceSettings(): WorkspaceSettings {
  if (typeof window === 'undefined') {
    return DEFAULT_WORKSPACE_SETTINGS;
  }

  try {
    const raw = window.localStorage.getItem(WORKSPACE_SETTINGS_STORAGE_KEY);
    if (!raw) return DEFAULT_WORKSPACE_SETTINGS;
    return normalizeWorkspaceSettings(JSON.parse(raw));
  } catch {
    return DEFAULT_WORKSPACE_SETTINGS;
  }
}

export function writeWorkspaceSettings(next: WorkspaceSettings): WorkspaceSettings {
  const normalized = normalizeWorkspaceSettings(next);
  if (typeof window === 'undefined') {
    return normalized;
  }

  try {
    window.localStorage.setItem(
      WORKSPACE_SETTINGS_STORAGE_KEY,
      JSON.stringify(normalized)
    );
    window.dispatchEvent(new Event(WORKSPACE_SETTINGS_EVENT));
  } catch {
    // Ignore storage failures and continue with in-memory state.
  }

  return normalized;
}

export function updateWorkspaceSettings(
  updater: (current: WorkspaceSettings) => WorkspaceSettings
): WorkspaceSettings {
  const current = readWorkspaceSettings();
  const next = updater(current);
  return writeWorkspaceSettings(next);
}

export function useWorkspaceSettings() {
  const [settings, setSettings] = useState<WorkspaceSettings>(() => readWorkspaceSettings());

  useEffect(() => {
    const sync = () => {
      setSettings(readWorkspaceSettings());
    };

    window.addEventListener(WORKSPACE_SETTINGS_EVENT, sync);
    window.addEventListener('storage', sync);

    return () => {
      window.removeEventListener(WORKSPACE_SETTINGS_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  const patchSettings = (
    updater: (current: WorkspaceSettings) => WorkspaceSettings
  ) => {
    const next = updateWorkspaceSettings(updater);
    setSettings(next);
  };

  return {
    settings,
    patchSettings,
  };
}

function formatTimestamp(date: Date): string {
  const y = date.getFullYear();
  const m = `${date.getMonth() + 1}`.padStart(2, '0');
  const d = `${date.getDate()}`.padStart(2, '0');
  const hh = `${date.getHours()}`.padStart(2, '0');
  const mm = `${date.getMinutes()}`.padStart(2, '0');
  const ss = `${date.getSeconds()}`.padStart(2, '0');
  return `${y}${m}${d}-${hh}${mm}${ss}`;
}

export function buildDownloadFileName(
  jobId: string,
  pattern: DownloadFilenamePattern
): string {
  if (pattern === 'job-id-timestamp') {
    return `${jobId}_${formatTimestamp(new Date())}.mp4`;
  }
  return `${jobId}.mp4`;
}
