import { formatStage } from '../../constants/stage';
import type { JobItem } from '../../services/types';

type JobStagePanelProps = {
  job: JobItem | null;
  onOpenPreview: (jobId: string) => void;
  onDownload: (jobId: string) => void;
};

type StageTone = 'done' | 'current' | 'pending' | 'failed';

const PREVIEW_STAGE_FLOW = [
  { key: 'GEMINI', label: '첫 프레임 Gemini 합성' },
];

const COMPOSITE_STAGE_FLOW = [
  { key: 'DOWNLOAD', label: '입력 파일 다운로드' },
  { key: 'DINO', label: 'Grounding DINO 객체 검출' },
  { key: 'SAM', label: 'SAM 마스크 추출' },
  { key: 'SHADOW', label: '그림자 생성' },
  { key: 'SCALE', label: '객체 크기 조정' },
  { key: 'DEPTH', label: '깊이 추정' },
  { key: 'COMPOSITE', label: '전체 프레임 합성' },
  { key: 'UPLOAD', label: '최종 합성 업로드' },
];

function getStageFlow(job: JobItem) {
  if (job.jobType === 'PREVIEW') return PREVIEW_STAGE_FLOW;
  return COMPOSITE_STAGE_FLOW;
}

function getStageTone(job: JobItem, stageKey: string, stageIndex: number, activeIndex: number): StageTone {
  if (job.status === 'COMPLETED') return 'done';

  if (job.status === 'FAILED') {
    if (activeIndex === -1) return 'pending';
    if (stageIndex < activeIndex) return 'done';
    if (stageIndex === activeIndex) return 'failed';
    return 'pending';
  }

  if (job.status === 'RUNNING') {
    if (activeIndex === -1) return stageIndex === 0 ? 'current' : 'pending';
    if (stageIndex < activeIndex) return 'done';
    if (stageIndex === activeIndex) return 'current';
    return 'pending';
  }

  if (job.status === 'QUEUED') {
    return 'pending';
  }

  if (job.stage === stageKey) {
    return 'current';
  }

  return 'pending';
}

function formatCreatedAt(createdAt: string | null) {
  if (!createdAt) return '방금 생성됨';
  return new Date(createdAt).toLocaleString('ko-KR');
}

function StatusIcon({ tone }: { tone: StageTone }) {
  if (tone === 'done') {
    return (
      <span className="job-stage-icon job-stage-icon-done" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="m5 12 4 4L19 6" />
        </svg>
      </span>
    );
  }

  if (tone === 'current') {
    return <span className="job-stage-icon job-stage-icon-current" aria-hidden="true" />;
  }

  if (tone === 'failed') {
    return (
      <span className="job-stage-icon job-stage-icon-failed" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
          <path d="M18 6 6 18" />
          <path d="m6 6 12 12" />
        </svg>
      </span>
    );
  }

  return <span className="job-stage-icon job-stage-icon-pending" aria-hidden="true" />;
}

function getStatusLabel(job: JobItem) {
  if (job.status === 'QUEUED') return '대기 중';
  if (job.status === 'RUNNING') return `처리 중${job.progress != null ? ` (${job.progress}%)` : ''}`;
  if (job.status === 'COMPLETED') return '완료';
  if (job.status === 'FAILED') return '실패';
  return job.status;
}

export function JobStagePanel({ job, onOpenPreview, onDownload }: JobStagePanelProps) {
  if (!job) {
    return (
      <aside className="job-stage-panel">
        <div className="job-stage-panel-inner">
          <h3 className="job-stage-panel-title">작업 상세</h3>
          <div className="job-stage-empty">
            <p>작업 카드를 선택하면 현재 단계와 상태를 여기서 확인할 수 있습니다.</p>
          </div>
        </div>
      </aside>
    );
  }

  const stages = getStageFlow(job);
  const activeIndex = job.stage ? stages.findIndex((stage) => stage.key === job.stage) : -1;
  const stageHeadline = formatStage(job.stage) ?? (job.status === 'QUEUED' ? '작업 대기 중' : '단계 정보 없음');
  const progress = job.progress ?? (job.status === 'COMPLETED' ? 100 : 0);
  const isPreviewCompleted = job.jobType === 'PREVIEW' && job.status === 'COMPLETED';
  const isCompositeCompleted = job.jobType === 'COMPOSITE' && job.status === 'COMPLETED';

  return (
    <aside className="job-stage-panel">
      <div className="job-stage-panel-inner">
        <div className="job-stage-head">
          <div>
            <h3 className="job-stage-panel-title">{job.jobId}</h3>
            <p className="job-stage-panel-subtitle">
              {job.jobType === 'PREVIEW' ? '프리뷰 생성 작업' : '최종 합성 작업'}
            </p>
          </div>
        </div>

        <div className="job-stage-progress-block">
          <div className="job-stage-progress-track">
            <div className="job-stage-progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>

        <section className="job-stage-section">
          <h4 className="job-stage-section-title">처리 단계</h4>
          <div className="job-stage-list">
            {stages.map((stage, index) => {
              const tone = getStageTone(job, stage.key, index, activeIndex);
              const isCurrent = tone === 'current';

              return (
                <div key={stage.key} className={`job-stage-item job-stage-item-${tone}`}>
                  <StatusIcon tone={tone} />
                  <div className="job-stage-copy">
                    <span className="job-stage-name">
                      {stage.label}
                      {isCurrent && job.progress != null ? ` (${job.progress}%)` : ''}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="job-stage-section">
          <div className="job-stage-meta-row">
            <span>현재 단계</span>
            <strong>{stageHeadline}</strong>
          </div>
          <div className="job-stage-meta-row">
            <span>상태</span>
            <strong className={job.status === 'RUNNING' ? 'job-stage-meta-running' : ''}>{getStatusLabel(job)}</strong>
          </div>
          <div className="job-stage-meta-row">
            <span>생성 시각</span>
            <strong>{formatCreatedAt(job.createdAt)}</strong>
          </div>
          <div className="job-stage-meta-row">
            <span>메시지</span>
            <strong>{job.message ?? '상세 메시지 없음'}</strong>
          </div>
        </section>

        {isPreviewCompleted && (
          <button type="button" className="job-stage-action-btn" onClick={() => onOpenPreview(job.jobId)}>
            프리뷰 선택하기
          </button>
        )}

        {isCompositeCompleted && (
          <button type="button" className="job-stage-action-btn job-stage-action-btn-download" onClick={() => onDownload(job.jobId)}>
            결과 다운로드
          </button>
        )}
      </div>
    </aside>
  );
}
