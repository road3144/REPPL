import { apiFetch } from './fetchClient';
import type {
  CandidateFrame,
  JobCreateResponse,
  JobListResponse,
  JobResultResponse,
  JobStatusResponse,
  PreviewListResponse,
  PreviewSelectResponse,
} from './types';

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

export async function selectPreview(jobId: string, selectedIndex: number): Promise<PreviewSelectResponse> {
  return apiFetch<PreviewSelectResponse>(`/api/v1/jobs/${jobId}/select`, {
    method: 'POST',
    body: JSON.stringify({ selectedIndex }),
  });
}

// ── Candidate (mock) ──

export async function getCandidateFrames(_videoKey: string): Promise<CandidateFrame[]> {
  await new Promise((r) => setTimeout(r, 1500));
  return [
    { id: 'A', color: 'linear-gradient(135deg, #0f1a1a, #0d2e1a)', timestampLabel: '장면 A · 00:34', description: '자연스러운 배치', confidence: 94 },
    { id: 'B', color: 'linear-gradient(135deg, #1a0f1a, #2e0d28)', timestampLabel: '장면 B · 01:12', description: '주목도 높음', confidence: 89 },
    { id: 'C', color: 'linear-gradient(135deg, #1a1a0f, #2a2e0d)', timestampLabel: '장면 C · 02:05', description: '클로즈업 구도', confidence: 82 },
  ];
}
