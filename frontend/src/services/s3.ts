import { apiFetch } from './fetchClient';
import type { UploadImagesResponse, UploadVideoResponse } from './types';

// ── Presigned URL 발급 ──

export async function getVideoUploadUrl(video: {
  filename: string;
  contentType: string;
  sizeBytes: number;
}): Promise<UploadVideoResponse> {
  return apiFetch<UploadVideoResponse>('/api/v1/url/video', {
    method: 'POST',
    body: JSON.stringify({ video }),
  });
}

export async function getImageUploadUrls(
  refImages: Array<{
    filename: string;
    contentType: string;
    sizeBytes: number;
  }>
): Promise<UploadImagesResponse> {
  return apiFetch<UploadImagesResponse>('/api/v1/url/images', {
    method: 'POST',
    body: JSON.stringify({ refImages }),
  });
}

// ── S3 직접 업로드 ──

export async function uploadToS3(
  file: File,
  uploadInfo: { url: string; headers: Record<string, string> }
): Promise<void> {
  const response = await fetch(uploadInfo.url, {
    method: 'PUT',
    headers: uploadInfo.headers,
    body: file,
  });

  if (!response.ok) {
    throw new Error('S3 업로드에 실패했습니다.');
  }
}
