export function NavBar() {
  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <header className="nav-glass">
      <div className="nav-inner">
        {/* Logo */}
        <div className="flex items-center">
          <p className="nav-logo">
            <span>Re:PPL</span>
          </p>
          <span className="nav-badge hidden sm:inline">Virtual Product Placement</span>
        </div>

        {/* Links */}
        <nav className="nav-links hidden md:flex">
          <button type="button" className="nav-link" onClick={() => scrollTo('pipeline')}>파이프라인</button>
          <button type="button" className="nav-link" onClick={() => scrollTo('workspace')}>워크스페이스</button>
          <button type="button" className="nav-cta" onClick={() => scrollTo('workspace')}>작업 시작</button>
        </nav>

        {/* Mobile — status only */}
        <div className="flex items-center gap-2 md:hidden">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-[0.65rem] font-semibold text-slate-500">ONLINE</span>
        </div>
      </div>
    </header>
  );
}
