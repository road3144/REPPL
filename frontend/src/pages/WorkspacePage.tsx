import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { JobCreateForm } from '../components/studio/JobCreateForm';
import { PreviewSelectModal } from '../components/studio/PreviewSelectModal';
import { JobStagePanel } from '../components/studio/JobStagePanel';
import { useJobs } from '../hooks/useJobs';
import { formatStage } from '../constants/stage';
import type { JobItem } from '../services/types';

/* ── Status config ── */
const STATUS_CFG: Record<string, { label: string; badgeCls: string; progressCls: string }> = {
  QUEUED:    { label: '대기 중', badgeCls: 'job-status-slate',   progressCls: 'job-progress-slate' },
  RUNNING:   { label: '처리 중', badgeCls: 'job-status-amber',   progressCls: 'job-progress-amber' },
  COMPLETED: { label: '완료',   badgeCls: 'job-status-emerald', progressCls: 'job-progress-emerald' },
  FAILED:    { label: '실패',   badgeCls: 'job-status-rose',    progressCls: 'job-progress-rose' },
};

type Tab = 'all' | 'running' | 'waiting' | 'done';

function FileStackIcon({ className = 'w-7 h-7' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M8 3h8l4 4v11a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" />
      <path d="M16 3v5h5" />
      <path d="M10 12h4" />
      <path d="M10 16h4" />
    </svg>
  );
}

function CheckCircleIcon({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12 2.3 2.3 4.7-4.8" />
    </svg>
  );
}

function VideoPanelIcon({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3" y="6" width="13" height="12" rx="2" />
      <path d="m16 10 5-3v10l-5-3z" />
    </svg>
  );
}

export function WorkspacePage() {
  const {
    jobs, loadingJobs, errorMessage, setErrorMessage,
    prependCreatedJob, downloadResult, getPlaybackUrl,
    previewSelecting, selectingIndex, loadPreviews, handleSelectPreview, closePreviewSelection,
  } = useJobs();

  /* ── Video player modal ── */
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);

  const openPlayer = async (jobId: string) => {
    try {
      const url = await getPlaybackUrl(jobId);
      setPlaybackUrl(url);
    } catch {
      setErrorMessage('영상 재생 URL을 가져올 수 없습니다.');
    }
  };

  const [tab, setTab] = useState<Tab>('all');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  /* ── Prompt validation modal ── */
  const [promptError, setPromptError] = useState<string | null>(null);

  /* ── Completion toast ── */
  const [toast, setToast] = useState<{ jobId: string } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevJobsRef = useRef<JobItem[]>([]);

  /* Detect status transitions */
  useEffect(() => {
    for (const job of jobs) {
      const prev = prevJobsRef.current.find(p => p.jobId === job.jobId);
      if (!prev) continue;

      // VALIDATE 실패 → 모달
      if (job.status === 'FAILED' && job.stage === 'VALIDATE' && prev.status !== 'FAILED') {
        setPromptError(job.message ?? '제품 배치와 관련된 프롬프트를 입력해주세요.');
      }

      // 완료 → 토스트
      if (job.status === 'COMPLETED' && (prev.status === 'RUNNING' || prev.status === 'QUEUED')) {
        setToast({ jobId: job.jobId });
        if (toastTimer.current) clearTimeout(toastTimer.current);
        toastTimer.current = setTimeout(() => setToast(null), 5000);
      }
    }
    prevJobsRef.current = jobs;
  }, [jobs]);

  const filteredJobs = useMemo(() => {
    if (tab === 'running') return jobs.filter(j => j.status === 'RUNNING');
    if (tab === 'waiting') return jobs.filter(j => j.status === 'QUEUED');
    if (tab === 'done') return jobs.filter(j => j.status === 'COMPLETED' || j.status === 'FAILED');
    return jobs;
  }, [jobs, tab]);

  useEffect(() => {
    if (jobs.length === 0) {
      setSelectedJobId(null);
      return;
    }

    if (selectedJobId && jobs.some((job) => job.jobId === selectedJobId)) {
      return;
    }

    const nextSelectedJob = jobs.find((job) => job.status === 'RUNNING')
      ?? jobs.find((job) => job.status === 'QUEUED')
      ?? jobs[0];

    setSelectedJobId(nextSelectedJob.jobId);
  }, [jobs, selectedJobId]);

  const selectedJob = jobs.find((job) => job.jobId === selectedJobId) ?? null;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#f0f2f8' }}>

      {/* LEFT PANEL — 새 작업 만들기 */}
      <div style={{
        width: 400, flexShrink: 0, background: '#fff', borderRight: '1px solid #e5e7ef',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        <div style={{ padding: '20px 24px 14px', borderBottom: '1px solid #f0f0f5' }}>
          <Link to="/" style={{ textDecoration: 'none', display: 'inline-block', marginBottom: 18 }}>
            <span style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 24,
              fontWeight: 900,
              letterSpacing: '-0.5px',
              color: '#111',
            }}>
              Re:<span style={{ color: '#4a6cf7' }}>PPL</span>
            </span>
          </Link>
          <h2 style={{ fontSize: 15, fontWeight: 700, color: '#111', margin: 0 }}>새 작업 만들기</h2>
          <p style={{ fontSize: 12, color: '#999', marginTop: 4 }}>영상과 광고 이미지를 업로드하세요</p>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          <JobCreateForm
            onCreated={prependCreatedJob}
            onError={setErrorMessage}
            className="p-5"
          />
        </div>

        {errorMessage && (
          <div style={{
            padding: '10px 20px', background: '#fff5f5', borderTop: '1px solid #fecaca',
            fontSize: 12, color: '#ef4444', display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{ flex: 1 }}>{errorMessage}</span>
            <button
              onClick={() => setErrorMessage(null)}
              style={{ background: 'none', border: 'none', color: '#ef4444', fontWeight: 700, cursor: 'pointer', fontSize: 16 }}
            >×</button>
          </div>
        )}
      </div>

      {/* RIGHT PANEL — 나의 작업들 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Header + filter tabs */}
        <div style={{
          padding: '16px 24px', background: '#fff', borderBottom: '1px solid #e5e7ef',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0,
        }}>
          <div>
            <span style={{ fontSize: 15, fontWeight: 700, color: '#111' }}>나의 작업들</span>
            <span style={{ fontSize: 13, color: '#aaa', marginLeft: 8 }}>· {jobs.length}개</span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {([
              ['all', '전체'],
              ['running', '처리 중'],
              ['waiting', '대기 중'],
              ['done', '완료'],
            ] as [Tab, string][]).map(([t, label]) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                style={{
                  padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                  background: tab === t ? '#4a6cf7' : '#f0f2f8',
                  color: tab === t ? '#fff' : '#888',
                  border: 'none', cursor: 'pointer', transition: 'all 0.15s',
                }}
              >{label}</button>
            ))}
          </div>
        </div>

        {/* Job list + stage panel */}
        <div className="workspace-right-content">
          <div className="workspace-job-list">
            {loadingJobs && (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
                <div className="loading-spinner" />
              </div>
            )}
            {!loadingJobs && filteredJobs.length === 0 && (
              <div className="empty-state">
                <span className="empty-state-icon" aria-hidden="true">
                  <FileStackIcon />
                </span>
                <p style={{ fontSize: 14, fontWeight: 600, color: '#64748b' }}>작업이 없습니다</p>
                <p style={{ fontSize: 12, color: '#94a3b8' }}>왼쪽에서 새 작업을 만들어보세요</p>
              </div>
            )}
            {filteredJobs.map(job => (
              <JobCard
                key={job.jobId}
                job={job}
                selected={job.jobId === selectedJobId}
                onSelect={() => setSelectedJobId(job.jobId)}
                onDownload={downloadResult}
                onPlay={openPlayer}
                onSelectPreview={loadPreviews}
              />
            ))}
          </div>
          <JobStagePanel
            job={selectedJob}
            onOpenPreview={loadPreviews}
            onDownload={(jobId) => { void downloadResult(jobId); }}
          />
        </div>
      </div>

      {/* ── VIDEO PLAYER MODAL ── */}
      {playbackUrl && (
        <>
          <div
            onClick={() => setPlaybackUrl(null)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 400 }}
          />
          <div style={{
            position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
            background: '#111', borderRadius: 16, zIndex: 401,
            width: '80vw', maxWidth: 900, boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
            animation: 'slideUpToast 0.2s ease', overflow: 'hidden',
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '12px 16px', background: '#1a1a2e',
            }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>영상 미리보기</span>
              <button
                onClick={() => setPlaybackUrl(null)}
                style={{ background: 'none', border: 'none', color: '#aaa', fontSize: 22, cursor: 'pointer', lineHeight: 1 }}
              >×</button>
            </div>
            <video
              src={playbackUrl}
              controls
              autoPlay
              style={{ width: '100%', display: 'block', maxHeight: '70vh', background: '#000' }}
            />
          </div>
        </>
      )}

      {/* ── PROMPT ERROR MODAL ── */}
      {promptError && (
        <>
          <div
            onClick={() => setPromptError(null)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 300 }}
          />
          <div style={{
            position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
            background: '#fff', borderRadius: 16, padding: '32px 28px', zIndex: 301,
            width: 400, maxWidth: '90vw', boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
            animation: 'slideUpToast 0.2s ease',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10,
                background: 'linear-gradient(135deg, #ef4444, #f97316)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 20, flexShrink: 0,
              }}>!</div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: '#111', margin: 0 }}>
                프롬프트를 확인해주세요
              </h3>
            </div>
            <p style={{ fontSize: 14, color: '#555', lineHeight: 1.6, margin: 0 }}>
              {promptError}
            </p>
            <p style={{ fontSize: 12, color: '#999', marginTop: 12, lineHeight: 1.5 }}>
              예시: "책상 위 빈 공간에 놓아줘", "테이블 오른쪽 컵 옆에 배치해줘"
            </p>
            <button
              onClick={() => setPromptError(null)}
              style={{
                marginTop: 20, width: '100%', padding: 12,
                background: '#4a6cf7', color: '#fff', border: 'none',
                borderRadius: 10, fontSize: 14, fontWeight: 700, cursor: 'pointer',
              }}
            >
              확인
            </button>
          </div>
        </>
      )}

      {/* ── PREVIEW SELECT MODAL ── */}
      {previewSelecting && (
        <PreviewSelectModal
          jobId={previewSelecting.jobId}
          previews={previewSelecting.previews}
          selecting={selectingIndex}
          onSelect={(index) => handleSelectPreview(previewSelecting.jobId, index)}
          onClose={closePreviewSelection}
        />
      )}

      {/* ── COMPLETION TOAST ── */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 28, right: 28, zIndex: 200,
          background: '#1e1e2e', color: '#fff', borderRadius: 16,
          padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 12,
          boxShadow: '0 8px 32px rgba(0,0,0,0.35), 0 0 0 1px rgba(74,108,247,0.2)',
          minWidth: 300, maxWidth: 340, overflow: 'hidden',
          animation: 'slideUpToast 0.3s ease',
        }}>
          <div style={{
            position: 'absolute', bottom: 0, left: 0, height: 3,
            background: '#4a6cf7', borderRadius: '0 3px 3px 0',
            animation: 'shrinkBar 5s linear forwards',
          }} />

          <div style={{
            width: 38, height: 38, borderRadius: 10, background: '#4a6cf7',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0, color: '#fff',
          }}>
            <CheckCircleIcon />
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 700 }}>합성이 완료되었습니다!</div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              결과물을 다운로드할 수 있습니다
            </div>
          </div>

          <button
            onClick={() => { setToast(null); if (toastTimer.current) clearTimeout(toastTimer.current); }}
            style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.35)', fontSize: 20, cursor: 'pointer', flexShrink: 0, lineHeight: 1 }}
          >×</button>
        </div>
      )}
    </div>
  );
}

/* ── Job Card component ── */
function JobCard({ job, selected, onSelect, onDownload, onPlay, onSelectPreview }: {
  job: JobItem;
  selected: boolean;
  onSelect: () => void;
  onDownload: (id: string) => Promise<void>;
  onPlay: (id: string) => Promise<void>;
  onSelectPreview: (id: string) => void;
}) {
  const cfg = STATUS_CFG[job.status] ?? STATUS_CFG['QUEUED'];
  const progress = job.progress ?? (job.status === 'COMPLETED' ? 100 : 0);
  const isPreviewCompleted = job.jobType === 'PREVIEW' && job.status === 'COMPLETED';
  const isCompositeCompleted = job.jobType === 'COMPOSITE' && job.status === 'COMPLETED';

  return (
    <div
      className={`job-card ${selected ? 'job-card-selected' : ''}`}
      style={{ display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer' }}
      onClick={onSelect}
    >
      {/* Thumbnail */}
      <div style={{
        width: 80, height: 52, borderRadius: 8,
        background: 'linear-gradient(135deg, #1a1a2e, #0d0d1a)',
        flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,0.92)',
      }}>
        <VideoPanelIcon />
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#111', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {job.jobId}
          </span>
          {job.jobType && (
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 4,
              background: job.jobType === 'PREVIEW' ? '#ede9fe' : '#ecfdf5',
              color: job.jobType === 'PREVIEW' ? '#7c3aed' : '#059669',
            }}>
              {job.jobType === 'PREVIEW' ? '프리뷰' : '합성'}
            </span>
          )}
        </div>
        {job.message && (
          <div style={{ fontSize: 12, color: '#aaa', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {job.message}
          </div>
        )}
        {job.stage && (
          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{formatStage(job.stage)}</div>
        )}
        {job.createdAt && (
          <div style={{ fontSize: 11, color: '#ccc', marginTop: 4 }}>
            {new Date(job.createdAt).toLocaleString('ko-KR')}
          </div>
        )}
        {(job.status === 'RUNNING' || job.status === 'COMPLETED') && (
          <div style={{ marginTop: 6 }}>
            <div className="job-progress-track">
              <div className={`job-progress-fill ${cfg.progressCls}`} style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}
      </div>

      {/* Status + action */}
      <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
        <span className={`job-status-badge ${cfg.badgeCls}`}>{cfg.label}</span>
        {job.status === 'RUNNING' && (
          <span style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b' }}>{progress}%</span>
        )}
        {isPreviewCompleted && (
          <button className="download-btn" onClick={(event) => { event.stopPropagation(); onSelectPreview(job.jobId); }}>
            프리뷰 선택
          </button>
        )}
        {isCompositeCompleted && (
          <div style={{ display: 'flex', gap: 4 }}>
            <button className="download-btn" onClick={(event) => { event.stopPropagation(); void onPlay(job.jobId); }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polygon points="6,3 20,12 6,21" />
              </svg>
              재생
            </button>
            <button className="download-btn" onClick={(event) => { event.stopPropagation(); void onDownload(job.jobId); }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 5v14M5 12l7 7 7-7" />
              </svg>
              다운로드
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
