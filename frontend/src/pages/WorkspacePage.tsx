import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { JobCreateForm } from '../components/studio/JobCreateForm';
import { PreviewSelectModal } from '../components/studio/PreviewSelectModal';
import { JobStagePanel } from '../components/studio/JobStagePanel';
import { useJobs } from '../hooks/useJobs';
import { formatStage } from '../constants/stage';
import {
  DEFAULT_WORKSPACE_SETTINGS,
  useWorkspaceSettings,
  type WorkspaceSettings,
} from '../services/workspaceSettings';
import type { JobItem, JobStatusResponse } from '../services/types';

/* ── Status config ── */
const STATUS_CFG: Record<
  string,
  { label: string; badgeCls: string; progressCls: string }
> = {
  QUEUED: { label: '대기 중', badgeCls: 'job-status-slate', progressCls: 'job-progress-slate' },
  RUNNING: { label: '처리 중', badgeCls: 'job-status-amber', progressCls: 'job-progress-amber' },
  COMPLETED: { label: '완료', badgeCls: 'job-status-emerald', progressCls: 'job-progress-emerald' },
  FAILED: { label: '실패', badgeCls: 'job-status-rose', progressCls: 'job-progress-rose' },
};

type Tab = 'all' | 'running' | 'waiting' | 'done';
type WorkspaceSection = 'studio' | 'results' | 'history';

const WORKSPACE_SECTIONS: Array<{ id: WorkspaceSection; label: string }> = [
  { id: 'studio', label: '작업 스튜디오' },
  { id: 'results', label: '내 결과물' },
  { id: 'history', label: '작업내역' },
];

const STATUS_TAB_ITEMS: Array<{ id: Tab; label: string }> = [
  { id: 'all', label: '전체' },
  { id: 'running', label: '처리 중' },
  { id: 'waiting', label: '대기 중' },
  { id: 'done', label: '완료' },
];

const GUIDE_QUICK_STEPS = [
  {
    title: '원본 영상 업로드',
    description: '프레임이 흔들리지 않고 제품이 놓일 공간이 충분한 영상을 선택하세요.',
  },
  {
    title: '제품 이미지 등록',
    description: '배경이 깔끔한 PNG/JPG를 최대 5장까지 업로드해 다양한 후보를 만드세요.',
  },
  {
    title: '배치 프롬프트 작성',
    description: '위치·크기·각도를 구체적으로 작성하면 검증 실패와 재작업을 줄일 수 있습니다.',
  },
  {
    title: '프리뷰 선택 후 합성',
    description: '프리뷰 4개 중 가장 자연스러운 결과를 선택한 뒤 최종 합성을 실행하세요.',
  },
] as const;

const GUIDE_PROMPT_DO = [
  '“테이블 오른쪽 컵 옆에 제품을 30도 각도로 배치”처럼 위치 기준점을 명확히 작성',
  '“원근감 유지, 그림자 자연스럽게”처럼 품질 요구사항을 한 줄로 덧붙이기',
  '제품이 가려지면 안 되는 오브젝트가 있다면 반드시 함께 지정하기',
] as const;

const GUIDE_PROMPT_DONT = [
  '“아무데나 자연스럽게”처럼 모호한 지시어만 단독으로 사용',
  '한 문장에 서로 충돌하는 지시를 동시에 작성',
  '“정중앙” 지시 후 가장자리 오브젝트와 충돌 가능한 장면을 그대로 사용',
] as const;

const GUIDE_STATUS_ITEMS = [
  {
    status: '대기 중',
    detail: '요청이 접수되어 순서를 기다리는 상태입니다.',
  },
  {
    status: '처리 중',
    detail: '추적/마스킹/합성 단계가 순차적으로 실행 중입니다.',
  },
  {
    status: '완료',
    detail: '결과 영상 다운로드 또는 재생이 가능합니다.',
  },
  {
    status: '실패',
    detail: '프롬프트 검증 실패나 입력 파일 품질 문제일 수 있습니다. 가이드 예시를 참고해 수정하세요.',
  },
] as const;

const GUIDE_FAQ_ITEMS = [
  {
    question: '작업이 오래 걸릴 때 먼저 확인할 것은 무엇인가요?',
    answer:
      '작업 내역에서 상태가 “대기 중”인지 “처리 중”인지 확인하세요. 대기 중이면 순차 처리 대기이며, 처리 중에서 오래 멈춘 경우 원본 영상 용량과 해상도를 먼저 점검하세요.',
  },
  {
    question: '프롬프트 검증 실패를 줄이려면 어떻게 작성해야 하나요?',
    answer:
      '공간 기준점(예: 책상 오른쪽 모서리), 배치 방식(예: 세워서/눕혀서), 품질 조건(예: 그림자 유지)을 함께 적으면 실패율이 크게 줄어듭니다.',
  },
  {
    question: '결과물이 어색할 때는 어떤 순서로 재시도하면 좋나요?',
    answer:
      '1) 제품 이미지 배경 정리 2) 프롬프트 위치 표현 구체화 3) 프리뷰 후보 중 다른 컷 선택 순서로 재시도하는 것을 권장합니다.',
  },
] as const;

const GUIDE_REFERENCE_IMAGES = [
  {
    title: '파이프라인 흐름',
    description: '요청부터 최종 출력까지 단계 구조',
    src: '/images/process_flow.png',
  },
  {
    title: '전/후 비교 예시',
    description: '합성 결과 품질 체크 기준',
    src: '/images/before_after_demo.png',
  },
  {
    title: '결과물 활용 예시',
    description: '숏폼 배포 화면 예시',
    src: '/images/shorts_mockup.png',
  },
] as const;

function filterJobsByTab(jobs: JobItem[], tab: Tab): JobItem[] {
  if (tab === 'running') return jobs.filter((job) => job.status === 'RUNNING');
  if (tab === 'waiting') return jobs.filter((job) => job.status === 'QUEUED');
  if (tab === 'done') return jobs.filter((job) => job.status === 'COMPLETED' || job.status === 'FAILED');
  return jobs;
}

function FileStackIcon({ className = 'w-7 h-7' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M8 3h8l4 4v11a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" />
      <path d="M16 3v5h5" />
      <path d="M10 12h4" />
      <path d="M10 16h4" />
    </svg>
  );
}

function VideoPanelIcon({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect x="3" y="6" width="13" height="12" rx="2" />
      <path d="m16 10 5-3v10l-5-3z" />
    </svg>
  );
}

function SidebarStudioIcon({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3" y="5" width="18" height="12" rx="2" />
      <path d="M8 21h8" />
      <path d="M12 17v4" />
    </svg>
  );
}

function SidebarFileIcon({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M8 3h8l4 4v13a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" />
      <path d="M16 3v5h5" />
    </svg>
  );
}

function SidebarClockIcon({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v6l3 2" />
    </svg>
  );
}

function SidebarGearIcon({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="3" />
      <path d="m19.4 15 .6 1-1.6 2.8-1.2-.4a7.3 7.3 0 0 1-1.7 1l-.2 1.3H11l-.2-1.3c-.6-.2-1.2-.5-1.7-1l-1.2.4L6.3 16l.6-1a7.8 7.8 0 0 1 0-2l-.6-1 1.6-2.8 1.2.4c.5-.4 1.1-.7 1.7-1L11 7.3h3.2l.2 1.3c.6.2 1.2.5 1.7 1l1.2-.4L20 12l-.6 1c.1.7.1 1.3 0 2z" />
    </svg>
  );
}

function SidebarHelpIcon({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9a2.5 2.5 0 0 1 4.6 1.2c0 1.8-2.1 2.1-2.1 3.6" />
      <circle cx="12" cy="17" r="0.8" fill="currentColor" stroke="none" />
    </svg>
  );
}

function TopbarBellIcon({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M15 18H5a1 1 0 0 1-.9-1.4l1.1-2.1V11a6 6 0 1 1 12 0v3.5l1.1 2.1A1 1 0 0 1 17.4 18H15" />
      <path d="M10 18a2 2 0 0 0 4 0" />
    </svg>
  );
}

function WorkspaceTopBar({ activeSection, onCreateJob }: {
  activeSection: WorkspaceSection;
  onCreateJob: () => void;
}) {
  const activeLabel = WORKSPACE_SECTIONS.find((item) => item.id === activeSection)?.label ?? '작업 스튜디오';

  return (
    <header className="workspace-topbar">
      <div className="workspace-topbar-left">
        <Link to="/" className="workspace-topbar-logo">
          Re:<span>PPL</span>
        </Link>
        <span className="workspace-topbar-separator" />
        <div className="workspace-topbar-breadcrumb">
          <span>{activeLabel}</span>
          <span>/</span>
          {activeSection === 'studio' ? (
            <button type="button" className="workspace-topbar-breadcrumb-action" onClick={onCreateJob}>
              새 작업 만들기
            </button>
          ) : (
            <strong>{activeLabel}</strong>
          )}
        </div>
      </div>

      <div className="workspace-topbar-actions">
        <button type="button" className="workspace-icon-btn" aria-label="알림">
          <TopbarBellIcon />
        </button>
      </div>
    </header>
  );
}

function WorkspaceSidebar({ activeSection, onSelect, onCreateJob, onOpenHelp, onOpenSettings, counts }: {
  activeSection: WorkspaceSection;
  onSelect: (next: WorkspaceSection) => void;
  onCreateJob: () => void;
  onOpenHelp: () => void;
  onOpenSettings: () => void;
  counts: Record<WorkspaceSection, number>;
}) {
  return (
    <aside className="workspace-sidebar">
      <div className="workspace-sidebar-block">
        <p className="workspace-sidebar-title">메뉴</p>
        <button type="button" className="workspace-create-btn workspace-sidebar-create" onClick={onCreateJob}>
          + 새 작업
        </button>
        <button
          type="button"
          className={`workspace-sidebar-item ${activeSection === 'studio' ? 'active' : ''}`}
          onClick={() => onSelect('studio')}
        >
          <SidebarStudioIcon />
          <span>작업 스튜디오</span>
          <span className="workspace-sidebar-count">{counts.studio}</span>
        </button>
        <button
          type="button"
          className={`workspace-sidebar-item ${activeSection === 'results' ? 'active' : ''}`}
          onClick={() => onSelect('results')}
        >
          <SidebarFileIcon />
          <span>내 결과물</span>
          <span className="workspace-sidebar-count">{counts.results}</span>
        </button>
        <button
          type="button"
          className={`workspace-sidebar-item ${activeSection === 'history' ? 'active' : ''}`}
          onClick={() => onSelect('history')}
        >
          <SidebarClockIcon />
          <span>작업 내역</span>
          <span className="workspace-sidebar-count">{counts.history}</span>
        </button>
      </div>

      <div className="workspace-sidebar-block">
        <p className="workspace-sidebar-title">설정</p>
        <button type="button" className="workspace-sidebar-subitem" onClick={onOpenSettings}>
          <SidebarGearIcon />
          <span>설정</span>
        </button>
        <button type="button" className="workspace-sidebar-subitem" onClick={onOpenHelp}>
          <SidebarHelpIcon />
          <span>도움말</span>
        </button>
      </div>
    </aside>
  );
}

function WorkspaceGuideModal({ onClose }: { onClose: () => void }) {
  return (
    <>
      <div className="workspace-guide-modal-backdrop" onClick={onClose} />
      <section
        className="workspace-guide-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="workspace-guide-title"
      >
        <div className="workspace-guide-modal-header">
          <div>
            <h2 id="workspace-guide-title">서비스 가이드라인</h2>
            <p>초기 온보딩부터 작업 품질 개선까지, 팀 공통 기준으로 바로 사용할 수 있습니다.</p>
          </div>
          <button type="button" className="workspace-guide-close-btn" onClick={onClose} aria-label="가이드 닫기">
            ×
          </button>
        </div>

        <div className="workspace-guide-modal-body">
          <section className="workspace-guide-hero">
            <strong>권장 운영 원칙</strong>
            <p>프롬프트를 먼저 구체화하고 프리뷰를 확인한 뒤 합성하면 재작업 시간을 크게 줄일 수 있습니다.</p>
            <div className="workspace-guide-badge-row">
              <span className="workspace-guide-badge">정확한 위치 지시</span>
              <span className="workspace-guide-badge">프리뷰 기반 선택</span>
              <span className="workspace-guide-badge">완료 토스트 실시간 확인</span>
            </div>
          </section>

          <section className="workspace-guide-section">
            <h3>빠른 시작</h3>
            <div className="workspace-guide-step-grid">
              {GUIDE_QUICK_STEPS.map((step, index) => (
                <article key={step.title} className="workspace-guide-step-card">
                  <span className="workspace-guide-step-index">STEP {index + 1}</span>
                  <h4>{step.title}</h4>
                  <p>{step.description}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="workspace-guide-section">
            <h3>프롬프트 작성 기준</h3>
            <div className="workspace-guide-rule-grid">
              <article className="workspace-guide-rule-card good">
                <h4>이렇게 작성하세요</h4>
                <ul>
                  {GUIDE_PROMPT_DO.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
              <article className="workspace-guide-rule-card bad">
                <h4>이 표현은 피하세요</h4>
                <ul>
                  {GUIDE_PROMPT_DONT.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            </div>
          </section>

          <section className="workspace-guide-section">
            <h3>작업 상태 이해</h3>
            <div className="workspace-guide-status-grid">
              {GUIDE_STATUS_ITEMS.map((item) => (
                <article key={item.status} className="workspace-guide-status-card">
                  <strong>{item.status}</strong>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="workspace-guide-section">
            <h3>자주 묻는 질문</h3>
            <div className="workspace-guide-faq-list">
              {GUIDE_FAQ_ITEMS.map((item) => (
                <details key={item.question} className="workspace-guide-faq-item">
                  <summary>{item.question}</summary>
                  <p>{item.answer}</p>
                </details>
              ))}
            </div>
          </section>

          {/* <section className="workspace-guide-section">
            <h3>시각 참고 자료</h3>
            <div className="workspace-guide-image-grid">
              {GUIDE_REFERENCE_IMAGES.map((item) => (
                <figure key={item.src} className="workspace-guide-image-card">
                  <img src={item.src} alt={item.title} loading="lazy" />
                  <figcaption>
                    <strong>{item.title}</strong>
                    <span>{item.description}</span>
                  </figcaption>
                </figure>
              ))}
            </div>
          </section> */}
        </div>
      </section>
    </>
  );
}

function WorkspaceSettingSwitch({
  label,
  description,
  enabled,
  disabled = false,
  onToggle,
}: {
  label: string;
  description: string;
  enabled: boolean;
  disabled?: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="workspace-settings-switch-row">
      <div className="workspace-settings-switch-copy">
        <strong>{label}</strong>
        <p>{description}</p>
      </div>
      <button
        type="button"
        className={`workspace-settings-switch ${enabled ? 'on' : ''}`}
        aria-pressed={enabled}
        disabled={disabled}
        onClick={onToggle}
      >
        <span />
      </button>
    </div>
  );
}

function WorkspaceSettingsModal({
  settings,
  onPatchSettings,
  onResetSettings,
  onClose,
}: {
  settings: WorkspaceSettings;
  onPatchSettings: (updater: (current: WorkspaceSettings) => WorkspaceSettings) => void;
  onResetSettings: () => void;
  onClose: () => void;
}) {
  const [browserPermission, setBrowserPermission] = useState<NotificationPermission | 'unsupported'>(() => {
    if (typeof Notification === 'undefined') {
      return 'unsupported';
    }
    return Notification.permission;
  });

  useEffect(() => {
    const syncPermission = () => {
      if (typeof Notification === 'undefined') {
        setBrowserPermission('unsupported');
        return;
      }
      setBrowserPermission(Notification.permission);
    };

    syncPermission();
    window.addEventListener('focus', syncPermission);
    return () => window.removeEventListener('focus', syncPermission);
  }, []);

  useEffect(() => {
    if (browserPermission === 'granted') {
      return;
    }

    if (!settings.notifications.browserEnabled) {
      return;
    }

    onPatchSettings((current) => ({
      ...current,
      notifications: {
        ...current.notifications,
        browserEnabled: false,
      },
    }));
  }, [browserPermission, onPatchSettings, settings.notifications.browserEnabled]);

  const browserPermissionLabel =
    browserPermission === 'unsupported'
      ? '이 브라우저는 웹 알림을 지원하지 않습니다.'
      : browserPermission === 'granted'
        ? '브라우저 알림 권한이 허용되어 있습니다.'
        : browserPermission === 'denied'
          ? '브라우저 알림 권한이 차단되어 있습니다.'
          : '브라우저 알림 권한 요청이 필요합니다.';

  const requestBrowserPermission = async () => {
    if (typeof Notification === 'undefined') {
      setBrowserPermission('unsupported');
      return;
    }

    try {
      const permission = await Notification.requestPermission();
      setBrowserPermission(permission);
      if (permission !== 'granted') {
        onPatchSettings((current) => ({
          ...current,
          notifications: {
            ...current.notifications,
            browserEnabled: false,
          },
        }));
      }
    } catch {
      setBrowserPermission(Notification.permission);
    }
  };

  const toggleBrowserNotification = async () => {
    if (settings.notifications.browserEnabled) {
      onPatchSettings((current) => ({
        ...current,
        notifications: {
          ...current.notifications,
          browserEnabled: false,
        },
      }));
      return;
    }

    if (browserPermission === 'unsupported') {
      return;
    }

    if (browserPermission !== 'granted') {
      await requestBrowserPermission();
    }

    if (
      typeof Notification !== 'undefined' &&
      Notification.permission === 'granted'
    ) {
      onPatchSettings((current) => ({
        ...current,
        notifications: {
          ...current.notifications,
          browserEnabled: true,
        },
      }));
    }
  };

  return (
    <>
      <div className="workspace-settings-modal-backdrop" onClick={onClose} />
      <section
        className="workspace-settings-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="workspace-settings-title"
      >
        <div className="workspace-settings-modal-header">
          <div>
            <h2 id="workspace-settings-title">설정</h2>
            <p>변경 사항은 현재 브라우저에 즉시 저장됩니다.</p>
          </div>
          <button type="button" className="workspace-settings-close-btn" onClick={onClose} aria-label="설정 닫기">
            ×
          </button>
        </div>

        <div className="workspace-settings-modal-body">
          <section className="workspace-settings-section">
            <h3>알림</h3>
            <WorkspaceSettingSwitch
              label="작업 완료 토스트"
              description="완료 시 우측 하단 토스트를 표시합니다."
              enabled={settings.notifications.toastEnabled}
              onToggle={() => {
                onPatchSettings((current) => ({
                  ...current,
                  notifications: {
                    ...current.notifications,
                    toastEnabled: !current.notifications.toastEnabled,
                  },
                }));
              }}
            />
            <WorkspaceSettingSwitch
              label="완료 사운드"
              description="작업 완료 시 짧은 알림음을 재생합니다."
              enabled={settings.notifications.soundEnabled}
              onToggle={() => {
                onPatchSettings((current) => ({
                  ...current,
                  notifications: {
                    ...current.notifications,
                    soundEnabled: !current.notifications.soundEnabled,
                  },
                }));
              }}
            />
            <WorkspaceSettingSwitch
              label="브라우저 알림"
              description="다른 탭/화면에 있어도 브라우저 알림을 수신합니다."
              enabled={settings.notifications.browserEnabled}
              disabled={browserPermission === 'unsupported'}
              onToggle={() => {
                void toggleBrowserNotification();
              }}
            />
            <div className="workspace-settings-help-row">
              <span>{browserPermissionLabel}</span>
              <button
                type="button"
                className="workspace-settings-secondary-btn"
                onClick={() => {
                  void requestBrowserPermission();
                }}
                disabled={browserPermission === 'unsupported' || browserPermission === 'granted'}
              >
                권한 요청
              </button>
            </div>
          </section>

          <section className="workspace-settings-section">
            <h3>다운로드</h3>
            <div className="workspace-settings-radio-group">
              <label className="workspace-settings-radio">
                <input
                  type="radio"
                  name="download-filename-pattern"
                  checked={settings.download.filenamePattern === 'job-id'}
                  onChange={() => {
                    onPatchSettings((current) => ({
                      ...current,
                      download: {
                        ...current.download,
                        filenamePattern: 'job-id',
                      },
                    }));
                  }}
                />
                <span>기본: 작업ID.mp4</span>
              </label>
              <label className="workspace-settings-radio">
                <input
                  type="radio"
                  name="download-filename-pattern"
                  checked={settings.download.filenamePattern === 'job-id-timestamp'}
                  onChange={() => {
                    onPatchSettings((current) => ({
                      ...current,
                      download: {
                        ...current.download,
                        filenamePattern: 'job-id-timestamp',
                      },
                    }));
                  }}
                />
                <span>작업ID_시간.mp4</span>
              </label>
            </div>
          </section>

          <section className="workspace-settings-section">
            <h3>작업 기본값</h3>
            <p className="workspace-settings-field-label">새 작업 모달 기본 프롬프트</p>
            <textarea
              className="workspace-settings-textarea"
              value={settings.defaults.placementPrompt}
              onChange={(event) => {
                onPatchSettings((current) => ({
                  ...current,
                  defaults: {
                    ...current.defaults,
                    placementPrompt: event.target.value,
                  },
                }));
              }}
              rows={4}
              placeholder="예: 테이블 오른쪽 위 컵 옆에 배치하고, 바닥 그림자가 자연스럽게 이어지도록"
            />
          </section>
        </div>

        <div className="workspace-settings-modal-footer">
          <button type="button" className="workspace-settings-secondary-btn" onClick={onResetSettings}>
            기본값으로 초기화
          </button>
          <button type="button" className="workspace-settings-primary-btn" onClick={onClose}>
            닫기
          </button>
        </div>
      </section>
    </>
  );
}

function WorkspaceStatusTabs({ tab, onChange }: { tab: Tab; onChange: (next: Tab) => void }) {
  return (
    <div style={{ display: 'flex', gap: 8 }}>
      {STATUS_TAB_ITEMS.map(({ id, label }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          style={{
            padding: '4px 12px',
            borderRadius: 20,
            fontSize: 11,
            fontWeight: 600,
            background: tab === id ? '#4a6cf7' : '#f0f2f8',
            color: tab === id ? '#fff' : '#888',
            border: 'none',
            cursor: 'pointer',
            transition: 'all 0.15s',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function WorkspaceStudioView({
  filteredJobs,
  jobs,
  loadingJobs,
  selectedJobId,
  tab,
  onTabChange,
  onSelectJob,
  onPlay,
  onDownload,
  onLoadPreviews,
}: {
  filteredJobs: JobItem[];
  jobs: JobItem[];
  loadingJobs: boolean;
  selectedJobId: string | null;
  tab: Tab;
  onTabChange: (tab: Tab) => void;
  onSelectJob: (id: string) => void;
  onPlay: (id: string) => Promise<void>;
  onDownload: (id: string) => Promise<void>;
  onLoadPreviews: (id: string) => void;
}) {
  const selectedJob = jobs.find((job) => job.jobId === selectedJobId) ?? null;

  return (
    <div className="workspace-studio-layout">
      <div className="workspace-studio-main">
        <div
          style={{
            padding: '16px 24px',
            background: '#fff',
            borderBottom: '1px solid #e5e7ef',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <div>
            <span style={{ fontSize: 14, fontWeight: 700, color: '#111' }}>나의 작업들</span>
            <span style={{ fontSize: 12, color: '#aaa', marginLeft: 8 }}>· {jobs.length}개</span>
          </div>
          <WorkspaceStatusTabs tab={tab} onChange={onTabChange} />
        </div>

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
                <p style={{ fontSize: 13, fontWeight: 600, color: '#64748b' }}>작업이 없습니다</p>
                <p style={{ fontSize: 12, color: '#94a3b8' }}>왼쪽에서 새 작업을 만들어보세요</p>
              </div>
            )}
            {filteredJobs.map((job) => (
              <JobCard
                key={job.jobId}
                job={job}
                selected={job.jobId === selectedJobId}
                onSelect={() => onSelectJob(job.jobId)}
                onDownload={onDownload}
                onPlay={onPlay}
                onSelectPreview={onLoadPreviews}
              />
            ))}
          </div>
          <JobStagePanel
            job={selectedJob}
            onOpenPreview={onLoadPreviews}
            onDownload={(jobId) => {
              void onDownload(jobId);
            }}
          />
        </div>
      </div>
    </div>
  );
}

function WorkspaceResultsView({
  jobs,
  loadingJobs,
  onDownload,
}: {
  jobs: JobItem[];
  loadingJobs: boolean;
  onDownload: (jobId: string) => Promise<void>;
}) {
  const completedCompositeJobs = useMemo(
    () => jobs.filter((job) => job.jobType === 'COMPOSITE' && job.status === 'COMPLETED'),
    [jobs]
  );

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#f0f2f8' }}>
      <div
        style={{
          padding: '16px 24px',
          background: '#fff',
          borderBottom: '1px solid #e5e7ef',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#111' }}>내 결과물</span>
          <span style={{ fontSize: 12, color: '#aaa', marginLeft: 8 }}>· {completedCompositeJobs.length}개</span>
        </div>
      </div>

      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          padding: '20px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        {loadingJobs && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
            <div className="loading-spinner" />
          </div>
        )}
        {!loadingJobs && completedCompositeJobs.length === 0 && (
          <div className="empty-state">
            <span className="empty-state-icon" aria-hidden="true">
              <FileStackIcon />
            </span>
            <p style={{ fontSize: 13, fontWeight: 600, color: '#64748b' }}>완료된 결과물이 없습니다</p>
            <p style={{ fontSize: 12, color: '#94a3b8' }}>합성 작업이 완료되면 이곳에 표시됩니다</p>
          </div>
        )}
        {completedCompositeJobs.map((job) => (
          <JobCard
            key={job.jobId}
            job={job}
            selected={false}
            onSelect={() => { }}
            onDownload={onDownload}
            onSelectPreview={() => { }}
          />
        ))}
      </div>
    </div>
  );
}

function WorkspaceHistoryView({
  filteredJobs,
  tab,
  onTabChange,
  onDownload,
  onSelectPreview,
  totalCount,
}: {
  filteredJobs: JobItem[];
  tab: Tab;
  onTabChange: (tab: Tab) => void;
  onDownload: (jobId: string) => Promise<void>;
  onSelectPreview: (id: string) => void;
  totalCount: number;
}) {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#f0f2f8' }}>
      <div
        style={{
          padding: '16px 24px',
          background: '#fff',
          borderBottom: '1px solid #e5e7ef',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#111' }}>작업내역</span>
          <span style={{ fontSize: 12, color: '#aaa', marginLeft: 8 }}>· {totalCount}개</span>
        </div>
        <WorkspaceStatusTabs tab={tab} onChange={onTabChange} />
      </div>

      <div className="workspace-job-list" style={{ padding: '20px 24px' }}>
        {filteredJobs.length === 0 && (
          <div className="empty-state">
            <span className="empty-state-icon" aria-hidden="true">
              <FileStackIcon />
            </span>
            <p style={{ fontSize: 13, fontWeight: 600, color: '#64748b' }}>기록이 없습니다</p>
            <p style={{ fontSize: 12, color: '#94a3b8' }}>왼쪽에서 작업을 등록하면 이곳에 누적됩니다</p>
          </div>
        )}
        {filteredJobs.map((job) => (
          <JobCard
            key={job.jobId}
            job={job}
            selected={false}
            onSelect={() => { }}
            onDownload={onDownload}
            onSelectPreview={onSelectPreview}
          />
        ))}
      </div>
    </div>
  );
}

export function WorkspacePage() {
  const { settings, patchSettings } = useWorkspaceSettings();
  const {
    jobs,
    loadingJobs,
    errorMessage,
    setErrorMessage,
    prependCreatedJob,
    downloadResult,
    getPlaybackUrl,
    previewSelecting,
    selectingIndex,
    loadPreviews,
    handleSelectPreview,
    closePreviewSelection,
  } = useJobs();

  const [activeSection, setActiveSection] = useState<WorkspaceSection>('studio');
  const [tab, setTab] = useState<Tab>('all');
  const [historyTab, setHistoryTab] = useState<Tab>('all');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [guideModalOpen, setGuideModalOpen] = useState(false);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [promptError, setPromptError] = useState<string | null>(null);
  const prevJobsRef = useRef<JobItem[]>([]);

  const openPlayer = async (jobId: string) => {
    try {
      const url = await getPlaybackUrl(jobId);
      setPlaybackUrl(url);
    } catch {
      setErrorMessage('영상 재생 URL을 가져올 수 없습니다.');
    }
  };

  /* Detect status transitions */
  useEffect(() => {
    for (const job of jobs) {
      const prev = prevJobsRef.current.find((p) => p.jobId === job.jobId);
      if (!prev) continue;

      if (job.status === 'FAILED' && job.stage === 'VALIDATE' && prev.status !== 'FAILED') {
        setPromptError(job.message ?? '제품 배치와 관련된 프롬프트를 입력해주세요.');
      }
    }
    prevJobsRef.current = jobs;
  }, [jobs]);

  useEffect(() => {
    if (jobs.length === 0) {
      setSelectedJobId(null);
      return;
    }

    if (selectedJobId && jobs.some((job) => job.jobId === selectedJobId)) {
      return;
    }

    const nextSelectedJob =
      jobs.find((job) => job.status === 'RUNNING') ??
      jobs.find((job) => job.status === 'QUEUED') ??
      jobs[0];

    setSelectedJobId(nextSelectedJob?.jobId ?? null);
  }, [jobs, selectedJobId]);

  const filteredJobs = useMemo(() => filterJobsByTab(jobs, tab), [jobs, tab]);
  const historyFilteredJobs = useMemo(() => filterJobsByTab(jobs, historyTab), [jobs, historyTab]);
  const sidebarCounts = useMemo<Record<WorkspaceSection, number>>(
    () => ({
      studio: jobs.filter((job) => job.status === 'RUNNING' || job.status === 'QUEUED').length,
      results: jobs.filter((job) => job.jobType === 'COMPOSITE' && job.status === 'COMPLETED').length,
      history: jobs.length,
    }),
    [jobs]
  );

  const handleCreatedJob = (status: JobStatusResponse) => {
    prependCreatedJob(status);
    setActiveSection('studio');
    setSelectedJobId(status.jobId);
    setCreateModalOpen(false);
    setErrorMessage(null);
  };

  const openCreateModal = () => {
    setActiveSection('studio');
    setCreateModalOpen(true);
    setErrorMessage(null);
  };

  const closeCreateModal = () => {
    setCreateModalOpen(false);
    setErrorMessage(null);
  };

  useEffect(() => {
    if (!guideModalOpen && !settingsModalOpen) {
      return undefined;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') {
        return;
      }

      if (settingsModalOpen) {
        setSettingsModalOpen(false);
        return;
      }

      if (guideModalOpen) {
        setGuideModalOpen(false);
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [guideModalOpen, settingsModalOpen]);

  return (
    <div className="workspace-shell">
      <WorkspaceTopBar activeSection={activeSection} onCreateJob={openCreateModal} />

      <div className="workspace-shell-body">
        <WorkspaceSidebar
          activeSection={activeSection}
          onSelect={setActiveSection}
          onCreateJob={openCreateModal}
          onOpenHelp={() => setGuideModalOpen(true)}
          onOpenSettings={() => setSettingsModalOpen(true)}
          counts={sidebarCounts}
        />

        <main className="workspace-shell-content">
          {activeSection === 'studio' && (
            <WorkspaceStudioView
              filteredJobs={filteredJobs}
              jobs={jobs}
              loadingJobs={loadingJobs}
              selectedJobId={selectedJobId}
              tab={tab}
              onTabChange={setTab}
              onSelectJob={setSelectedJobId}
              onDownload={downloadResult}
              onPlay={openPlayer}
              onLoadPreviews={loadPreviews}
            />
          )}
          {activeSection === 'results' && (
            <WorkspaceResultsView jobs={jobs} loadingJobs={loadingJobs} onDownload={downloadResult} />
          )}
          {activeSection === 'history' && (
            <WorkspaceHistoryView
              filteredJobs={historyFilteredJobs}
              tab={historyTab}
              onTabChange={setHistoryTab}
              onDownload={downloadResult}
              onSelectPreview={loadPreviews}
              totalCount={jobs.length}
            />
          )}
        </main>
      </div>

      {createModalOpen && (
        <>
          <div className="workspace-create-modal-backdrop" onClick={closeCreateModal} />
          <div className="workspace-create-modal">
            <div className="workspace-create-modal-header">
              <div>
                <h2>새 작업 만들기</h2>
                <p>영상과 상품 이미지를 업로드하세요</p>
              </div>
              <button type="button" onClick={closeCreateModal} aria-label="새 작업 모달 닫기">
                ×
              </button>
            </div>
            <div className="workspace-create-modal-body">
              <JobCreateForm
                className="p-5"
                defaultPlacementPrompt={settings.defaults.placementPrompt}
                onCreated={handleCreatedJob}
                onError={setErrorMessage}
              />
            </div>
            {errorMessage && (
              <div className="workspace-create-modal-error">
                <span>{errorMessage}</span>
                <button type="button" onClick={() => setErrorMessage(null)} aria-label="에러 닫기">
                  ×
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {settingsModalOpen && (
        <WorkspaceSettingsModal
          settings={settings}
          onPatchSettings={patchSettings}
          onResetSettings={() => {
            patchSettings(() => DEFAULT_WORKSPACE_SETTINGS);
          }}
          onClose={() => setSettingsModalOpen(false)}
        />
      )}

      {guideModalOpen && <WorkspaceGuideModal onClose={() => setGuideModalOpen(false)} />}

      {playbackUrl && (
        <>
          <div
            onClick={() => setPlaybackUrl(null)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 400 }}
          />
          <div
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              background: '#111',
              borderRadius: 16,
              zIndex: 401,
              width: '80vw',
              maxWidth: 900,
              boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
              animation: 'slideUpToast 0.2s ease',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '12px 16px',
                background: '#1a1a2e',
              }}
            >
              <span style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>영상 미리보기</span>
              <button
                onClick={() => setPlaybackUrl(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#aaa',
                  fontSize: 22,
                  cursor: 'pointer',
                  lineHeight: 1,
                }}
              >
                ×
              </button>
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

      {promptError && (
        <>
          <div
            onClick={() => setPromptError(null)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 300 }}
          />
          <div
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              background: '#fff',
              borderRadius: 16,
              padding: '32px 28px',
              zIndex: 301,
              width: 400,
              maxWidth: '90vw',
              boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
              animation: 'slideUpToast 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: 'linear-gradient(135deg, #ef4444, #f97316)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 20,
                  flexShrink: 0,
                }}
              >
                !
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: '#111', margin: 0 }}>
                프롬프트를 확인해주세요
              </h3>
            </div>
            <p style={{ fontSize: 14, color: '#555', lineHeight: 1.6, margin: 0 }}>{promptError}</p>
            <p style={{ fontSize: 12, color: '#999', marginTop: 12, lineHeight: 1.5 }}>
              예시: "책상 위 빈 공간에 놓아줘", "테이블 오른쪽 컵 옆에 배치해줘"
            </p>
            <button
              onClick={() => setPromptError(null)}
              style={{
                marginTop: 20,
                width: '100%',
                padding: 12,
                background: '#4a6cf7',
                color: '#fff',
                border: 'none',
                borderRadius: 10,
                fontSize: 14,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              확인
            </button>
          </div>
        </>
      )}

      {previewSelecting && (
        <PreviewSelectModal
          jobId={previewSelecting.jobId}
          previews={previewSelecting.previews}
          selecting={selectingIndex}
          onSelect={(index) => handleSelectPreview(previewSelecting.jobId, index)}
          onClose={closePreviewSelection}
        />
      )}
    </div>
  );
}

function JobCard({ job, selected, onSelect, onDownload, onPlay, onSelectPreview }: {
  job: JobItem;
  selected: boolean;
  onSelect: () => void;
  onDownload: (id: string) => Promise<void>;
  onPlay?: (id: string) => Promise<void>;
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
      <div
        style={{
          width: 80,
          height: 52,
          borderRadius: 8,
          background: 'linear-gradient(135deg, #1a1a2e, #0d0d1a)',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'rgba(255,255,255,0.92)',
        }}
      >
        <VideoPanelIcon />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: '#111',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {job.jobId}
          </span>
          {job.jobType && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                padding: '1px 6px',
                borderRadius: 4,
                background: job.jobType === 'PREVIEW' ? '#ede9fe' : '#ecfdf5',
                color: job.jobType === 'PREVIEW' ? '#7c3aed' : '#059669',
              }}
            >
              {job.jobType === 'PREVIEW' ? '프리뷰' : '합성'}
            </span>
          )}
        </div>
        {job.message && (
          <div
            style={{
              fontSize: 12,
              color: '#aaa',
              marginTop: 2,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
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

      <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
        <span className={`job-status-badge ${cfg.badgeCls}`}>{cfg.label}</span>
        {job.status === 'RUNNING' && <span style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b' }}>{progress}%</span>}
        {isPreviewCompleted && (
          <button
            className="download-btn"
            onClick={(event) => {
              event.stopPropagation();
              onSelectPreview(job.jobId);
            }}
          >
            프리뷰 선택
          </button>
        )}
        {isCompositeCompleted && (
          <div style={{ display: 'flex', gap: 4 }}>
            {onPlay && (
              <button
                className="download-btn"
                onClick={(event) => {
                  event.stopPropagation();
                  void onPlay(job.jobId);
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polygon points="6,3 20,12 6,21" />
                </svg>
                재생
              </button>
            )}
            <button
              className="download-btn"
              onClick={(event) => {
                event.stopPropagation();
                void onDownload(job.jobId);
              }}
            >
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
