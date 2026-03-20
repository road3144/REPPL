import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { JobCreateForm } from '../components/studio/JobCreateForm';
import { useDemoJobs } from '../hooks/useDemoJobs';
import { JobItem, JobStatusResponse } from '../services/demoApi';

/* ─── types ─── */
type Tab = 'all' | 'active' | 'done';

/* ─── status config ─── */
const STATUS_CFG: Record<string, { label: string; dotColor: string; badgeCls: string; progressCls: string }> = {
  QUEUED:    { label: '대기 중',  dotColor: '#94a3b8', badgeCls: 'bg-slate-100 text-slate-500',    progressCls: 'bg-slate-300' },
  RUNNING:   { label: '처리 중',  dotColor: '#f59e0b', badgeCls: 'bg-amber-50 text-amber-600',      progressCls: 'bg-amber-400' },
  COMPLETED: { label: '완료',     dotColor: '#10b981', badgeCls: 'bg-emerald-50 text-emerald-600',  progressCls: 'bg-emerald-400' },
  FAILED:    { label: '실패',     dotColor: '#ef4444', badgeCls: 'bg-red-50 text-red-500',          progressCls: 'bg-red-400' },
};

/* ─── AI pipeline steps (shown in preview panel) ─── */
const PIPELINE_STEPS = [
  '첫 프레임 Gemini 합성',
  'Grounding DINO 객체 검출',
  'SAM 마스크 추출',
  'Lucas-Kanade 전체 프레임 추적',
  '최종 합성 출력',
];

/* ─── sidebar nav items ─── */
const SIDEBAR_ITEMS = [
  {
    id: 'studio',
    label: '작업 스튜디오',
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <rect x="2" y="3" width="20" height="14" rx="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" />
      </svg>
    ),
  },
  {
    id: 'results',
    label: '내 결과물',
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
      </svg>
    ),
  },
  {
    id: 'history',
    label: '작업 내역',
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
      </svg>
    ),
  },
];

/* ─── helpers ─── */
function getProgressValue(job: JobItem): number {
  if (job.progress != null) return job.progress;
  const cfg = STATUS_CFG[job.status];
  if (!cfg) return 0;
  if (job.status === 'QUEUED') return 5;
  if (job.status === 'RUNNING') return 50;
  if (job.status === 'COMPLETED') return 100;
  return 0;
}

function getPipelineStepIndex(job: JobItem): number {
  const progress = getProgressValue(job);
  if (job.status === 'COMPLETED') return PIPELINE_STEPS.length;
  if (job.status === 'QUEUED') return 0;
  // map 0-100 progress to 0-4 step index
  return Math.min(Math.floor((progress / 100) * PIPELINE_STEPS.length), PIPELINE_STEPS.length - 1);
}

function formatTime(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/* ─── sub-components ─── */

function WorkspaceTopNav({ activeJobs }: { activeJobs: number }) {
  return (
    <header className="h-14 flex-shrink-0 bg-white border-b border-slate-200 flex items-center justify-between px-5 shadow-[0_1px_3px_rgba(0,0,0,0.05)]">
      <div className="flex items-center gap-6">
        <Link to="/" className="text-lg font-black text-slate-900 pr-6 border-r border-slate-200">
          VP<span className="text-brand">PL</span>
        </Link>
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <span>작업 스튜디오</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-800 font-semibold">새 작업 만들기</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {activeJobs > 0 && (
          <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-600 bg-amber-50 px-3 py-1.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            {activeJobs}개 처리 중
          </div>
        )}
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand to-brand-light flex items-center justify-center text-white text-xs font-bold">
          U
        </div>
      </div>
    </header>
  );
}

function Sidebar({ activeItem, onSelect }: { activeItem: string; onSelect: (id: string) => void }) {
  return (
    <aside className="w-[220px] flex-shrink-0 bg-white border-r border-slate-200 flex flex-col">
      <div className="p-4 pt-5">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-2 mb-2">메뉴</p>
        {SIDEBAR_ITEMS.map(({ id, label, icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => onSelect(id)}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors mb-0.5 ${
              activeItem === id
                ? 'bg-blue-50 text-brand font-semibold'
                : 'text-slate-500 hover:bg-slate-50'
            }`}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      <div className="mt-auto p-4 border-t border-slate-100">
        <p className="text-xs text-slate-400 font-semibold mb-3">이번 달 사용량</p>
        <div className="flex justify-between text-xs text-slate-500 mb-1.5">
          <span>3 / 10 작업</span>
          <span className="text-brand font-bold">30%</span>
        </div>
        <div className="h-1 bg-slate-100 rounded-full">
          <div className="h-1 w-[30%] bg-brand rounded-full" />
        </div>
      </div>
    </aside>
  );
}

function JobCard({
  job,
  selected,
  onClick,
  onDownload,
}: {
  job: JobItem;
  selected: boolean;
  onClick: () => void;
  onDownload: (jobId: string) => void;
}) {
  const cfg = STATUS_CFG[job.status] ?? STATUS_CFG['QUEUED'];
  const progress = getProgressValue(job);

  return (
    <article
      onClick={onClick}
      className={`rounded-2xl border p-5 cursor-pointer transition-all ${
        selected
          ? 'border-brand shadow-[0_0_0_3px_rgba(74,108,247,0.12)]'
          : 'border-slate-200 hover:border-blue-200 hover:shadow-brand-sm'
      } bg-white`}
    >
      {/* top row */}
      <div className="flex items-start gap-3">
        {/* video thumb placeholder */}
        <div className="w-20 h-13 rounded-lg flex-shrink-0 overflow-hidden" style={{ background: 'linear-gradient(135deg, #1a1a2e, #0d0d1a)', minHeight: '52px' }} />

        <div className="flex-1 min-w-0">
          <p className="text-sm font-bold text-slate-800 truncate" title={job.jobId}>
            작업 {job.jobId.slice(0, 8)}
          </p>
          <p className="text-xs text-slate-400 mt-0.5">{formatTime(job.createdAt)}</p>
        </div>

        <span className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${cfg.badgeCls}`}>
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.dotColor }} />
          {cfg.label}
        </span>
      </div>

      {/* progress bar */}
      <div className="mt-4">
        <div className="flex justify-between text-xs text-slate-400 mb-1.5">
          <span className="truncate pr-2">{job.stage ?? job.message ?? '파이프라인 대기 중'}</span>
          <span className="font-bold flex-shrink-0">{progress}%</span>
        </div>
        <div className="h-1 bg-slate-100 rounded-full">
          <div
            className={`h-1 rounded-full transition-all duration-500 ${cfg.progressCls}`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* actions */}
      <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onClick(); }}
          className="text-xs font-semibold text-slate-500 border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors"
        >
          미리보기
        </button>
        {job.status === 'COMPLETED' && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDownload(job.jobId); }}
            className="text-xs font-bold text-white bg-brand px-4 py-1.5 rounded-lg hover:bg-brand-dark transition-colors"
          >
            다운로드
          </button>
        )}
      </div>
    </article>
  );
}

function PreviewPanel({
  job,
  onClose,
  onDownload,
}: {
  job: JobItem;
  onClose: () => void;
  onDownload: (jobId: string) => void;
}) {
  const cfg = STATUS_CFG[job.status] ?? STATUS_CFG['QUEUED'];
  const progress = getProgressValue(job);
  const activeStep = getPipelineStepIndex(job);

  return (
    <aside className="w-[400px] flex-shrink-0 bg-white border-l border-slate-200 flex flex-col overflow-y-auto shadow-[-4px_0_20px_rgba(0,0,0,0.05)]">
      {/* header */}
      <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100">
        <div>
          <h3 className="text-sm font-bold text-slate-800">작업 {job.jobId.slice(0, 8)}</h3>
          <p className="text-xs text-slate-400 mt-0.5">{formatTime(job.createdAt)}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 transition-colors text-lg leading-none"
        >
          ×
        </button>
      </div>

      {/* video placeholder */}
      <div
        className="mx-5 mt-5 rounded-xl overflow-hidden flex items-center justify-center relative"
        style={{ aspectRatio: '16/9', background: 'linear-gradient(135deg, #1a1a2e, #0d0d1a)' }}
      >
        <div className="w-12 h-12 rounded-full border-2 border-white/30 bg-white/10 flex items-center justify-center cursor-pointer hover:bg-white/20 transition-colors">
          <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5 ml-0.5">
            <polygon points="5,3 19,12 5,21" fill="rgba(255,255,255,0.8)" />
          </svg>
        </div>
        <p className="absolute bottom-2 left-4 text-[10px] text-white/30 tracking-widest uppercase">합성 결과 미리보기</p>
      </div>

      {/* before/after toggle */}
      <div className="mx-5 mt-3 flex border border-slate-200 rounded-lg overflow-hidden text-xs font-semibold">
        <div className="flex-1 text-center py-2 bg-brand text-white">합성 결과</div>
        <div className="flex-1 text-center py-2 text-slate-400 cursor-pointer hover:bg-slate-50 transition-colors">원본 비교</div>
      </div>

      {/* pipeline steps */}
      <div className="px-6 mt-6">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">처리 단계</p>
        <div className="space-y-3">
          {PIPELINE_STEPS.map((step, i) => {
            const isDone = i < activeStep;
            const isActive = i === activeStep && job.status === 'RUNNING';
            const isPending = !isDone && !isActive;
            return (
              <div key={step} className="flex items-center gap-3">
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-bold ${
                    isDone
                      ? 'bg-emerald-400 text-white'
                      : isActive
                      ? 'bg-brand text-white'
                      : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {isDone ? '✓' : isActive ? '⟳' : '○'}
                </div>
                <span className={`text-xs ${isDone ? 'text-slate-600' : isActive ? 'text-brand font-semibold' : 'text-slate-400'}`}>
                  {step}
                  {isActive && progress > 0 && ` (${progress}%)`}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* info table */}
      <div className="px-6 mt-6">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">작업 정보</p>
        <div className="space-y-0">
          {[
            { key: 'Job ID', val: job.jobId },
            { key: '상태', val: cfg.label },
            { key: '진행률', val: `${progress}%` },
            { key: '생성 시각', val: formatTime(job.createdAt) },
          ].map(({ key, val }) => (
            <div key={key} className="flex justify-between py-2.5 border-b border-slate-100 last:border-b-0">
              <span className="text-xs text-slate-400">{key}</span>
              <span className="text-xs font-semibold text-slate-700 text-right max-w-[180px] truncate" title={val}>{val}</span>
            </div>
          ))}
        </div>
      </div>

      {/* actions */}
      <div className="px-5 py-5 mt-auto space-y-2.5 border-t border-slate-100">
        <button
          type="button"
          onClick={() => job.status === 'COMPLETED' && onDownload(job.jobId)}
          disabled={job.status !== 'COMPLETED'}
          className="w-full py-3 rounded-xl text-sm font-bold text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ background: '#10b981' }}
        >
          결과 다운로드
          {job.status !== 'COMPLETED' && ' (처리 완료 후)'}
        </button>
        <button
          type="button"
          className="w-full py-3 rounded-xl text-sm font-semibold text-slate-600 border border-slate-200 hover:bg-slate-50 transition-colors"
        >
          링크 공유
        </button>
      </div>
    </aside>
  );
}

/* ─── main page ─── */
export function WorkspacePage() {
  const { jobs, running, loadingJobs, errorMessage, setErrorMessage, prependCreatedJob, downloadResult } =
    useDemoJobs();

  const [activeTab, setActiveTab] = useState<Tab>('all');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [sidebarActive, setSidebarActive] = useState('studio');

  const filteredJobs = useMemo(() => {
    if (activeTab === 'active') return jobs.filter((j) => j.status === 'QUEUED' || j.status === 'RUNNING');
    if (activeTab === 'done') return jobs.filter((j) => j.status === 'COMPLETED');
    return jobs;
  }, [jobs, activeTab]);

  const activeCount = jobs.filter((j) => j.status === 'QUEUED' || j.status === 'RUNNING').length;
  const doneCount = jobs.filter((j) => j.status === 'COMPLETED').length;

  const selectedJob = jobs.find((j) => j.jobId === selectedJobId) ?? null;

  const handleCreated = (status: JobStatusResponse) => {
    prependCreatedJob(status);
    setActiveTab('active');
  };

  const handleDownload = async (jobId: string) => {
    try {
      await downloadResult(jobId);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : '다운로드에 실패했습니다.');
    }
  };

  const TABS: { id: Tab; label: string; count: number }[] = [
    { id: 'all',    label: '전체',   count: jobs.length },
    { id: 'active', label: '진행 중', count: activeCount },
    { id: 'done',   label: '완료됨',  count: doneCount },
  ];

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-50">
      <WorkspaceTopNav activeJobs={running} />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeItem={sidebarActive} onSelect={setSidebarActive} />

        {/* ── main area ── */}
        <div className="flex flex-1 overflow-hidden">

          {/* upload panel */}
          <div className="w-[380px] flex-shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
            <div className="px-6 pt-5 pb-4 border-b border-slate-100">
              <h2 className="text-base font-bold text-slate-800">새 작업 만들기</h2>
              <p className="text-xs text-slate-400 mt-1">영상과 상품 이미지를 업로드하세요</p>
            </div>
            <div className="flex-1 p-6">
              <JobCreateForm onCreated={handleCreated} onError={setErrorMessage} />
              {errorMessage && (
                <p className="mt-3 text-xs text-red-500">{errorMessage}</p>
              )}
            </div>
          </div>

          {/* job list */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* tabs */}
            <div className="flex-shrink-0 bg-white border-b border-slate-200 flex items-center px-6 gap-1">
              {TABS.map(({ id, label, count }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setActiveTab(id)}
                  className={`flex items-center gap-2 px-5 py-4 text-sm font-semibold border-b-2 -mb-px transition-colors ${
                    activeTab === id
                      ? 'text-brand border-brand'
                      : 'text-slate-400 border-transparent hover:text-slate-600'
                  }`}
                >
                  {label}
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                      activeTab === id ? 'bg-blue-50 text-brand' : 'bg-slate-100 text-slate-400'
                    }`}
                  >
                    {count}
                  </span>
                </button>
              ))}
            </div>

            {/* job cards */}
            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {loadingJobs && (
                <div className="flex items-center justify-center py-16 gap-3 text-sm text-slate-400">
                  <div className="w-4 h-4 border-2 border-slate-300 border-t-brand rounded-full animate-spin" />
                  작업 목록 불러오는 중...
                </div>
              )}

              {!loadingJobs && filteredJobs.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center text-2xl mb-4">📋</div>
                  <p className="text-sm font-semibold text-slate-500">작업이 없습니다</p>
                  <p className="text-xs text-slate-400 mt-1">
                    {activeTab === 'active' ? '현재 진행 중인 작업이 없습니다' : activeTab === 'done' ? '완료된 작업이 없습니다' : '왼쪽 패널에서 새 작업을 만드세요'}
                  </p>
                </div>
              )}

              {filteredJobs.map((job) => (
                <JobCard
                  key={job.jobId}
                  job={job}
                  selected={job.jobId === selectedJobId}
                  onClick={() => setSelectedJobId((prev) => (prev === job.jobId ? null : job.jobId))}
                  onDownload={handleDownload}
                />
              ))}
            </div>
          </div>

          {/* preview panel — slide in when job selected */}
          {selectedJob && (
            <PreviewPanel
              job={selectedJob}
              onClose={() => setSelectedJobId(null)}
              onDownload={handleDownload}
            />
          )}
        </div>
      </div>
    </div>
  );
}
