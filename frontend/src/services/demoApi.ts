export type ApiResponse<T> = {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
};

export type UploadVideoResponse = {
  upload: {
    video: {
      key: string;
      url: string;
      method: string;
      headers: Record<string, string>;
      expiresAt: string;
    };
  };
};

export type UploadImagesResponse = {
  upload: {
    refImages: Array<{
      key: string;
      url: string;
      method: string;
      headers: Record<string, string>;
      expiresAt: string;
    }>;
  };
};

export type JobCreateResponse = {
  jobId: string;
  status: string;
};

export type JobItem = {
  jobId: string;
  status: string;
  progress: number | null;
  stage: string | null;
  message: string | null;
  createdAt: string | null;
};

export type JobListResponse = {
  items: JobItem[];
  page: number;
  size: number;
  totalCount: number;
  totalPages: number;
};

export type JobStatusResponse = {
  jobId: string;
  status: string;
  progress: number | null;
  stage: string | null;
  message: string | null;
  result: {
    videoKey: string;
  } | null;
};

export type JobResultResponse = {
  download: {
    key: string;
    url: string;
    method: string;
    expiresAt: string;
  };
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {})
    }
  });

  const payload = (await response.json()) as ApiResponse<T>;

  if (!response.ok || !payload.success) {
    throw new Error(payload.error?.message ?? 'API 요청에 실패했습니다.');
  }

  return payload.data;
}

export async function getJobs(page = 0, size = 20): Promise<JobListResponse> {
  return apiFetch<JobListResponse>(`/api/v1/jobs?page=${page}&size=${size}`);
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return apiFetch<JobStatusResponse>(`/api/v1/jobs/${jobId}`);
}

export async function getJobResult(jobId: string): Promise<JobResultResponse> {
  return apiFetch<JobResultResponse>(`/api/v1/jobs/${jobId}/result`);
}

export async function getVideoUploadUrl(video: {
  filename: string;
  contentType: string;
  sizeBytes: number;
}): Promise<UploadVideoResponse> {
  return apiFetch<UploadVideoResponse>('/api/v1/url/video', {
    method: 'POST',
    body: JSON.stringify({ video })
  });
}

export async function getImageUploadUrls(refImages: Array<{
  filename: string;
  contentType: string;
  sizeBytes: number;
}>): Promise<UploadImagesResponse> {
  return apiFetch<UploadImagesResponse>('/api/v1/url/images', {
    method: 'POST',
    body: JSON.stringify({ refImages })
  });
}

export async function createJob(payload: {
  videoKey: string;
  refImageKeys: string[];
  options: { placementPrompt: string };
}): Promise<JobCreateResponse> {
  return apiFetch<JobCreateResponse>('/api/v1/jobs', {
    method: 'POST',
    body: JSON.stringify({
      videoKey: payload.videoKey,
      refImageKeys: payload.refImageKeys,
      roi: {
        frame: { type: 'FIRST', timestampMs: 0 },
        coordinateSystem: 'normalized',
        boxes: [{ id: 'full-frame', x: 0, y: 0, w: 1, h: 1 }]
      },
      options: payload.options
    })
  });
}

export type CandidateFrame = {
  id: string;
  color: string;
  timestampLabel: string;
  description: string;
  confidence: number;
};

export async function getCandidateFrames(_videoKey: string): Promise<CandidateFrame[]> {
  // Mock: simulate AI analysis delay
  await new Promise(r => setTimeout(r, 1500));
  return [
    { id: 'A', color: 'linear-gradient(135deg, #0f1a1a, #0d2e1a)', timestampLabel: '장면 A · 00:34', description: '자연스러운 배치', confidence: 94 },
    { id: 'B', color: 'linear-gradient(135deg, #1a0f1a, #2e0d28)', timestampLabel: '장면 B · 01:12', description: '주목도 높음', confidence: 89 },
    { id: 'C', color: 'linear-gradient(135deg, #1a1a0f, #2a2e0d)', timestampLabel: '장면 C · 02:05', description: '클로즈업 구도', confidence: 82 },
  ];
}

export async function uploadWithPresignedUrl(file: File, uploadInfo: { url: string; headers: Record<string, string> }) {
  const response = await fetch(uploadInfo.url, {
    method: 'PUT',
    headers: uploadInfo.headers,
    body: file
  });

  if (!response.ok) {
    throw new Error('S3 업로드에 실패했습니다.');
  }
}
