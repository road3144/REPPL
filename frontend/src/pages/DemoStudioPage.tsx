import { FormEvent, useMemo, useState } from 'react';
import { NavBar } from '../components/NavBar';
import { useScrollReveal } from '../hooks/useScrollReveal';

type Job = {
  id: number;
  videoName: string;
  brand: string;
  status: '분석중' | '합성중' | '완료';
  eta: string;
};

const statusStyle: Record<Job['status'], string> = {
  분석중: 'text-sky-700',
  합성중: 'text-amber-600',
  완료: 'text-emerald-600'
};

export function DemoStudioPage() {
  const pageRef = useScrollReveal<HTMLDivElement>();
  const [videoName, setVideoName] = useState('');
  const [brand, setBrand] = useState('');
  const [jobs, setJobs] = useState<Job[]>([
    { id: 1, videoName: 'vlog_episode_08.mp4', brand: 'Coca-Cola Can', status: '완료', eta: '완료됨' },
    { id: 2, videoName: 'studio_talk_021.mp4', brand: 'Sprite PET', status: '합성중', eta: '약 18분' }
  ]);

  const running = useMemo(() => jobs.filter((job) => job.status !== '완료').length, [jobs]);
  const canSubmit = videoName.trim().length > 0 && brand.trim().length > 0;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmedVideoName = videoName.trim();
    const trimmedBrand = brand.trim();

    if (!trimmedVideoName || !trimmedBrand) {
      return;
    }

    const nextJob: Job = {
      id: Date.now(),
      videoName: trimmedVideoName,
      brand: trimmedBrand,
      status: '분석중',
      eta: '약 30분'
    };

    setJobs((prev) => [nextJob, ...prev]);
    setVideoName('');
    setBrand('');
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
          <form onSubmit={handleSubmit} className="light-slide-card">
            <h2 className="text-2xl font-black text-slate-900">새 VPP 작업 요청</h2>

            <div className="mt-6 space-y-4">
              <label className="block text-sm">
                <span className="mb-2 block text-slate-600">원본 영상 파일명</span>
                <input
                  type="text"
                  value={videoName}
                  onChange={(e) => setVideoName(e.target.value)}
                  placeholder="ex) creator_vlog_032.mp4"
                  autoComplete="off"
                  required
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none ring-sky-400 transition focus:ring"
                />
              </label>
              <label className="block text-sm">
                <span className="mb-2 block text-slate-600">삽입할 음료 브랜드</span>
                <input
                  type="text"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  placeholder="ex) Pepsi Zero Can"
                  autoComplete="off"
                  required
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none ring-sky-400 transition focus:ring"
                />
              </label>
            </div>

            <button
              type="submit"
              disabled={!canSubmit}
              className="mt-6 w-full rounded-xl bg-sky-500 px-4 py-3 font-black text-white transition enabled:hover:bg-sky-600 disabled:cursor-not-allowed disabled:bg-sky-300"
            >
              분석 큐에 작업 추가
            </button>
          </form>

          <section className="light-slide-card">
            <h2 className="text-2xl font-black text-slate-900">작업 현황</h2>
            <div className="mt-5 space-y-3" aria-live="polite">
              {jobs.map((job) => (
                <article key={job.id} className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-bold text-slate-800">{job.videoName}</p>
                    <span className={`text-sm font-black ${statusStyle[job.status]}`}>{job.status}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">브랜드: {job.brand}</p>
                  <p className="mt-1 text-xs text-slate-500">예상 완료: {job.eta}</p>
                </article>
              ))}
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}
