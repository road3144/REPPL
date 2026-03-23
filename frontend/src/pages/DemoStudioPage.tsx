import { NavBar } from '../components/NavBar';
import { JobCreateForm } from '../components/studio/JobCreateForm';
import { JobListPanel } from '../components/studio/JobListPanel';
import { PreviewSelectModal } from '../components/studio/PreviewSelectModal';
import { useScrollReveal } from '../hooks/useScrollReveal';
import { useDemoJobs } from '../hooks/useDemoJobs';

const pipelineSteps = [
  {
    icon: '📥',
    title: '입력 수집',
    description: '원본 동영상과 삽입할 물체 사진, 배치 위치 설명을 입력합니다.',
  },
  {
    icon: '🎯',
    title: '첫 프레임 삽입',
    description: 'NanoBanana 엔진이 프롬프트에 맞춰 첫 프레임에 물체를 정밀 배치합니다.',
  },
  {
    icon: '🎬',
    title: '전체 영상 합성',
    description: '첫 프레임을 기준으로 전체 영상에 자연스럽게 합성하고 그림자를 추가합니다.',
  },
];

export function DemoStudioPage() {
  const pageRef = useScrollReveal<HTMLDivElement>();
  const {
    jobs,
    running,
    loadingJobs,
    errorMessage,
    setErrorMessage,
    prependCreatedJob,
    downloadResult,
    previewSelecting,
    selectingIndex,
    loadPreviews,
    handleSelectPreview,
    closePreviewSelection,
  } = useDemoJobs();
  const completed = jobs.filter((job) => job.status === 'COMPLETED' && job.jobType === 'COMPOSITE').length;

  const handleDownload = async (jobId: string) => {
    try {
      await downloadResult(jobId);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : '결과 다운로드 URL 조회에 실패했습니다.');
    }
  };

  return (
    <div className="page-dark" ref={pageRef}>
      <NavBar />

      {/* ════════════ Hero ════════════ */}
      <section className="hero">
        <div className="hero-content animate-on-scroll">
          <span className="hero-tag">
            <span style={{ fontSize: '0.85rem' }}>✦</span>
            AI-Powered Virtual Product Placement
          </span>

          <h1 className="hero-title">
            촬영 끝난 영상에
            <br />
            <span className="gradient">제품을 자연스럽게 삽입</span>합니다
          </h1>

          <p className="hero-subtitle">
            원본 동영상과 제품 이미지만 업로드하세요.
            AI가 첫 프레임에 물체를 배치하고, 전체 영상으로 확장하며
            그림자까지 자연스럽게 합성합니다.
          </p>

          <div className="hero-actions">
            <a href="#workspace" className="btn-primary">
              작업 시작하기 →
            </a>
            <a href="#pipeline" className="btn-ghost">
              파이프라인 보기
            </a>
          </div>
        </div>
      </section>

      {/* ════════════ Pipeline ════════════ */}
      <section id="pipeline" className="pipeline-section">
        <div className="pipeline-grid">
          {pipelineSteps.map((step, index) => (
            <div
              key={step.title}
              className={`animate-on-scroll delay-${index + 1} pipeline-card`}
            >
              <div className="pipeline-icon" style={{ animation: `float 4s ease-in-out ${index * 0.3}s infinite` }}>
                {step.icon}
              </div>
              <div className="pipeline-num">{index + 1}</div>
              <h3>{step.title}</h3>
              <p>{step.description}</p>

              {index < pipelineSteps.length - 1 && (
                <div className="pipeline-arrow">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <path d="M5 12h14" />
                    <path d="m12 5 7 7-7 7" />
                  </svg>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <hr className="section-divider" />

      {/* ════════════ Stats ════════════ */}
      <div className="stats-strip" style={{ marginTop: '2.5rem' }}>
        {[
          { value: running, label: '진행 중', color: 'text-cyan-400' },
          { value: completed, label: '완료', color: 'text-emerald-400' },
          { value: jobs.length, label: '전체 작업', color: 'text-violet-400' },
          { value: jobs.length > 0 ? `${Math.round((completed / jobs.length) * 100)}%` : '0%', label: '성공률', color: 'text-amber-400' },
        ].map((s) => (
          <div key={s.label} className="animate-on-scroll stat-card">
            <p className={`stat-value ${s.color}`}>{s.value}</p>
            <p className="stat-label">{s.label}</p>
          </div>
        ))}
      </div>

      {/* ════════════ Workspace ════════════ */}
      <section id="workspace" className="workspace-section">
        <div className="workspace-header animate-on-scroll">
          <h2>워크스페이스</h2>
          <p>파일을 업로드하고, 배치 위치를 설명한 뒤 합성을 시작하세요.</p>
        </div>

        <div className="workspace-grid">
          <div className="space-y-5">
            <div className="animate-on-scroll delay-1">
              <JobCreateForm onCreated={prependCreatedJob} onError={setErrorMessage} />
              {errorMessage && (
                <p className="mt-3 text-sm" style={{ color: 'var(--rose)' }}>{errorMessage}</p>
              )}
            </div>

            {/* Prompt Guide */}
            <section className="animate-on-scroll delay-3 glass-card">
              <p className="text-xs font-bold uppercase tracking-[0.15em]" style={{ color: 'var(--accent)' }}>
                프롬프트 가이드
              </p>
              <h3 className="mt-2 text-lg font-extrabold" style={{ color: 'var(--text-primary)' }}>
                위치 설명은 장면 기준으로 구체적으로
              </h3>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="guide-chip">테이블 오른쪽 위 컵 옆</span>
                <span className="guide-chip">손 앞쪽 그림자가 자연스럽게</span>
                <span className="guide-chip">바닥 접지감 유지</span>
              </div>
              <p className="mt-3 text-sm leading-6" style={{ color: 'var(--text-muted)' }}>
                장면 기준 위치, 가려짐, 그림자 방향까지 함께 적으면 첫 프레임 프롬프트 품질을 높일 수 있습니다.
              </p>
            </section>
          </div>

          <div className="animate-on-scroll delay-2">
            <JobListPanel
              jobs={jobs}
              loadingJobs={loadingJobs}
              onDownload={handleDownload}
              onViewPreviews={loadPreviews}
            />
          </div>
        </div>
      </section>

      {/* ════════════ Preview Selection Modal ════════════ */}
      {previewSelecting && (
        <PreviewSelectModal
          jobId={previewSelecting.jobId}
          previews={previewSelecting.previews}
          selecting={selectingIndex}
          onSelect={(index: number) => handleSelectPreview(previewSelecting.jobId, index)}
          onClose={closePreviewSelection}
        />
      )}
    </div>
  );
}
