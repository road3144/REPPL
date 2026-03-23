export type ApiResponse<T> = {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
};

// ── Upload ──

export type UploadInfo = {
  key: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  expiresAt: string;
};

export type UploadVideoResponse = {
  upload: {
    video: UploadInfo;
  };
};

export type UploadImagesResponse = {
  upload: {
    refImages: UploadInfo[];
  };
};

// ── Job ──

export type JobType = 'PREVIEW' | 'COMPOSITE';

export type JobItem = {
  jobId: string;
  jobType: JobType | null;
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
  jobType: JobType | null;
  status: string;
  progress: number | null;
  stage: string | null;
  message: string | null;
  result: {
    videoKey: string;
  } | null;
};

export type JobCreateResponse = {
  jobId: string;
  status: string;
};

export type JobResultResponse = {
  download: {
    key: string;
    url: string;
    method: string;
    expiresAt: string;
  };
};

// ── Preview ──

export type PreviewItem = {
  index: number;
  key: string;
  url: string;
};

export type PreviewListResponse = {
  jobId: string;
  previews: PreviewItem[];
};

export type PreviewSelectResponse = {
  compositeJobId: string;
  status: string;
};