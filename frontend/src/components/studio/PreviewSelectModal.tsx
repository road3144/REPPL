import { useState, useEffect, useCallback } from 'react';
import type { PreviewItem } from '../../services/types';

type PreviewSelectModalProps = {
  jobId: string;
  previews: PreviewItem[];
  selecting: boolean;
  onSelect: (index: number) => void;
  onClose: () => void;
};

export function PreviewSelectModal({ jobId, previews, selecting, onSelect, onClose }: PreviewSelectModalProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const openLightbox = (index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setLightboxIndex(index);
  };

  const closeLightbox = useCallback(() => setLightboxIndex(null), []);

  const moveLightbox = useCallback((direction: -1 | 1) => {
    setLightboxIndex((prev) => {
      if (prev === null) return null;
      return (prev + direction + previews.length) % previews.length;
    });
  }, [previews.length]);

  useEffect(() => {
    if (lightboxIndex === null) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeLightbox();
      if (e.key === 'ArrowLeft') moveLightbox(-1);
      if (e.key === 'ArrowRight') moveLightbox(1);
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [lightboxIndex, closeLightbox, moveLightbox]);

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
        <div
          className="relative w-full max-w-3xl mx-4 rounded-2xl bg-white p-6 shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            onClick={onClose}
            className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 transition"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>

          <h3 className="text-xl font-black text-slate-900">프리뷰 선택</h3>
          <p className="mt-1 text-sm text-slate-500">
            <span className="font-mono text-xs text-slate-400">{jobId.slice(0, 12)}...</span>
            {' '}— 원하는 프리뷰를 선택하면 최종 합성이 시작됩니다.
          </p>

          <div className={`mt-5 grid grid-cols-1 gap-4 ${previews.length === 1 ? 'sm:grid-cols-1 max-w-sm mx-auto' : previews.length === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-3'}`}>
            {previews.map((preview) => (
              <button
                key={preview.index}
                type="button"
                disabled={selecting}
                onClick={() => setSelectedIndex(preview.index)}
                className={`group relative rounded-xl border-2 overflow-hidden transition-all ${
                  selectedIndex === preview.index
                    ? 'border-sky-500 ring-2 ring-sky-200 shadow-lg'
                    : 'border-slate-200 hover:border-slate-300'
                } ${selecting ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <img
                  src={preview.url}
                  alt={`프리뷰 ${preview.index + 1}`}
                  className="w-full aspect-video object-cover bg-slate-100"
                />
                {/* 확대 버튼 - 호버 시 표시 */}
                {!selecting && (
                  <div
                    role="button"
                    aria-label={`프리뷰 ${preview.index + 1} 크게 보기`}
                    onClick={(e) => openLightbox(preview.index, e)}
                    className="absolute bottom-8 right-2 w-7 h-7 rounded-full bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/70"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="11" cy="11" r="8" />
                      <path d="m21 21-4.35-4.35" />
                      <path d="M11 8v6M8 11h6" />
                    </svg>
                  </div>
                )}
                <div className="p-2 text-center">
                  <span className={`text-xs font-bold ${
                    selectedIndex === preview.index ? 'text-sky-600' : 'text-slate-500'
                  }`}>
                    프리뷰 {preview.index + 1}
                  </span>
                </div>
                {selectedIndex === preview.index && (
                  <div className="absolute top-2 right-2 w-6 h-6 rounded-full bg-sky-500 flex items-center justify-center">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round">
                      <path d="m5 12 5 5L20 7" />
                    </svg>
                  </div>
                )}
              </button>
            ))}
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={selecting}
              className="rounded-xl px-5 py-2.5 text-sm font-bold text-slate-600 hover:bg-slate-100 transition disabled:opacity-50"
            >
              취소
            </button>
            <button
              type="button"
              disabled={selectedIndex === null || selecting}
              onClick={() => selectedIndex !== null && onSelect(selectedIndex)}
              className="rounded-xl bg-sky-500 px-5 py-2.5 text-sm font-bold text-white transition enabled:hover:bg-sky-600 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
            >
              {selecting ? '합성 시작 중...' : '선택하고 합성 시작'}
            </button>
          </div>
        </div>
      </div>

      {/* 라이트박스 */}
      {lightboxIndex !== null && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90"
          onClick={closeLightbox}
        >
          {/* 닫기 버튼 */}
          <button
            type="button"
            onClick={closeLightbox}
            className="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>

          {/* 이전 버튼 */}
          {previews.length > 1 && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); moveLightbox(-1); }}
              className="absolute left-4 w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="m15 18-6-6 6-6" />
              </svg>
            </button>
          )}

          {/* 이미지 */}
          <div className="flex flex-col items-center gap-3 px-16" onClick={(e) => e.stopPropagation()}>
            <img
              src={previews[lightboxIndex].url}
              alt={`프리뷰 ${lightboxIndex + 1}`}
              className="max-w-full max-h-[80vh] rounded-xl shadow-2xl object-contain"
            />
            <span className="text-white/70 text-sm font-medium">
              프리뷰 {lightboxIndex + 1} / {previews.length}
            </span>
          </div>

          {/* 다음 버튼 */}
          {previews.length > 1 && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); moveLightbox(1); }}
              className="absolute right-4 w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="m9 18 6-6-6-6" />
              </svg>
            </button>
          )}
        </div>
      )}
    </>
  );
}
