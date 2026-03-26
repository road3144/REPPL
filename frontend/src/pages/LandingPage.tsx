import { Link } from 'react-router-dom';
import { useScrollReveal } from '../hooks/useScrollReveal';

/* ─── smooth scroll helper ─── */
const scrollTo = (id: string) =>
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });

/* ─── inline SVG icons ─── */
const UploadIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="#4a6cf7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);
const AiIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="#4a6cf7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
  </svg>
);
const DownloadIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="#4a6cf7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
    <path d="M12 2L2 7l10 5 10-5-10-5z" />
    <path d="M2 17l10 5 10-5" />
    <path d="M2 12l10 5 10-5" />
  </svg>
);
const SpeedIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="#4a6cf7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
    <polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);
const CostIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="#4a6cf7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
    <line x1="12" y1="1" x2="12" y2="23" />
    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
  </svg>
);
const QualityIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="#4a6cf7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="2" />
  </svg>
);
const PlayIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" className="w-7 h-7">
    <polygon points="5,3 19,12 5,21" fill="rgba(255,255,255,0.85)" />
  </svg>
);

/* ─── static data ─── */
const NAV_LINKS = [
  { label: '서비스 소개', id: 'intro' },
  { label: '작동 방식', id: 'how' },
  { label: '활용 사례', id: 'benefits' },
  { label: '대상 고객', id: 'who' },
  { label: '문의하기', id: 'contact' },
];

const METRICS = [
  { prefix: '최대', value: '80%', label: '광고 집행 비용 절감', sub: '재촬영·세트 대비' },
  { prefix: '평균', value: '3일', label: '광고 삽입 소요 시간', sub: '기존 6~8주 대비' },
  { prefix: '', value: '99%', label: '원본 화질 유지율', sub: 'AI 합성 정확도' },
];

const STEPS = [
  {
    num: '01',
    icon: <UploadIcon />,
    title: '영상 & 상품 업로드',
    desc: '기존 촬영 영상(MP4)과 삽입할 상품 이미지 또는 키워드를 업로드합니다. 별도 소프트웨어 설치가 필요 없습니다.',
  },
  {
    num: '02',
    icon: <AiIcon />,
    title: 'AI 자동 분석 & 합성',
    desc: 'DINO·SAM·Lucas-Kanade 모델이 장면을 분석하고, 카메라 움직임을 추적하여 상품을 자연스럽게 합성합니다.',
  },
  {
    num: '03',
    icon: <DownloadIcon />,
    title: '결과 영상 다운로드',
    desc: '합성이 완료된 MP4 파일을 즉시 다운로드하거나 방송사·플랫폼에 바로 납품할 수 있습니다.',
  },
];

const TARGETS = [
  {
    avatar: '📺',
    title: '방송사 & OTT 플랫폼',
    desc: '이미 방영된 콘텐츠에 새로운 광고를 삽입하여 추가 수익을 창출하세요. 재방송·VOD 광고 단가를 높입니다.',
    tags: ['KBS / MBC / SBS', 'Netflix / Wavve', '재방송 수익화'],
  },
  {
    avatar: '🎬',
    title: '광고 대행사',
    desc: '광고주 요청이 촬영 이후에 들어와도 문제없습니다. 기존 영상 자산을 활용해 빠르게 캠페인을 집행하세요.',
    tags: ['캠페인 신속 집행', '비용 효율화', 'A/B 테스트'],
  },
  {
    avatar: '🏢',
    title: '브랜드 마케터',
    desc: '인기 드라마·예능의 특정 장면에 자사 제품을 자연스럽게 녹여내어 브랜드 인지도를 효과적으로 높이세요.',
    tags: ['브랜드 인지도', 'PPL 효과 극대화', '타겟 노출'],
  },
];

/* ─── component ─── */
export function LandingPage() {
  const pageRef = useScrollReveal<HTMLDivElement>();

  return (
    <div ref={pageRef} className="bg-white text-slate-900">

      {/* ══════════ NAV ══════════ */}
      <header className="fixed top-0 inset-x-0 z-50 h-[70px] bg-white/95 backdrop-blur-sm border-b border-slate-200 flex items-center justify-between px-10 lg:px-16">
        <div className="text-xl font-black tracking-tight">
          VP<span className="text-brand">PL</span>
        </div>

        <nav className="hidden md:flex items-center gap-8">
          {NAV_LINKS.map(({ label, id }) => (
            <button
              key={id}
              type="button"
              onClick={() => scrollTo(id)}
              className="text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors"
            >
              {label}
            </button>
          ))}
        </nav>

        <Link
          to="/studio"
          className="bg-slate-900 text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-slate-700 transition-colors"
        >
          서비스 바로가기 →
        </Link>
      </header>

      {/* ══════════ HERO ══════════ */}
      <section
        id="intro"
        className="mt-[70px] relative flex items-center justify-center overflow-hidden"
        style={{ height: '90vh', background: 'linear-gradient(135deg, #0d0d0d 0%, #1a1a2e 50%, #0d0d0d 100%)' }}
      >
        <video
          autoPlay
          muted
          loop
          playsInline
          className="absolute inset-0 h-full w-full object-cover"
        >
          <source src="/videos/test_video.mp4" type="video/mp4" />
        </video>

        {/* dark overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/20 to-black/60" />

        {/* play button — bottom center */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-3">
          <div className="w-16 h-16 rounded-full border-2 border-white/30 bg-white/10 flex items-center justify-center cursor-pointer hover:bg-white/20 transition-colors">
            <PlayIcon />
          </div>
          <span className="text-white/40 text-xs tracking-[2px] uppercase">Before / After 데모 영상 재생</span>
        </div>

        {/* content */}
        <div className="relative z-10 text-center max-w-3xl px-6 animate-on-scroll">
          <span
            className="inline-block px-4 py-1.5 rounded-full text-xs font-bold tracking-widest uppercase mb-7"
            style={{ background: 'rgba(74,108,247,0.2)', border: '1px solid rgba(74,108,247,0.4)', color: '#7a9cff' }}
          >
            AI Virtual Product Placement
          </span>

          <h1 className="text-5xl lg:text-6xl font-black leading-[1.1] text-white mb-6 tracking-tight">
            촬영 없이<br />
            광고를 <span className="text-brand-light">삽입</span>하세요
          </h1>

          <p className="text-lg text-white/60 leading-relaxed mb-10">
            이미 촬영이 완료된 드라마·예능 영상에<br />
            AI가 상품을 자연스럽게 합성합니다. 재촬영 없이, 빠르게.
          </p>

          <div className="flex items-center justify-center gap-4">
            <button
              type="button"
              onClick={() => scrollTo('how')}
              className="px-8 py-3.5 rounded-lg font-bold text-white text-sm transition-colors"
              style={{ background: '#4a6cf7' }}
              onMouseOver={(e) => ((e.currentTarget as HTMLButtonElement).style.background = '#3a5ce5')}
              onMouseOut={(e) => ((e.currentTarget as HTMLButtonElement).style.background = '#4a6cf7')}
            >
              작동 방식 보기 →
            </button>
            <button
              type="button"
              onClick={() => scrollTo('who')}
              className="px-8 py-3.5 rounded-lg font-semibold text-white/75 text-sm border border-white/25 hover:bg-white/10 transition-colors"
            >
              대상 고객 알아보기
            </button>
          </div>
        </div>
      </section>

      {/* ══════════ METRICS BAND ══════════ */}
      <div className="bg-slate-50 border-y border-slate-200 py-14 px-10 lg:px-16">
        <div className="max-w-3xl mx-auto flex divide-x divide-slate-200">
          {METRICS.map(({ prefix, value, label, sub }) => (
            <div key={label} className="flex-1 text-center px-8 lg:px-12">
              <div className="text-4xl lg:text-5xl font-black text-brand tracking-tight">
                {prefix && <span className="text-xl font-bold mr-1">{prefix}</span>}
                {value}
              </div>
              <div className="mt-2 text-sm font-medium text-slate-600">{label}</div>
              <div className="mt-1 text-xs text-slate-400">{sub}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ══════════ HOW IT WORKS ══════════ */}
      <section id="how" className="py-24 px-10 lg:px-16 bg-white">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16 animate-on-scroll">
            <span className="inline-block px-4 py-1.5 rounded-full text-xs font-bold tracking-widest uppercase text-brand bg-blue-50 mb-5">
              작동 방식
            </span>
            <h2 className="text-4xl lg:text-[44px] font-black leading-tight tracking-tight">
              3단계로 완성되는<br />AI 광고 합성
            </h2>
            <p className="mt-4 text-lg text-slate-500 leading-relaxed max-w-xl mx-auto">
              복잡한 설정 없이 영상과 상품 이미지만 올리면<br />AI가 나머지를 알아서 처리합니다.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {STEPS.map(({ num, icon, title, desc }, i) => (
              <div
                key={num}
                className={`animate-on-scroll delay-${i + 1} relative border border-slate-200 rounded-2xl p-10 bg-white hover:shadow-brand-sm hover:border-blue-100 transition-all`}
              >
                <span className="absolute top-6 right-7 text-6xl font-black text-slate-100 leading-none select-none">
                  {num}
                </span>
                <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center mb-5">
                  {icon}
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-3">{title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════ BENEFITS (dark) ══════════ */}
      <section id="benefits" className="py-24 px-10 lg:px-16 bg-zinc-950">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16 animate-on-scroll">
            <span
              className="inline-block px-4 py-1.5 rounded-full text-xs font-bold tracking-widest uppercase mb-5"
              style={{ background: 'rgba(74,108,247,0.15)', color: '#7a9cff' }}
            >
              비용 & 시간 효과
            </span>
            <h2 className="text-4xl lg:text-[44px] font-black leading-tight tracking-tight text-white">
              기존 방식과 무엇이<br />다른가요?
            </h2>
            <p className="mt-4 text-lg text-zinc-400 leading-relaxed">
              PPL 재촬영 없이 완성되는 광고 삽입.<br />시간과 예산 모두를 아낍니다.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* wide comparison card */}
            <div
              className="md:col-span-2 rounded-2xl p-10 border animate-on-scroll"
              style={{ background: '#0f1a3a', borderColor: '#2a3a6a' }}
            >
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-5" style={{ background: 'rgba(74,108,247,0.15)', border: '1px solid rgba(74,108,247,0.3)' }}>
                <SpeedIcon />
              </div>
              <h3 className="text-xl font-bold text-white mb-3">기존 재촬영 방식 vs VPPL AI 방식</h3>
              <p className="text-sm text-zinc-400 leading-relaxed mb-8">
                기존 PPL 재촬영은 세트 대관·인력·후반 작업까지 수주~수개월이 소요됩니다.<br />
                VPPL은 영상 업로드 후 평균 <strong className="text-brand-light">3일 이내</strong> 결과물을 제공합니다.
              </p>
              <div className="flex items-center gap-10">
                <div>
                  <div className="text-xs text-zinc-500 mb-1">기존 방식</div>
                  <div className="text-3xl font-black text-zinc-400">6~8주</div>
                  <div className="text-xs text-zinc-600 mt-1">세트·촬영·후반작업 포함</div>
                </div>
                <div className="text-2xl text-zinc-600">→</div>
                <div>
                  <div className="text-xs text-brand-light mb-1">VPPL AI 방식</div>
                  <div className="text-3xl font-black text-brand">3일</div>
                  <div className="text-xs text-brand/70 mt-1">업로드 후 결과 수령</div>
                </div>
              </div>
            </div>

            {/* cost card */}
            <div className="rounded-2xl p-10 border border-zinc-800 bg-zinc-900 animate-on-scroll">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-5" style={{ background: 'rgba(74,108,247,0.15)', border: '1px solid rgba(74,108,247,0.3)' }}>
                <CostIcon />
              </div>
              <h3 className="text-xl font-bold text-white mb-3">비용 최대 80% 절감</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">
                재촬영·세트 대관·배우 섭외 없이 이미 완성된 영상을 활용하여 광고 집행 비용을 대폭 절감합니다.
              </p>
              <div className="mt-5 text-4xl font-black text-brand tracking-tight">- 80%</div>
            </div>

            {/* quality card */}
            <div className="rounded-2xl p-10 border border-zinc-800 bg-zinc-900 animate-on-scroll">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-5" style={{ background: 'rgba(74,108,247,0.15)', border: '1px solid rgba(74,108,247,0.3)' }}>
                <QualityIcon />
              </div>
              <h3 className="text-xl font-bold text-white mb-3">자연스러운 합성 품질</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">
                최신 AI 모델이 카메라 움직임과 조명을 반영하여 육안으로 구분하기 어려운 합성 결과를 제공합니다.
              </p>
              <div className="mt-5 text-4xl font-black text-brand tracking-tight">99%</div>
            </div>
          </div>
        </div>
      </section>

      {/* ══════════ FOR WHO ══════════ */}
      <section id="who" className="py-24 px-10 lg:px-16 bg-slate-50">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16 animate-on-scroll">
            <span className="inline-block px-4 py-1.5 rounded-full text-xs font-bold tracking-widest uppercase text-brand bg-blue-50 mb-5">
              사용 대상
            </span>
            <h2 className="text-4xl lg:text-[44px] font-black leading-tight tracking-tight">
              누구를 위한 서비스인가요?
            </h2>
            <p className="mt-4 text-lg text-slate-500 leading-relaxed max-w-xl mx-auto">
              방송사부터 광고대행사, 브랜드 마케터까지<br />영상 광고가 필요한 모든 분들을 위해 만들었습니다.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-7">
            {TARGETS.map(({ avatar, title, desc, tags }, i) => (
              <div
                key={title}
                className={`animate-on-scroll delay-${i + 1} relative bg-white border border-slate-200 rounded-2xl px-8 py-10 text-center overflow-hidden`}
              >
                {/* top accent bar */}
                <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-brand to-brand-light" />

                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center text-3xl mx-auto mb-5">
                  {avatar}
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-3">{title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed mb-5">{desc}</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {tags.map((tag) => (
                    <span key={tag} className="px-3 py-1 rounded-full text-xs font-semibold text-brand bg-blue-50">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════ CONTACT CTA ══════════ */}
      <section
        id="contact"
        className="py-28 px-10 lg:px-16 text-center"
        style={{ background: 'linear-gradient(135deg, #1a2a6c 0%, #2a4af7 50%, #1a2a6c 100%)' }}
      >
        <div className="animate-on-scroll max-w-2xl mx-auto">
          <h2 className="text-4xl lg:text-5xl font-black text-white tracking-tight mb-5">
            도입 문의하기
          </h2>
          <p className="text-lg text-white/70 leading-relaxed mb-11">
            VPPL의 AI 합성 기술을 귀사의 영상 자산에 적용하고 싶으시다면<br />
            언제든지 문의 주세요. 빠르게 답변 드립니다.
          </p>
          <div className="flex items-center justify-center gap-4">
            <a
              href="mailto:contact@vppl.ai"
              className="px-10 py-4 rounded-xl font-bold text-base bg-white hover:bg-slate-100 transition-colors"
              style={{ color: '#1a2a6c' }}
            >
              문의 남기기 →
            </a>
            <button
              type="button"
              onClick={() => scrollTo('how')}
              className="px-10 py-4 rounded-xl font-semibold text-base text-white border-2 border-white/30 hover:bg-white/10 transition-colors"
            >
              작동 방식 다시 보기
            </button>
          </div>
        </div>
      </section>

      {/* ══════════ FOOTER ══════════ */}
      <footer className="bg-zinc-950 border-t border-zinc-900 px-10 lg:px-16 pt-16 pb-8">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-12 mb-12">
            <div className="col-span-2 md:col-span-1">
              <div className="text-lg font-black text-white mb-4">
                VP<span className="text-brand">PL</span>
              </div>
              <p className="text-sm text-zinc-500 leading-relaxed">
                AI 기반 가상 PPL 합성 서비스.<br />
                이미 촬영된 영상에 상품을<br />자연스럽게 삽입합니다.
              </p>
            </div>

            <div>
              <h4 className="text-xs font-bold text-zinc-600 uppercase tracking-widest mb-5">서비스</h4>
              {['작동 방식', '활용 사례', '대상 고객', '문의하기'].map((item, i) => {
                const ids = ['how', 'benefits', 'who', 'contact'];
                return (
                  <button
                    key={item}
                    type="button"
                    onClick={() => scrollTo(ids[i])}
                    className="block text-sm text-zinc-500 hover:text-white transition-colors mb-3"
                  >
                    {item}
                  </button>
                );
              })}
            </div>

            <div>
              <h4 className="text-xs font-bold text-zinc-600 uppercase tracking-widest mb-5">서비스 이용</h4>
              <Link to="/studio" className="block text-sm text-zinc-500 hover:text-white transition-colors mb-3">
                작업 스튜디오
              </Link>
              <a href="#" className="block text-sm text-zinc-500 hover:text-white transition-colors mb-3">API 문서</a>
              <a href="#" className="block text-sm text-zinc-500 hover:text-white transition-colors mb-3">블로그</a>
            </div>

            <div>
              <h4 className="text-xs font-bold text-zinc-600 uppercase tracking-widest mb-5">법적 고지</h4>
              <a href="#" className="block text-sm text-zinc-500 hover:text-white transition-colors mb-3">이용약관</a>
              <a href="#" className="block text-sm text-zinc-500 hover:text-white transition-colors mb-3">개인정보처리방침</a>
              <a href="#" className="block text-sm text-zinc-500 hover:text-white transition-colors mb-3">저작권 안내</a>
            </div>
          </div>

          <div className="border-t border-zinc-900 pt-7 flex flex-col md:flex-row items-center justify-between gap-3 text-xs text-zinc-600">
            <span>© 2025 VPPL Inc. All rights reserved.</span>
            <span>삼성 청년 SW·AI 아카데미 S14 · A401팀</span>
          </div>
        </div>
      </footer>

    </div>
  );
}
