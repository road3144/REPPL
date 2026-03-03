import { Link, useNavigate } from 'react-router-dom';
import { clearUser, getUser } from '../lib/auth';
import { useState } from 'react';

export function NavBar() {
  const user = getUser();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    clearUser();
    navigate('/');
  };

  const navLinks = [
    { href: '/#before-after', label: '데모' },
    { href: '/#problem', label: '문제 정의' },
    { href: '/#workflow', label: '작업 흐름' },
    { href: '/#compare', label: '차별점' },
    { href: '/#value', label: '비용 가치' },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-slate-950/60 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-3.5">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3 group">
          <span className="text-xl font-bold tracking-tight text-white group-hover:text-cyan-400 transition-colors">
            Re:PPL
          </span>
          <span className="hidden sm:inline text-[0.65rem] font-semibold tracking-wide text-slate-500 border border-white/10 rounded-full px-2.5 py-0.5">
            AI 음료 VPP
          </span>
        </Link>

        {/* Desktop Nav */}
        <nav className="hidden lg:flex items-center gap-1 text-sm">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="rounded-lg px-3.5 py-2 text-slate-300 transition hover:text-white hover:bg-white/[0.06]"
            >
              {link.label}
            </a>
          ))}

          <div className="ml-3 h-5 w-px bg-white/10" />

          {user ? (
            <div className="ml-3 flex items-center gap-2">
              <Link
                to="/studio"
                className="btn-primary !py-2 !px-5 !text-sm"
              >
                작업 시작
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/[0.06]"
              >
                로그아웃
              </button>
            </div>
          ) : (
            <div className="ml-3 flex items-center gap-2">
              <Link
                to="/login"
                className="rounded-lg px-4 py-2 text-slate-300 transition hover:text-white hover:bg-white/[0.06]"
              >
                로그인
              </Link>
              <Link
                to="/signup"
                className="btn-primary !py-2 !px-5 !text-sm"
              >
                무료 시작
              </Link>
            </div>
          )}
        </nav>

        {/* Mobile Toggle */}
        <button
          className="lg:hidden text-slate-300 hover:text-white p-2"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="메뉴 열기"
        >
          <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            {mobileOpen ? (
              <>
                <line x1="6" y1="6" x2="18" y2="18" />
                <line x1="6" y1="18" x2="18" y2="6" />
              </>
            ) : (
              <>
                <line x1="4" y1="7" x2="20" y2="7" />
                <line x1="4" y1="12" x2="20" y2="12" />
                <line x1="4" y1="17" x2="20" y2="17" />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div className="lg:hidden border-t border-white/[0.06] bg-slate-950/95 backdrop-blur-xl px-5 pb-5 pt-3 space-y-1">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              onClick={() => setMobileOpen(false)}
              className="block rounded-lg px-4 py-2.5 text-sm text-slate-300 hover:text-white hover:bg-white/[0.06]"
            >
              {link.label}
            </a>
          ))}
          <div className="pt-3 flex flex-col gap-2">
            {user ? (
              <>
                <Link to="/studio" className="btn-primary justify-center !text-sm" onClick={() => setMobileOpen(false)}>
                  작업 시작
                </Link>
                <button onClick={() => { handleLogout(); setMobileOpen(false); }} className="btn-secondary justify-center !text-sm">
                  로그아웃
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="btn-secondary justify-center !text-sm" onClick={() => setMobileOpen(false)}>
                  로그인
                </Link>
                <Link to="/signup" className="btn-primary justify-center !text-sm" onClick={() => setMobileOpen(false)}>
                  무료 시작
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
