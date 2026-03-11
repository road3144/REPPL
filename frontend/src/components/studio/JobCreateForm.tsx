import { FormEvent, useState } from 'react';
import {
  createJob,
  getImageUploadUrls,
  getJobStatus,
  getVideoUploadUrl,
  JobStatusResponse,
  uploadWithPresignedUrl
} from '../../services/demoApi';

type JobCreateFormProps = {
  onCreated: (status: JobStatusResponse) => void;
  onError: (message: string | null) => void;
};

export function JobCreateForm({ onCreated, onError }: JobCreateFormProps) {
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [refImageFiles, setRefImageFiles] = useState<File[]>([]);
  const [brand, setBrand] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const canSubmit = !!videoFile && refImageFiles.length > 0 && brand.trim().length > 0 && !submitting;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onError(null);

    if (!videoFile || refImageFiles.length === 0) {
      return;
    }

    const trimmedBrand = brand.trim();
    if (!trimmedBrand) {
      return;
    }

    try {
      setSubmitting(true);

      const videoUpload = await getVideoUploadUrl({
        filename: videoFile.name,
        contentType: videoFile.type || 'video/mp4',
        sizeBytes: videoFile.size
      });
      await uploadWithPresignedUrl(videoFile, videoUpload.upload.video);

      const imagesUpload = await getImageUploadUrls(
        refImageFiles.map((file) => ({
          filename: file.name,
          contentType: file.type || 'image/jpeg',
          sizeBytes: file.size
        }))
      );
      await Promise.all(
        refImageFiles.map((file, index) => uploadWithPresignedUrl(file, imagesUpload.upload.refImages[index]))
      );

      const created = await createJob({
        videoKey: videoUpload.upload.video.key,
        refImageKeys: imagesUpload.upload.refImages.map((image) => image.key),
        options: { brand: trimmedBrand }
      });
      const createdStatus = await getJobStatus(created.jobId);

      onCreated(createdStatus);
      setVideoFile(null);
      setRefImageFiles([]);
      setBrand('');
    } catch (error: unknown) {
      onError(error instanceof Error ? error.message : '작업 생성에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="light-slide-card">
      <h2 className="text-2xl font-black text-slate-900">새 VPP 작업 요청</h2>

      <div className="mt-6 space-y-4">
        <label className="block text-sm">
          <span className="mb-2 block text-slate-600">원본 영상 파일</span>
          <input
            type="file"
            accept="video/mp4"
            onChange={(e) => setVideoFile(e.target.files?.[0] ?? null)}
            required
            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none ring-sky-400 transition focus:ring"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-slate-600">레퍼런스 이미지(1개 이상)</span>
          <input
            type="file"
            accept="image/png,image/jpeg"
            multiple
            onChange={(e) => setRefImageFiles(Array.from(e.target.files ?? []))}
            required
            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none ring-sky-400 transition focus:ring"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-2 block text-slate-600">삽입할 음료 브랜드</span>
          <input
            type="text"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            placeholder="ex) Pepsi Zero Can"
            autoComplete="off"
            required
            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none ring-sky-400 transition focus:ring"
          />
        </label>
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className="mt-6 w-full rounded-xl bg-sky-500 px-4 py-3 font-black text-white transition enabled:hover:bg-sky-600 disabled:cursor-not-allowed disabled:bg-sky-300"
      >
        {submitting ? '요청 처리 중...' : '분석 큐에 작업 추가'}
      </button>
    </form>
  );
}
