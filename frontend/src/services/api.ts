import { apiFetch } from './fetchClient';
import type {
  JobCreateResponse,
  JobListResponse,
  JobResultResponse,
  JobStatusResponse,
  PreviewListResponse,
  PreviewSelectResponse,
} from './types';

// ── Session ──

export async function initSession(): Promise<void> {
  await apiFetch<unknown>('/api/v1/session');
}

// ── Job ──

export async function getJobs(page = 0, size = 20): Promise<JobListResponse> {
  return apiFetch<JobListResponse>(`/api/v1/jobs?page=${page}&size=${size}`);
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return apiFetch<JobStatusResponse>(`/api/v1/jobs/${jobId}`);
}

export async function getJobResult(jobId: string): Promise<JobResultResponse> {
  return apiFetch<JobResultResponse>(`/api/v1/jobs/${jobId}/result`);
}

// ── Preview / Composite ──

export async function createPreviewJob(payload: {
  videoKey: string;
  refImageKeys: string[];
  options: { placementPrompt: string };
}): Promise<JobCreateResponse> {
  return apiFetch<JobCreateResponse>('/api/v1/jobs/preview', {
    method: 'POST',
    body: JSON.stringify({
      videoKey: payload.videoKey,
      refImageKeys: payload.refImageKeys,
      options: payload.options,
    }),
  });
}

export async function getPreviewUrls(jobId: string): Promise<PreviewListResponse> {
  return apiFetch<PreviewListResponse>(`/api/v1/jobs/${jobId}/previews`);
}

export async function selectPreview(
  jobId: string,
  selectedIndex: number,
  overrides?: { videoKey?: string; refImageKey?: string },
): Promise<PreviewSelectResponse> {
  return apiFetch<PreviewSelectResponse>(`/api/v1/jobs/${jobId}/select`, {
    method: 'POST',
    body: JSON.stringify({
      selectedIndex,
      ...(overrides?.videoKey && { videoKey: overrides.videoKey }),
      ...(overrides?.refImageKey && { refImageKey: overrides.refImageKey }),
    }),
  });
}