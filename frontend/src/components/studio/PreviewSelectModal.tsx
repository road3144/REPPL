import { useState } from 'react';
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

  return (
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

        <div className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-4">
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
  );
}
