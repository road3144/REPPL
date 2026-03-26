import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  getJobResult,
  getJobs,
  getJobStatus,
  getPreviewUrls,
  initSession,
  selectPreview,
} from '../services/api';
import { downloadBlobFromUrl } from '../services/download';
import {
  buildDownloadFileName,
  readWorkspaceSettings,
} from '../services/workspaceSettings';
import { subscribeJobProgress, WsJobProgress } from '../services/ws';
import type { JobItem, JobStatusResponse, JobType, PreviewItem } from '../services/types';

export type TrackedJob = JobItem & {
  jobType: JobType;
};

export function useJobs() {
  const [jobs, setJobs] = useState<TrackedJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  // 프리뷰 선택 UI 상태
  const [previewSelecting, setPreviewSelecting] = useState<{
    jobId: string;
    previews: PreviewItem[];
  } | null>(null);
  const [selectingIndex, setSelectingIndex] = useState(false);

  // WS 구독 해제 함수 저장
  const wsUnsubs = useRef<Map<string, () => void>>(new Map());

  const running = useMemo(
    () => jobs.filter((job) => job.status === 'QUEUED' || job.status === 'RUNNING').length,
    [jobs]
  );

  // WS 메시지로 Job 상태 업데이트
  const handleWsMessage = useCallback((data: WsJobProgress) => {
    setWsConnected(true);
    setJobs((prev) =>
      prev.map((job) => {
        if (job.jobId !== data.jobId) return job;
        return {
          ...job,
          status: data.status,
          progress: data.progress,
          stage: data.stage ?? null,
          message: data.message || null,
        };
      })
    );
  }, []);

  // 초기 Job 목록 로드
  useEffect(() => {
    let active = true;
    setLoadingJobs(true);

    initSession()
      .then(() => getJobs(0, 20))
      .then((data) => {
        if (!active) return;
        setJobs(
          data.items.map((item) => ({
            ...item,
            jobType: item.jobType ?? 'COMPOSITE',
          }))
        );
      })
      .catch((error: unknown) => {
        if (!active) return;
        setErrorMessage(error instanceof Error ? error.message : '작업 목록 조회에 실패했습니다.');
      })
      .finally(() => {
        if (active) setLoadingJobs(false);
      });

    return () => { active = false; };
  }, []);

  // 활성 Job에 대해 WebSocket 구독 (구독/해제만, cleanup은 언마운트 시만)
  useEffect(() => {
    const activeJobIds = jobs
      .filter((job) => job.status === 'QUEUED' || job.status === 'RUNNING')
      .map((job) => job.jobId);

    // 새로운 활성 Job 구독
    for (const jobId of activeJobIds) {
      if (!wsUnsubs.current.has(jobId)) {
        const unsub = subscribeJobProgress(jobId, handleWsMessage);
        wsUnsubs.current.set(jobId, unsub);
      }
    }

    // 완료/실패된 Job 구독 해제
    for (const [jobId, unsub] of wsUnsubs.current) {
      if (!activeJobIds.includes(jobId)) {
        unsub();
        wsUnsubs.current.delete(jobId);
      }
    }
    // cleanup은 아래 별도 effect에서 언마운트 시만 실행
  });

  // 컴포넌트 언마운트 시 전체 구독 해제
  useEffect(() => {
    return () => {
      for (const unsub of wsUnsubs.current.values()) {
        unsub();
      }
      wsUnsubs.current.clear();
    };
  }, []);

  // WS 연결 실패 시 폴링 폴백
  useEffect(() => {
    if (wsConnected) return;

    const activeJobIds = jobs
      .filter((job) => job.status === 'QUEUED' || job.status === 'RUNNING')
      .map((job) => job.jobId);

    if (activeJobIds.length === 0) return;

    const timer = window.setInterval(() => {
      Promise.all(activeJobIds.map((jobId) => getJobStatus(jobId)))
        .then((statuses) => {
          setJobs((prev) =>
            prev.map((job) => {
              const next = statuses.find((s) => s.jobId === job.jobId);
              if (!next) return job;
              return {
                ...job,
                status: next.status,
                progress: next.progress,
                stage: next.stage,
                message: next.message,
              };
            })
          );
        })
        .catch((error: unknown) => {
          setErrorMessage(error instanceof Error ? error.message : '작업 상태 조회에 실패했습니다.');
        });
    }, 3000);

    return () => { window.clearInterval(timer); };
  }, [jobs, wsConnected]);

  const prependCreatedJob = (status: JobStatusResponse) => {
    setJobs((prev) => [{
      ...status,
      createdAt: null,
      jobType: status.jobType ?? 'PREVIEW',
    }, ...prev]);
  };

  // 프리뷰 완료 시 프리뷰 목록 로드
  const loadPreviews = async (jobId: string) => {
    try {
      const data = await getPreviewUrls(jobId);
      setPreviewSelecting({ jobId, previews: data.previews });
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : '프리뷰 목록 조회에 실패했습니다.');
    }
  };

  // 프리뷰 선택 → 합성 작업 시작
  const handleSelectPreview = async (previewJobId: string, selectedIndex: number) => {
    try {
      setSelectingIndex(true);
      const result = await selectPreview(previewJobId, selectedIndex);
      const compositeStatus = await getJobStatus(result.compositeJobId);
      prependCreatedJob(compositeStatus);
      setPreviewSelecting(null);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : '프리뷰 선택에 실패했습니다.');
    } finally {
      setSelectingIndex(false);
    }
  };

  const downloadResult = async (jobId: string) => {
    try {
      const result = await getJobResult(jobId);
      const settings = readWorkspaceSettings();
      const filename = buildDownloadFileName(
        jobId,
        settings.download.filenamePattern
      );
      await downloadBlobFromUrl(result.download.url, filename);
    } catch {
      setErrorMessage('다운로드에 실패했습니다.');
    }
  };

  const getPlaybackUrl = async (jobId: string): Promise<string> => {
    const result = await getJobResult(jobId);
    return result.download.url;
  };

  return {
    jobs,
    running,
    loadingJobs,
    errorMessage,
    setErrorMessage,
    prependCreatedJob,
    downloadResult,
    getPlaybackUrl,
    // 프리뷰 관련
    previewSelecting,
    selectingIndex,
    loadPreviews,
    handleSelectPreview,
    closePreviewSelection: () => setPreviewSelecting(null),
  };
}
