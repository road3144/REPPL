import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

export function NavBar() {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navLinks = [
    { to: '/#quick', label: '요약' },
    { to: '/#slides', label: '핵심 데모' },
  ];

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname, location.hash]);

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/85 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-3.5">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3 group">
          <span className="text-xl font-bold tracking-tight text-slate-900 group-hover:text-sky-600 transition-colors">
            Re:PPL
          </span>
          <span className="hidden sm:inline text-[0.65rem] font-semibold tracking-wide text-slate-500 border border-slate-200 rounded-full px-2.5 py-0.5">
            AI 음료 VPP
          </span>
        </Link>

        {/* Desktop Nav */}
        <nav className="hidden lg:flex items-center gap-1 text-sm">
          {navLinks.map((link) => (
            <Link
              key={link.label}
              to={link.to}
              className="rounded-lg px-3.5 py-2 text-slate-600 transition hover:text-slate-900 hover:bg-slate-100"
            >
              {link.label}
            </Link>
          ))}

          <div className="ml-3 h-5 w-px bg-slate-200" />
          <div className="ml-3 flex items-center gap-2">
            <Link
              to="/studio"
              className="btn-primary !py-2 !px-5 !text-sm"
            >
              작업 시작
            </Link>
          </div>
        </nav>

        {/* Mobile Toggle */}
        <button
          type="button"
          className="lg:hidden text-slate-600 hover:text-slate-900 p-2"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-controls="mobile-nav"
          aria-expanded={mobileOpen}
          aria-label={mobileOpen ? '메뉴 닫기' : '메뉴 열기'}
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
        <div id="mobile-nav" className="lg:hidden border-t border-slate-200 bg-white/95 backdrop-blur-xl px-5 pb-5 pt-3 space-y-1">
          {navLinks.map((link) => (
            <Link
              key={link.label}
              to={link.to}
              className="block rounded-lg px-4 py-2.5 text-sm text-slate-700 hover:text-slate-900 hover:bg-slate-100"
            >
              {link.label}
            </Link>
          ))}
          <div className="pt-3 flex flex-col gap-2">
            <Link to="/studio" className="btn-primary justify-center !text-sm">
              작업 시작
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
