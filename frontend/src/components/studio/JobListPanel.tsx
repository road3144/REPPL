import { TrackedJob } from '../../hooks/useJobs';
import { formatStage } from '../../constants/stage';

type JobListPanelProps = {
  jobs: TrackedJob[];
  loadingJobs: boolean;
  onDownload: (jobId: string) => void;
  onViewPreviews: (jobId: string) => void;
};

const statusConfig: Record<string, { color: string; label: string; progress: number }> = {
  QUEUED: { color: 'sky', label: '대기중', progress: 15 },
  RUNNING: { color: 'amber', label: '처리중', progress: 55 },
  COMPLETED: { color: 'emerald', label: '완료', progress: 100 },
  FAILED: { color: 'rose', label: '실패', progress: 100 },
};

const jobTypeLabel: Record<string, string> = {
  PREVIEW: '프리뷰',
  COMPOSITE: '합성',
};

export function JobListPanel({ jobs, loadingJobs, onDownload, onViewPreviews }: JobListPanelProps) {
  return (
    <section className="light-slide-card h-full">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-black text-slate-900">작업 현황</h2>
        <span className="text-xs font-bold text-slate-400">{jobs.length}건</span>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        프리뷰 완료 후 원하는 결과를 선택하면 최종 합성이 시작됩니다.
      </p>

      <div className="mt-5 space-y-3 max-h-[520px] overflow-y-auto pr-1" aria-live="polite">
        {loadingJobs && (
          <div className="flex items-center justify-center py-8">
            <div className="loading-spinner" />
            <span className="ml-3 text-sm text-slate-500">작업 목록 불러오는 중...</span>
          </div>
        )}

        {!loadingJobs && jobs.length === 0 && (
          <div className="empty-state">
            <span className="empty-state-icon">📋</span>
            <p className="text-sm font-semibold text-slate-600">아직 등록된 작업이 없습니다</p>
            <p className="text-xs text-slate-400 mt-1">왼쪽에서 첫 작업을 생성하세요</p>
          </div>
        )}

        {jobs.map((job) => {
          const config = statusConfig[job.status] ?? { color: 'slate', label: job.status, progress: 0 };
          const progressValue = job.progress ?? config.progress;
          const isPreviewCompleted = job.status === 'COMPLETED' && job.jobType === 'PREVIEW';
          const isCompositeCompleted = job.status === 'COMPLETED' && job.jobType === 'COMPOSITE';

          return (
            <article key={job.jobId} className="job-card">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 shrink-0">
                    {jobTypeLabel[job.jobType] ?? job.jobType}
                  </span>
                  <p className="text-sm font-bold text-slate-800 truncate" title={job.jobId}>
                    {job.jobId.slice(0, 8)}...
                  </p>
                </div>
                <span className={`job-status-badge job-status-${config.color}`}>
                  {config.label}
                </span>
              </div>

              {/* Progress bar */}
              <div className="mt-3 job-progress-track">
                <div
                  className={`job-progress-fill job-progress-${config.color}`}
                  style={{ width: `${progressValue}%` }}
                />
              </div>
              <div className="mt-1.5 flex items-center justify-between">
                <p className="text-xs text-slate-500">
                  {job.stage ? (formatStage(job.stage) ?? job.stage) : job.message ?? '파이프라인 대기 중'}
                </p>
                <p className="text-xs font-bold text-slate-500">{progressValue}%</p>
              </div>

              {/* 프리뷰 완료 → 프리뷰 선택 버튼 */}
              {isPreviewCompleted && (
                <button
                  type="button"
                  onClick={() => onViewPreviews(job.jobId)}
                  className="mt-3 w-full download-btn"
                  style={{ background: 'linear-gradient(135deg, #7c3aed, #6366f1)' }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                    <path d="m9 12 2 2 4-4" />
                  </svg>
                  프리뷰 선택하기
                </button>
              )}

              {/* 합성 완료 → 다운로드 버튼 */}
              {isCompositeCompleted && (
                <button
                  type="button"
                  onClick={() => onDownload(job.jobId)}
                  className="mt-3 w-full download-btn"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  결과 영상 다운로드
                </button>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
