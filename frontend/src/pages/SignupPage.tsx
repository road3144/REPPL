import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { NavBar } from '../components/NavBar';
import { saveUser } from '../lib/auth';

export function SignupPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!name || !email || !password) {
      setError('모든 필드를 입력해 주세요.');
      return;
    }

    saveUser({ name, email });
    navigate('/studio');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <NavBar />
      <main className="mx-auto flex min-h-[calc(100vh-81px)] max-w-5xl items-center px-6 py-12">
        <div className="grid w-full gap-8 rounded-3xl border border-white/10 bg-slate-900/80 p-8 md:grid-cols-2">
          <section>
            <p className="text-xs font-black uppercase tracking-[0.2em] text-orange-300">Get Started</p>
            <h1 className="mt-3 text-3xl font-black">3주 MVP를 위한 팀 온보딩</h1>
            <p className="mt-4 text-sm leading-6 text-slate-300">
              FE 데모에서는 가입 즉시 작업 스튜디오로 진입됩니다. 이후 결제/권한/크레딧은 백엔드 API와
              연결해 확장하기 쉽게 구성되어 있습니다.
            </p>
          </section>

          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block text-sm">
              <span className="mb-2 block text-slate-300">이름</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-xl border border-white/20 bg-slate-950 px-4 py-3 outline-none ring-orange-400 transition focus:ring"
                placeholder="홍길동"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-2 block text-slate-300">이메일</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-white/20 bg-slate-950 px-4 py-3 outline-none ring-orange-400 transition focus:ring"
                placeholder="you@company.com"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-2 block text-slate-300">비밀번호</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-white/20 bg-slate-950 px-4 py-3 outline-none ring-orange-400 transition focus:ring"
                placeholder="********"
              />
            </label>
            {error ? <p className="text-sm font-semibold text-orange-300">{error}</p> : null}
            <button
              type="submit"
              className="w-full rounded-xl bg-orange-400 px-4 py-3 font-black text-slate-950 transition hover:bg-orange-300"
            >
              회원가입 후 시작하기
            </button>
            <p className="text-center text-sm text-slate-300">
              이미 계정이 있다면 <Link to="/login" className="font-bold text-sky-300">로그인</Link>
            </p>
          </form>
        </div>
      </main>
    </div>
  );
}
