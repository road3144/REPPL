import { JobItem } from '../../services/demoApi';

type JobListPanelProps = {
  jobs: JobItem[];
  loadingJobs: boolean;
  onDownload: (jobId: string) => void;
};

const statusStyle: Record<string, string> = {
  QUEUED: 'text-sky-700',
  RUNNING: 'text-amber-600',
  COMPLETED: 'text-emerald-600',
  FAILED: 'text-rose-600'
};

const statusLabel: Record<string, string> = {
  QUEUED: '대기중',
  RUNNING: '처리중',
  COMPLETED: '완료',
  FAILED: '실패'
};

export function JobListPanel({ jobs, loadingJobs, onDownload }: JobListPanelProps) {
  return (
    <section className="light-slide-card">
      <h2 className="text-2xl font-black text-slate-900">작업 현황</h2>
      <div className="mt-5 space-y-3" aria-live="polite">
        {loadingJobs ? <p className="text-sm text-slate-500">작업 목록을 불러오는 중입니다...</p> : null}
        {jobs.map((job) => (
          <article key={job.jobId} className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-bold text-slate-800">{job.jobId}</p>
              <span className={`text-sm font-black ${statusStyle[job.status] ?? 'text-slate-600'}`}>
                {statusLabel[job.status] ?? job.status}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              진행률: {job.progress ?? 0}% {job.stage ? `(${job.stage})` : ''}
            </p>
            <p className="mt-1 text-xs text-slate-500">{job.message ?? '처리 중입니다.'}</p>
            {job.status === 'COMPLETED' ? (
              <button
                type="button"
                onClick={() => onDownload(job.jobId)}
                className="mt-3 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-bold text-white transition hover:bg-emerald-600"
              >
                결과 다운로드
              </button>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
