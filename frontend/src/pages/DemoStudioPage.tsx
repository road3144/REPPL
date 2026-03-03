import { FormEvent, useMemo, useState } from 'react';
import { NavBar } from '../components/NavBar';
import { getUser } from '../lib/auth';

type Job = {
  id: number;
  videoName: string;
  brand: string;
  status: '분석중' | '합성중' | '완료';
  eta: string;
};

const statusStyle: Record<Job['status'], string> = {
  분석중: 'text-sky-300',
  합성중: 'text-orange-300',
  완료: 'text-mint'
};

export function DemoStudioPage() {
  const user = getUser();
  const [videoName, setVideoName] = useState('');
  const [brand, setBrand] = useState('');
  const [jobs, setJobs] = useState<Job[]>([
    { id: 1, videoName: 'vlog_episode_08.mp4', brand: 'Coca-Cola Can', status: '완료', eta: '완료됨' },
    { id: 2, videoName: 'studio_talk_021.mp4', brand: 'Sprite PET', status: '합성중', eta: '약 18분' }
  ]);

  const running = useMemo(() => jobs.filter((job) => job.status !== '완료').length, [jobs]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!videoName || !brand) {
      return;
    }

    const nextJob: Job = {
      id: Date.now(),
      videoName,
      brand,
      status: '분석중',
      eta: '약 30분'
    };

    setJobs((prev) => [nextJob, ...prev]);
    setVideoName('');
    setBrand('');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <NavBar />
      <main className="mx-auto max-w-6xl px-6 py-12">
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
            <p className="text-sm text-slate-300">현재 사용자</p>
            <p className="mt-2 text-xl font-black">{user?.name ?? 'Unknown'} 님</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
            <p className="text-sm text-slate-300">진행 중 작업</p>
            <p className="mt-2 text-xl font-black text-orange-300">{running}건</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
            <p className="text-sm text-slate-300">데모 크레딧</p>
            <p className="mt-2 text-xl font-black text-mint">120 Credits</p>
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_1.1fr]">
          <form onSubmit={handleSubmit} className="rounded-3xl border border-white/10 bg-slate-900/70 p-6">
            <h1 className="text-2xl font-black">새 VPP 작업 요청</h1>
            <p className="mt-2 text-sm text-slate-300">영상 파일명과 교체할 음료 브랜드를 입력해 데모 작업을 생성합니다.</p>

            <div className="mt-6 space-y-4">
              <label className="block text-sm">
                <span className="mb-2 block text-slate-300">원본 영상 파일명</span>
                <input
                  type="text"
                  value={videoName}
                  onChange={(e) => setVideoName(e.target.value)}
                  placeholder="ex) creator_vlog_032.mp4"
                  className="w-full rounded-xl border border-white/20 bg-slate-950 px-4 py-3 outline-none ring-sky-400 transition focus:ring"
                />
              </label>
              <label className="block text-sm">
                <span className="mb-2 block text-slate-300">삽입할 음료 브랜드</span>
                <input
                  type="text"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  placeholder="ex) Pepsi Zero Can"
                  className="w-full rounded-xl border border-white/20 bg-slate-950 px-4 py-3 outline-none ring-sky-400 transition focus:ring"
                />
              </label>
            </div>

            <button
              type="submit"
              className="mt-6 w-full rounded-xl bg-sky-400 px-4 py-3 font-black text-slate-950 transition hover:bg-sky-300"
            >
              분석 큐에 작업 추가
            </button>
          </form>

          <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-6">
            <h2 className="text-2xl font-black">작업 현황</h2>
            <div className="mt-5 space-y-3">
              {jobs.map((job) => (
                <article key={job.id} className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-bold text-slate-100">{job.videoName}</p>
                    <span className={`text-sm font-black ${statusStyle[job.status]}`}>{job.status}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-300">브랜드: {job.brand}</p>
                  <p className="mt-1 text-xs text-slate-400">예상 완료: {job.eta}</p>
                </article>
              ))}
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}
