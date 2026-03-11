import { useEffect, useMemo, useState } from 'react';
import { getJobResult, getJobs, getJobStatus, JobItem, JobStatusResponse } from '../services/demoApi';

export function useDemoJobs() {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const running = useMemo(
    () => jobs.filter((job) => job.status === 'QUEUED' || job.status === 'RUNNING').length,
    [jobs]
  );

  useEffect(() => {
    let active = true;
    setLoadingJobs(true);

    getJobs(0, 20)
      .then((data) => {
        if (!active) {
          return;
        }
        setJobs(data.items);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : '작업 목록 조회에 실패했습니다.');
      })
      .finally(() => {
        if (active) {
          setLoadingJobs(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const activeJobIds = jobs
      .filter((job) => job.status === 'QUEUED' || job.status === 'RUNNING')
      .map((job) => job.jobId);

    if (activeJobIds.length === 0) {
      return;
    }

    const timer = window.setInterval(() => {
      Promise.all(activeJobIds.map((jobId) => getJobStatus(jobId)))
        .then((statuses) => {
          setJobs((prev) =>
            prev.map((job) => {
              const next = statuses.find((status) => status.jobId === job.jobId);
              if (!next) {
                return job;
              }
              return {
                ...job,
                status: next.status,
                progress: next.progress,
                stage: next.stage,
                message: next.message
              };
            })
          );
        })
        .catch((error: unknown) => {
          setErrorMessage(error instanceof Error ? error.message : '작업 상태 조회에 실패했습니다.');
        });
    }, 3000);

    return () => {
      window.clearInterval(timer);
    };
  }, [jobs]);

  const prependCreatedJob = (status: JobStatusResponse) => {
    setJobs((prev) => [{ ...status, createdAt: null }, ...prev]);
  };

  const downloadResult = async (jobId: string) => {
    const result = await getJobResult(jobId);
    window.open(result.download.url, '_blank', 'noopener,noreferrer');
  };

  return {
    jobs,
    running,
    loadingJobs,
    errorMessage,
    setErrorMessage,
    prependCreatedJob,
    downloadResult
  };
}
