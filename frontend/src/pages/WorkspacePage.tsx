import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { JobCreateForm } from '../components/studio/JobCreateForm';
import { useDemoJobs } from '../hooks/useDemoJobs';
import {
  CandidateFrame,
  createJob,
  getCandidateFrames,
  getJobStatus,
  JobItem,
} from '../services/demoApi';

/* ── Status config ── */
const STATUS_CFG: Record<string, { label: string; badgeCls: string; progressCls: string }> = {
  QUEUED:    { label: '대기 중', badgeCls: 'job-status-slate',   progressCls: 'job-progress-slate' },
  RUNNING:   { label: '처리 중', badgeCls: 'job-status-amber',   progressCls: 'job-progress-amber' },
  COMPLETED: { label: '완료',   badgeCls: 'job-status-emerald', progressCls: 'job-progress-emerald' },
  FAILED:    { label: '실패',   badgeCls: 'job-status-rose',    progressCls: 'job-progress-rose' },
};

type Tab = 'all' | 'running' | 'waiting' | 'done';

type UploadedInfo = {
  videoKey: string;
  imageKey: string;
  prompt: string;
};

export function WorkspacePage() {
  const { jobs, loadingJobs, errorMessage, setErrorMessage, prependCreatedJob, downloadResult } = useDemoJobs();

  const [tab, setTab] = useState<Tab>('all');

  /* ── Candidate drawer state ── */
  const [uploadedInfo, setUploadedInfo] = useState<UploadedInfo | null>(null);
  const [candidates, setCandidates] = useState<CandidateFrame[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<string | null>(null);
  const [confirmingJob, setConfirmingJob] = useState(false);

  /* ── Completion toast ── */
  const [toast, setToast] = useState<{ jobId: string } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevJobsRef = useRef<JobItem[]>([]);

  /* Detect RUNNING/QUEUED → COMPLETED transition */
  useEffect(() => {
    const justCompleted = jobs.find(job =>
      job.status === 'COMPLETED' &&
      prevJobsRef.current.some(p => p.jobId === job.jobId && (p.status === 'RUNNING' || p.status === 'QUEUED'))
    );
    if (justCompleted) {
      setToast({ jobId: justCompleted.jobId });
      if (toastTimer.current) clearTimeout(toastTimer.current);
      toastTimer.current = setTimeout(() => setToast(null), 5000);
    }
    prevJobsRef.current = jobs;
  }, [jobs]);

  /* After upload → fetch mock candidate frames → open drawer */
  const handleUploaded = async (videoKey: string, imageKey: string, prompt: string) => {
    setUploadedInfo({ videoKey, imageKey, prompt });
    setLoadingCandidates(true);
    setCandidates([]);
    setSelectedCandidate(null);
    try {
      const frames = await getCandidateFrames(videoKey);
      setCandidates(frames);
      if (frames[0]) setSelectedCandidate(frames[0].id);
    } catch {
      setErrorMessage('후보 장면 조회에 실패했습니다.');
      setUploadedInfo(null);
    } finally {
      setLoadingCandidates(false);
    }
  };

  /* Candidate confirmed → createJob → add to list */
  const handleConfirm = async () => {
    if (!uploadedInfo || !selectedCandidate) return;
    setConfirmingJob(true);
    try {
      const created = await createJob({
        videoKey: uploadedInfo.videoKey,
        refImageKeys: [uploadedInfo.imageKey],
        options: { placementPrompt: uploadedInfo.prompt },
      });
      const status = await getJobStatus(created.jobId);
      prependCreatedJob(status);
      setUploadedInfo(null);
      setCandidates([]);
      setSelectedCandidate(null);
    } catch (e: unknown) {
      setErrorMessage(e instanceof Error ? e.message : '작업 생성에 실패했습니다.');
    } finally {
      setConfirmingJob(false);
    }
  };

  const closeDrawer = () => {
    if (confirmingJob) return;
    setUploadedInfo(null);
    setCandidates([]);
    setSelectedCandidate(null);
  };

  const drawerOpen = uploadedInfo !== null;

  const filteredJobs = useMemo(() => {
    if (tab === 'running') return jobs.filter(j => j.status === 'RUNNING');
    if (tab === 'waiting') return jobs.filter(j => j.status === 'QUEUED');
    if (tab === 'done') return jobs.filter(j => j.status === 'COMPLETED' || j.status === 'FAILED');
    return jobs;
  }, [jobs, tab]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: '#f0f2f8' }}>

      {/* ── TOP NAV ── */}
      <nav style={{
        height: 56, background: '#fff', borderBottom: '1px solid #e5e7ef',
        display: 'flex', alignItems: 'center', padding: '0 24px', flexShrink: 0,
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}>
        <Link to="/" style={{ textDecoration: 'none' }}>
          <span style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 18, fontWeight: 900, color: '#111',
            paddingRight: 20, borderRight: '1px solid #eee', letterSpacing: '-0.5px',
          }}>
            RE:<span style={{ color: '#4a6cf7' }}>PPL</span>
          </span>
        </Link>
        <div style={{ paddingLeft: 20, fontSize: 14, color: '#aaa', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>홈</span>
          <span style={{ color: '#ddd' }}>›</span>
          <span style={{ color: '#111', fontWeight: 600 }}>작업</span>
        </div>
        <div style={{ marginLeft: 'auto' }}>
          <div style={{
            width: 34, height: 34, borderRadius: '50%',
            background: 'linear-gradient(135deg, #4a6cf7, #7a9cff)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: 13, fontWeight: 700,
          }}>U</div>
        </div>
      </nav>

      {/* ── APP BODY ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* LEFT PANEL — 새 작업 만들기 (fixed) */}
        <div style={{
          width: 400, flexShrink: 0, background: '#fff', borderRight: '1px solid #e5e7ef',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          <div style={{ padding: '20px 24px 14px', borderBottom: '1px solid #f0f0f5' }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: '#111', margin: 0 }}>새 작업 만들기</h2>
            <p style={{ fontSize: 12, color: '#999', marginTop: 4 }}>영상과 광고 이미지를 업로드하세요</p>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            <JobCreateForm
              onCreated={prependCreatedJob}
              onError={setErrorMessage}
              onUploaded={handleUploaded}
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

        {/* RIGHT PANEL — 나의 작업들 (scrollable) */}
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

          {/* Job list */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
            {loadingJobs && (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
                <div className="loading-spinner" />
              </div>
            )}
            {!loadingJobs && filteredJobs.length === 0 && (
              <div className="empty-state">
                <span className="empty-state-icon">📋</span>
                <p style={{ fontSize: 14, fontWeight: 600, color: '#64748b' }}>작업이 없습니다</p>
                <p style={{ fontSize: 12, color: '#94a3b8' }}>왼쪽에서 새 작업을 만들어보세요</p>
              </div>
            )}
            {filteredJobs.map(job => (
              <JobCard key={job.jobId} job={job} onDownload={downloadResult} />
            ))}
          </div>
        </div>
      </div>

      {/* ── CANDIDATE DRAWER (right slide-in) ── */}
      {drawerOpen && (
        <>
          {/* Overlay */}
          <div
            onClick={closeDrawer}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 100 }}
          />

          {/* Drawer panel */}
          <div style={{
            position: 'fixed', top: 0, right: 0, bottom: 0, width: 480,
            background: '#fff', zIndex: 101,
            display: 'flex', flexDirection: 'column',
            boxShadow: '-8px 0 40px rgba(0,0,0,0.15)',
            animation: 'slideInDrawer 0.25s ease',
          }}>
            {/* Drawer header */}
            <div style={{
              padding: '20px 24px', borderBottom: '1px solid #f0f0f5',
              display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexShrink: 0,
            }}>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: '#111', margin: 0 }}>삽입 위치 선택</h3>
                <p style={{ fontSize: 12, color: '#999', marginTop: 4 }}>AI가 추천하는 장면 중 하나를 선택하세요</p>
              </div>
              {!confirmingJob && (
                <button
                  onClick={closeDrawer}
                  style={{
                    background: '#f5f5f8', border: 'none', borderRadius: 8,
                    width: 32, height: 32, cursor: 'pointer', fontSize: 18, color: '#666',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                >×</button>
              )}
            </div>

            {/* Candidate list */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
              {loadingCandidates ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '64px 0' }}>
                  <div className="loading-spinner" />
                  <p style={{ fontSize: 13, color: '#999' }}>영상 분석 중…</p>
                </div>
              ) : (
                candidates.map(frame => (
                  <div
                    key={frame.id}
                    onClick={() => setSelectedCandidate(frame.id)}
                    style={{
                      border: `2px solid ${selectedCandidate === frame.id ? '#4a6cf7' : '#e8ebf5'}`,
                      borderRadius: 12, overflow: 'hidden', cursor: 'pointer',
                      boxShadow: selectedCandidate === frame.id ? '0 0 0 3px rgba(74,108,247,0.12)' : 'none',
                      transition: 'all 0.15s',
                    }}
                  >
                    {/* Thumbnail */}
                    <div style={{
                      width: '100%', height: 160,
                      background: frame.color,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      position: 'relative',
                    }}>
                      <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', letterSpacing: 1, textTransform: 'uppercase' }}>
                        scene {frame.id}
                      </span>
                      <span style={{
                        position: 'absolute', top: 10, right: 10,
                        padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700,
                        background: selectedCandidate === frame.id ? '#4a6cf7' : 'rgba(0,0,0,0.45)',
                        color: '#fff',
                      }}>
                        {selectedCandidate === frame.id ? '선택됨' : '추천'}
                      </span>
                    </div>
                    {/* Meta */}
                    <div style={{ padding: '12px 14px', background: '#fff' }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: '#111' }}>{frame.timestampLabel}</div>
                      <div style={{ fontSize: 12, color: '#aaa', marginTop: 2 }}>
                        {frame.description} · 신뢰도 {frame.confidence}%
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Confirm button */}
            <div style={{ padding: '16px 24px', borderTop: '1px solid #f0f0f5', flexShrink: 0 }}>
              <button
                onClick={handleConfirm}
                disabled={!selectedCandidate || confirmingJob || loadingCandidates}
                style={{
                  width: '100%', padding: 13,
                  background: (!selectedCandidate || confirmingJob || loadingCandidates) ? '#e2e8f0' : '#4a6cf7',
                  color: (!selectedCandidate || confirmingJob || loadingCandidates) ? '#94a3b8' : '#fff',
                  border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 700,
                  cursor: (!selectedCandidate || confirmingJob || loadingCandidates) ? 'not-allowed' : 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                {confirmingJob ? '작업 생성 중…' : '이 장면으로 합성 시작 →'}
              </button>
            </div>
          </div>
        </>
      )}

      {/* ── COMPLETION TOAST (bottom-right, kakao style) ── */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 28, right: 28, zIndex: 200,
          background: '#1e1e2e', color: '#fff', borderRadius: 16,
          padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 12,
          boxShadow: '0 8px 32px rgba(0,0,0,0.35), 0 0 0 1px rgba(74,108,247,0.2)',
          minWidth: 300, maxWidth: 340, overflow: 'hidden',
          animation: 'slideUpToast 0.3s ease',
        }}>
          {/* Progress bar (auto-dismiss indicator) */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, height: 3,
            background: '#4a6cf7', borderRadius: '0 3px 3px 0',
            animation: 'shrinkBar 5s linear forwards',
          }} />

          <div style={{
            width: 38, height: 38, borderRadius: 10, background: '#4a6cf7',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0, fontSize: 18,
          }}>🎉</div>

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
function JobCard({ job, onDownload }: { job: JobItem; onDownload: (id: string) => Promise<void> }) {
  const cfg = STATUS_CFG[job.status] ?? STATUS_CFG['QUEUED'];
  const progress = job.progress ?? (job.status === 'COMPLETED' ? 100 : 0);

  return (
    <div className="job-card" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      {/* Thumbnail */}
      <div style={{
        width: 80, height: 52, borderRadius: 8,
        background: 'linear-gradient(135deg, #1a1a2e, #0d0d1a)',
        flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
      }}>🎬</div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#111', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {job.jobId}
        </div>
        {job.message && (
          <div style={{ fontSize: 12, color: '#aaa', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {job.message}
          </div>
        )}
        {job.stage && (
          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{job.stage}</div>
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
        {job.status === 'COMPLETED' && (
          <button className="download-btn" onClick={() => onDownload(job.jobId)}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 5v14M5 12l7 7 7-7" />
            </svg>
            다운로드
          </button>
        )}
      </div>
    </div>
  );
}
