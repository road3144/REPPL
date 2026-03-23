import { DragEvent, FormEvent, useCallback, useRef, useState } from 'react';
import { createPreviewJob, getJobStatus } from '../../services/api';
import { getImageUploadUrls, getVideoUploadUrl, uploadToS3 } from '../../services/s3';
import type { JobStatusResponse } from '../../services/types';

type JobCreateFormProps = {
  onCreated: (status: JobStatusResponse) => void;
  onError: (message: string | null) => void;
  /** If provided, called after upload completes instead of proceeding to createJob */
  onUploaded?: (videoKey: string, imageKey: string, prompt: string) => void;
  className?: string;
};

const examplePrompts = [
  '테이블 오른쪽 위 컵 옆에 배치',
  '소파 왼쪽 팔걸이 위에 놓기',
  '바닥에 자연스럽게 그림자 포함',
  '인물 손 앞쪽에 배치',
];

type SubmitStage = 'idle' | 'uploading-video' | 'uploading-image' | 'creating-job';
const stageLabel: Record<SubmitStage, string> = {
  idle: 'AI 분석 시작',
  'uploading-video': '영상 업로드 중...',
  'uploading-image': '이미지 업로드 중...',
  'creating-job': '작업 생성 중...',
};

export function JobCreateForm({ onCreated, onError, onUploaded, className }: JobCreateFormProps) {
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [refImageFile, setRefImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [placementPrompt, setPlacementPrompt] = useState('');
  const [stage, setStage] = useState<SubmitStage>('idle');
  const [videoDragOver, setVideoDragOver] = useState(false);
  const [imageDragOver, setImageDragOver] = useState(false);

  const videoInputRef = useRef<HTMLInputElement>(null);
  const refImageInputRef = useRef<HTMLInputElement>(null);

  const submitting = stage !== 'idle';
  const canSubmit = !!videoFile && !!refImageFile && placementPrompt.trim().length > 0 && !submitting;

  /* ── File handlers ── */
  const handleVideoSelect = useCallback((file: File | null) => {
    if (file && !file.type.startsWith('video/')) {
      onError('mp4 동영상 파일만 업로드 가능합니다.');
      return;
    }
    setVideoFile(file);
  }, [onError]);

  const handleImageSelect = useCallback((file: File | null) => {
    if (file && !file.type.startsWith('image/')) {
      onError('png, jpg, jpeg 이미지 파일만 업로드 가능합니다.');
      return;
    }
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    if (file) {
      setImagePreview(URL.createObjectURL(file));
    } else {
      setImagePreview(null);
    }
    setRefImageFile(file);
  }, [onError, imagePreview]);

  /* ── Drag & Drop helpers ── */
  const preventDefaults = (e: DragEvent) => { e.preventDefault(); e.stopPropagation(); };

  const handleVideoDrop = (e: DragEvent<HTMLDivElement>) => {
    preventDefaults(e);
    setVideoDragOver(false);
    const file = e.dataTransfer.files[0] ?? null;
    handleVideoSelect(file);
    if (videoInputRef.current) videoInputRef.current.value = '';
  };

  const handleImageDrop = (e: DragEvent<HTMLDivElement>) => {
    preventDefaults(e);
    setImageDragOver(false);
    const file = e.dataTransfer.files[0] ?? null;
    handleImageSelect(file);
    if (refImageInputRef.current) refImageInputRef.current.value = '';
  };

  /* ── Submit ── */
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onError(null);

    if (!videoFile || !refImageFile) return;
    const trimmedPlacementPrompt = placementPrompt.trim();
    if (!trimmedPlacementPrompt) return;

    try {
      setStage('uploading-video');
      const videoUpload = await getVideoUploadUrl({
        filename: videoFile.name,
        contentType: videoFile.type || 'video/mp4',
        sizeBytes: videoFile.size
      });
      await uploadToS3(videoFile, videoUpload.upload.video);

      setStage('uploading-image');
      const imagesUpload = await getImageUploadUrls([{
        filename: refImageFile.name,
        contentType: refImageFile.type || 'image/jpeg',
        sizeBytes: refImageFile.size
      }]);
      const uploadedRefImage = imagesUpload.upload.refImages[0];
      if (!uploadedRefImage) throw new Error('삽입 이미지 업로드 URL 조회에 실패했습니다.');
      await uploadToS3(refImageFile, uploadedRefImage);

      // If parent wants to handle candidate selection first, stop here
      if (onUploaded) {
        onUploaded(videoUpload.upload.video.key, uploadedRefImage.key, trimmedPlacementPrompt);
        setVideoFile(null);
        setRefImageFile(null);
        setPlacementPrompt('');
        if (imagePreview) { URL.revokeObjectURL(imagePreview); setImagePreview(null); }
        if (videoInputRef.current) videoInputRef.current.value = '';
        if (refImageInputRef.current) refImageInputRef.current.value = '';
        return;
      }

      setStage('creating-job');
      const created = await createPreviewJob({
        videoKey: videoUpload.upload.video.key,
        refImageKeys: [uploadedRefImage.key],
        options: { placementPrompt: trimmedPlacementPrompt }
      });
      const createdStatus = await getJobStatus(created.jobId);

      onCreated(createdStatus);
      setVideoFile(null);
      setRefImageFile(null);
      setPlacementPrompt('');
      if (imagePreview) { URL.revokeObjectURL(imagePreview); setImagePreview(null); }
      if (videoInputRef.current) videoInputRef.current.value = '';
      if (refImageInputRef.current) refImageInputRef.current.value = '';
    } catch (error: unknown) {
      onError(error instanceof Error ? error.message : '작업 생성에 실패했습니다.');
    } finally {
      setStage('idle');
    }
  };

  return (
    <form onSubmit={handleSubmit} className={className ?? 'light-slide-card'}>
      <h2 className="text-2xl font-black text-slate-900">새 삽입 작업</h2>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        동영상과 물체 사진을 업로드하고 배치 위치를 설명하세요.
      </p>

      <div className="mt-6 space-y-5">
        {/* ── 1. Video Upload ── */}
        <div>
          <p className="form-label">① 원본 영상 파일</p>
          <div
            className={`drop-zone ${videoDragOver ? 'drop-zone-active' : ''} ${videoFile ? 'drop-zone-filled' : ''}`}
            onDragOver={(e) => { preventDefaults(e); setVideoDragOver(true); }}
            onDragLeave={() => setVideoDragOver(false)}
            onDrop={handleVideoDrop}
            onClick={() => videoInputRef.current?.click()}
          >
            <input
              ref={videoInputRef}
              type="file"
              accept="video/mp4"
              onChange={(e) => handleVideoSelect(e.target.files?.[0] ?? null)}
              className="hidden"
            />
            {videoFile ? (
              <div className="drop-zone-info">
                <span className="drop-zone-icon">🎬</span>
                <div>
                  <p className="text-sm font-bold text-slate-800">{videoFile.name}</p>
                  <p className="text-xs text-slate-500">{(videoFile.size / 1024 / 1024).toFixed(1)} MB</p>
                </div>
                <button
                  type="button"
                  className="ml-auto text-xs font-semibold text-rose-500 hover:text-rose-700 transition"
                  onClick={(e) => { e.stopPropagation(); setVideoFile(null); if (videoInputRef.current) videoInputRef.current.value = ''; }}
                >
                  삭제
                </button>
              </div>
            ) : (
              <div className="drop-zone-placeholder">
                <span className="drop-zone-icon-large">📁</span>
                <p className="text-sm font-semibold text-slate-600">클릭 또는 드래그하여 mp4 파일 업로드</p>
                <p className="text-xs text-slate-400 mt-1">최대 1개 파일</p>
              </div>
            )}
          </div>
        </div>

        {/* ── 2. Image Upload ── */}
        <div>
          <p className="form-label">② 삽입할 물체 사진</p>
          <div
            className={`drop-zone ${imageDragOver ? 'drop-zone-active' : ''} ${refImageFile ? 'drop-zone-filled' : ''}`}
            onDragOver={(e) => { preventDefaults(e); setImageDragOver(true); }}
            onDragLeave={() => setImageDragOver(false)}
            onDrop={handleImageDrop}
            onClick={() => refImageInputRef.current?.click()}
          >
            <input
              ref={refImageInputRef}
              type="file"
              accept="image/png,image/jpeg"
              onChange={(e) => handleImageSelect(e.target.files?.[0] ?? null)}
              className="hidden"
            />
            {refImageFile && imagePreview ? (
              <div className="drop-zone-info">
                <img src={imagePreview} alt="삽입 물체 미리보기" className="drop-zone-thumb" />
                <div>
                  <p className="text-sm font-bold text-slate-800">{refImageFile.name}</p>
                  <p className="text-xs text-slate-500">{(refImageFile.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
                <button
                  type="button"
                  className="ml-auto text-xs font-semibold text-rose-500 hover:text-rose-700 transition"
                  onClick={(e) => { e.stopPropagation(); handleImageSelect(null); if (refImageInputRef.current) refImageInputRef.current.value = ''; }}
                >
                  삭제
                </button>
              </div>
            ) : (
              <div className="drop-zone-placeholder">
                <span className="drop-zone-icon-large">🖼️</span>
                <p className="text-sm font-semibold text-slate-600">클릭 또는 드래그하여 이미지 업로드</p>
                <p className="text-xs text-slate-400 mt-1">png, jpg, jpeg (1개)</p>
              </div>
            )}
          </div>
        </div>

        {/* ── 3. Placement Prompt ── */}
        <div>
          <p className="form-label">③ 삽입 위치 설명</p>
          <textarea
            value={placementPrompt}
            onChange={(e) => setPlacementPrompt(e.target.value)}
            placeholder="예: 테이블 오른쪽 위 컵 옆에 배치하고, 바닥 그림자가 자연스럽게 이어지도록"
            required
            rows={4}
            className="w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none ring-sky-400 transition focus:ring"
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {examplePrompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="example-chip"
                onClick={() => setPlacementPrompt((prev) => prev ? `${prev}, ${prompt}` : prompt)}
              >
                + {prompt}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Submit Progress ── */}
      {submitting && (
        <div className="mt-4">
          <div className="submit-progress-bar">
            <div
              className="submit-progress-fill"
              style={{
                width: stage === 'uploading-video' ? '33%' : stage === 'uploading-image' ? '66%' : '90%',
              }}
            />
          </div>
        </div>
      )}

      <button
        type="submit"
        disabled={!canSubmit}
        className="mt-5 w-full rounded-xl bg-sky-500 px-4 py-3.5 font-black text-white transition enabled:hover:bg-sky-600 enabled:hover:shadow-lg enabled:hover:shadow-sky-200 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
      >
        {stageLabel[stage]}
      </button>
    </form>
  );
}
