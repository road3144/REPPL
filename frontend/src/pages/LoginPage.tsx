import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { NavBar } from '../components/NavBar';
import { saveUser } from '../lib/auth';

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!email || !password) {
      setError('이메일과 비밀번호를 입력해 주세요.');
      return;
    }

    saveUser({ name: email.split('@')[0], email });
    navigate('/studio');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <NavBar />
      <main className="mx-auto flex min-h-[calc(100vh-81px)] max-w-5xl items-center px-6 py-12">
        <div className="grid w-full gap-8 rounded-3xl border border-white/10 bg-slate-900/80 p-8 md:grid-cols-2">
          <section>
            <p className="text-xs font-black uppercase tracking-[0.2em] text-sky-300">Sign In</p>
            <h1 className="mt-3 text-3xl font-black">Re:PPL 데모 로그인</h1>
            <p className="mt-4 text-sm leading-6 text-slate-300">
              지금은 FE 데모 단계이므로 입력한 계정으로 즉시 로그인됩니다. 이후 Spring Boot API 연동 시
              실제 인증으로 교체하면 됩니다.
            </p>
          </section>

          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block text-sm">
              <span className="mb-2 block text-slate-300">이메일</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-white/20 bg-slate-950 px-4 py-3 outline-none ring-sky-400 transition focus:ring"
                placeholder="you@company.com"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-2 block text-slate-300">비밀번호</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-white/20 bg-slate-950 px-4 py-3 outline-none ring-sky-400 transition focus:ring"
                placeholder="********"
              />
            </label>
            {error ? <p className="text-sm font-semibold text-orange-300">{error}</p> : null}
            <button
              type="submit"
              className="w-full rounded-xl bg-sky-400 px-4 py-3 font-black text-slate-950 transition hover:bg-sky-300"
            >
              로그인 후 스튜디오 이동
            </button>
            <p className="text-center text-sm text-slate-300">
              계정이 없다면 <Link to="/signup" className="font-bold text-sky-300">회원가입</Link>
            </p>
          </form>
        </div>
      </main>
    </div>
  );
}
