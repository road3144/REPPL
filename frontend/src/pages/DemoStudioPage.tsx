import { NavBar } from '../components/NavBar';
import { JobCreateForm } from '../components/studio/JobCreateForm';
import { JobListPanel } from '../components/studio/JobListPanel';
import { useScrollReveal } from '../hooks/useScrollReveal';
import { useDemoJobs } from '../hooks/useDemoJobs';

export function DemoStudioPage() {
  const pageRef = useScrollReveal<HTMLDivElement>();
  const { jobs, running, loadingJobs, errorMessage, setErrorMessage, prependCreatedJob, downloadResult } = useDemoJobs();

  const handleDownload = async (jobId: string) => {
    try {
      await downloadResult(jobId);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : '결과 다운로드 URL 조회에 실패했습니다.');
    }
  };

  return (
    <div className="home-light min-h-screen text-slate-900" ref={pageRef}>
      <NavBar />
      <main className="mx-auto max-w-6xl px-6 py-10">
        <section className="animate-on-scroll mb-6">
          <span className="light-pill">Studio</span>
          <h1 className="mt-4 text-4xl font-black tracking-tight">작업 시작</h1>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <div className="light-metric-card text-left">
            <p className="text-sm text-slate-500">진행 중 작업</p>
            <p className="mt-2 text-2xl font-black text-sky-600">{running}건</p>
          </div>
          <div className="light-metric-card text-left">
            <p className="text-sm text-slate-500">데모 크레딧</p>
            <p className="mt-2 text-2xl font-black text-sky-600">120 Credits</p>
          </div>
          <div className="light-metric-card text-left">
            <p className="text-sm text-slate-500">평균 처리 시간</p>
            <p className="mt-2 text-2xl font-black text-sky-600">24h 이내</p>
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_1.1fr]">
          <div>
            <JobCreateForm onCreated={prependCreatedJob} onError={setErrorMessage} />
            {errorMessage ? <p className="mt-3 text-sm text-rose-600">{errorMessage}</p> : null}
          </div>
          <JobListPanel jobs={jobs} loadingJobs={loadingJobs} onDownload={handleDownload} />
        </section>
      </main>
    </div>
  );
}
