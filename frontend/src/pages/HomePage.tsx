import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { NavBar } from '../components/NavBar';
import { isLoggedIn } from '../lib/auth';

/* ─── Scroll animation hook ─── */
function useScrollReveal() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
          }
        });
      },
      { threshold: 0.12 }
    );
    el.querySelectorAll('.animate-on-scroll').forEach((child) => observer.observe(child));
    return () => observer.disconnect();
  }, []);
  return ref;
}

/* ─── Data ─── */
const processSteps = [
  { icon: '📤', title: '영상 업로드', desc: '유튜브 영상 또는 편집본을 업로드합니다.' },
  { icon: '🔍', title: '음료 장면 자동 탐지', desc: '손 + 입 + 용기 동시 조건으로 음료 섭취 장면을 추출합니다.' },
  { icon: '🎯', title: '최적 컷 추천', desc: '광고 효과가 높은 구간을 우선순위로 제안합니다.' },
  { icon: '🤖', title: 'AI 합성', desc: '조명·반사·가림을 반영해 이질감 없이 음료를 교체합니다.' },
  { icon: '📱', title: '쇼츠 변환', desc: '9:16 비율 변환, 자막 유지, 전후 10초 자동 컷팅합니다.' },
  { icon: '✅', title: '최종 산출물', desc: '유튜브 쇼츠에 바로 업로드 가능한 버전을 패키징합니다.' },
];

const painPoints = [
  {
    icon: '⚡',
    title: '쇼츠에 PPL을 넣을 수 없다',
    desc: '롱폼 촬영 이후 쇼츠로 재가공하지만, 새로운 PPL을 추가할 방법이 없습니다.',
  },
  {
    icon: '💸',
    title: '기존 PPL은 추가 촬영에 의존',
    desc: '새로운 브랜드 음료를 넣으려면 재촬영이나 수작업 VFX가 필요합니다. 비용이 20~100만원까지.',
  },
  {
    icon: '🚧',
    title: '소규모 제작자에게 진입 장벽',
    desc: 'VPP 시장은 99% B2B 엔터프라이즈 모델이라 개인 크리에이터는 접근 자체가 어렵습니다.',
  },
];

const comparisons = [
  { category: '작업 시작', old: '텍스트 프롬프트 입력', reppl: '영상 자동 분석 → 위치 추천' },
  { category: '광고 위치', old: '사용자가 수동 지정', reppl: '음료 섭취 동작 자동 탐지' },
  { category: '최종 결과물', old: '단발성 합성 이미지', reppl: '쇼츠용 리패키징 + 배포 가능 버전' },
  { category: '후처리', old: '별도 편집 필요', reppl: '9:16 변환 + 자막 보존 자동 처리' },
];

/* ─── Component ─── */
export function HomePage() {
  const loggedIn = isLoggedIn();
  const mainRef = useScrollReveal();
  const ctaLink = loggedIn ? '/studio' : '/signup';
  const ctaLabel = loggedIn ? '바로 작업 시작' : '무료로 시작하기';

  return (
    <div className="min-h-screen text-white" ref={mainRef}>
      <NavBar />

      {/* ═══════════════ HERO ═══════════════ */}
      <section className="hero-section">
        <div className="section-container relative z-10 grid items-center gap-10 lg:grid-cols-2">
          {/* Copy */}
          <div className="flex flex-col gap-6">
            <span className="tag-pill">
              <span className="inline-block h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
              YouTube Shorts 전용 AI 음료 VPP
            </span>

            <h1 className="text-4xl font-bold leading-[1.15] tracking-tight sm:text-5xl lg:text-[3.4rem]">
              이미 촬영된 영상에서
              <br />
              <span className="gradient-text">추가 광고 수익</span>을
              <br />
              자동으로 만드세요
            </h1>

            <p className="max-w-lg text-lg leading-relaxed text-slate-300">
              <strong className="text-white">Re:PPL</strong>은 업로드된 영상 속 음료 장면을 AI가 자동 탐지하고,
              브랜드 음료로 교체한 뒤 쇼츠로 재가공하는 SaaS입니다.
            </p>

            <p className="max-w-lg text-sm text-slate-400">
              추가 촬영 없이, 프롬프트 입력 없이 — 영상을 올리기만 하면 됩니다.
            </p>

            <div className="flex flex-wrap gap-4 pt-2">
              <Link to={ctaLink} className="btn-primary">{ctaLabel} →</Link>
              <a href="#before-after" className="btn-secondary">서비스 살펴보기 ↓</a>
            </div>

            {/* Mini stats */}
            <div className="mt-4 grid grid-cols-3 gap-3">
              {[
                { num: '촬영 0회', sub: '재촬영 불필요' },
                { num: '24h 이내', sub: '결과 산출' },
                { num: '70%↓', sub: '제작비 절감' },
              ].map((s) => (
                <div key={s.num} className="rounded-xl border border-white/8 bg-white/[0.03] px-4 py-3 text-center">
                  <p className="text-xl font-bold gradient-text">{s.num}</p>
                  <p className="mt-1 text-xs text-slate-400">{s.sub}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Hero Image */}
          <div className="img-showcase glow-cyan float-anim">
            <img src="/images/hero_banner.png" alt="Re:PPL AI 기반 가상 음료 PPL 합성 — Before & After" />
          </div>
        </div>
      </section>

      <hr className="gradient-divider" />

      {/* ═══════════════ MARKET BACKGROUND ═══════════════ */}
      <section className="section-container">
        <div className="animate-on-scroll mx-auto max-w-3xl text-center">
          <span className="tag-pill">Market Insight</span>
          <h2 className="mt-5 text-3xl font-bold sm:text-4xl">
            VPP 시장, <span className="gradient-text">왜 지금</span>인가?
          </h2>
          <p className="mt-4 text-slate-300 leading-relaxed">
            2025년 3월, CJ ENM이 국내 최초로 VPP를 도입하며 시장 가치가 증명되었습니다.<br />
            하지만 VPP 시장의 99%는 B2B 엔터프라이즈 모델 — 개인 크리에이터와 소규모 제작사에게는 높은 진입 장벽이 존재합니다.
          </p>
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {[
            { value: '₩2조+', label: '국내 PPL 시장 규모', color: 'text-cyan-400' },
            { value: '99%', label: 'B2B 엔터프라이즈 독점', color: 'gradient-text-warm' },
            { value: '2025.03', label: 'CJ ENM VPP 최초 도입', color: 'text-emerald-400' },
          ].map((m, i) => (
            <div key={m.label} className={`animate-on-scroll delay-${i + 1} glass-card p-6 text-center`}>
              <p className={`metric-big ${m.color}`}>{m.value}</p>
              <p className="mt-3 text-sm text-slate-300">{m.label}</p>
            </div>
          ))}
        </div>
      </section>

      <hr className="gradient-divider" />

      {/* ═══════════════ BEFORE / AFTER ═══════════════ */}
      <section id="before-after" className="section-container">
        <div className="animate-on-scroll text-center">
          <span className="tag-pill">핵심 데모</span>
          <h2 className="mt-5 text-3xl font-bold sm:text-4xl">
            커피를 <span className="gradient-text">코카콜라</span>로, AI가 자동으로
          </h2>
          <p className="mt-4 max-w-2xl mx-auto text-slate-300">
            영상 속 음료를 바꾸고, 쇼츠로 재가공하는 전 과정을 자동화합니다.
            아래는 실제 적용 시나리오의 Before → After 비교입니다.
          </p>
        </div>

        <div className="animate-on-scroll delay-2 mt-10 img-showcase glow-cyan mx-auto max-w-4xl">
          <img src="/images/before_after_demo.png" alt="Before: 커피컵 → After: 코카콜라 캔 — AI 자동 합성 데모" />
        </div>

        <div className="mt-10 grid gap-6 md:grid-cols-2 max-w-4xl mx-auto">
          <div className="animate-on-scroll delay-2 compare-old">
            <p className="text-xs font-bold tracking-widest text-orange-300 uppercase">Before</p>
            <p className="mt-3 text-sm text-slate-200">기존 촬영 영상에 일반 커피컵이 노출된 상태. 별도 PPL 수익 없음.</p>
          </div>
          <div className="animate-on-scroll delay-3 compare-new">
            <p className="text-xs font-bold tracking-widest text-cyan-300 uppercase">After — Re:PPL</p>
            <p className="mt-3 text-sm text-slate-100">AI가 음료를 브랜드 제품으로 교체. 쇼츠로 자동 리패키징하여 추가 광고 수익 창출.</p>
          </div>
        </div>
      </section>

      <hr className="gradient-divider" />

      {/* ═══════════════ PAIN POINTS ═══════════════ */}
      <section id="problem" className="section-container">
        <div className="animate-on-scroll text-center">
          <span className="tag-pill">Problem</span>
          <h2 className="mt-5 text-3xl font-bold sm:text-4xl">
            촬영이 끝난 영상은 <span className="gradient-text-warm">광고 수익을 더 만들 수 없다?</span>
          </h2>
          <p className="mt-4 text-slate-300">
            유튜브 크리에이터가 겪는 핵심 문제 3가지를 Re:PPL이 해결합니다.
          </p>
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {painPoints.map((p, i) => (
            <article key={p.title} className={`animate-on-scroll delay-${i + 1} pain-card`}>
              <span className="text-3xl">{p.icon}</span>
              <h3 className="mt-4 text-lg font-bold text-slate-100">{p.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-slate-300">{p.desc}</p>
            </article>
          ))}
        </div>
      </section>

      <hr className="gradient-divider" />

      {/* ═══════════════ PROCESS / PIPELINE ═══════════════ */}
      <section id="workflow" className="section-container">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <div>
            <div className="animate-on-scroll">
              <span className="tag-pill">How It Works</span>
              <h2 className="mt-5 text-3xl font-bold sm:text-4xl">
                영상 업로드 하나로<br />
                <span className="gradient-text">6단계 자동 처리</span>
              </h2>
              <p className="mt-4 text-slate-300 leading-relaxed">
                프롬프트 없이, 위치 지정 없이 — 영상을 올리면 AI가 음료 섭취 장면을 찾아
                브랜드 제품으로 교체하고 쇼츠로 변환합니다.
              </p>
            </div>

            <div className="mt-8 space-y-3">
              {processSteps.map((step, idx) => (
                <div key={step.title} className={`animate-on-scroll delay-${Math.min(idx + 1, 5)} step-card flex items-start gap-4`}>
                  <span className="step-number">{idx + 1}</span>
                  <div>
                    <p className="font-bold text-slate-100">
                      <span className="mr-2">{step.icon}</span>{step.title}
                    </p>
                    <p className="mt-1 text-sm text-slate-400">{step.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="animate-on-scroll delay-2 img-showcase glow-cyan">
            <img src="/images/process_flow.png" alt="Re:PPL AI 파이프라인 — 탐지, 합성, 쇼츠 변환 3단계" />
          </div>
        </div>
      </section>

      <hr className="gradient-divider" />

      {/* ═══════════════ COMPARISON ═══════════════ */}
      <section id="compare" className="section-container">
        <div className="animate-on-scroll text-center">
          <span className="tag-pill">Difference</span>
          <h2 className="mt-5 text-3xl font-bold sm:text-4xl">
            기존 비디오 생성 AI와 <span className="gradient-text">완전히 다릅니다</span>
          </h2>
          <p className="mt-4 text-slate-300 max-w-2xl mx-auto">
            Re:PPL은 "이미지 생성 도구"가 아니라 <strong className="text-white">"영상 광고 자동 리패키징 도구"</strong>입니다.
          </p>
        </div>

        <div className="mt-12 grid gap-4 max-w-4xl mx-auto">
          {/* Header */}
          <div className="grid grid-cols-[1fr_1fr_1fr] gap-3 px-4 text-xs font-bold uppercase tracking-widest text-slate-500">
            <span>항목</span>
            <span>기존 방식</span>
            <span>Re:PPL</span>
          </div>
          {comparisons.map((c, i) => (
            <div key={c.category} className={`animate-on-scroll delay-${Math.min(i + 1, 5)} grid grid-cols-[1fr_1fr_1fr] gap-3 items-center rounded-xl border border-white/6 bg-white/[0.02] p-4`}>
              <p className="font-bold text-sm text-slate-200">{c.category}</p>
              <p className="text-sm text-orange-200/80">{c.old}</p>
              <p className="text-sm text-cyan-200 font-semibold">{c.reppl}</p>
            </div>
          ))}
        </div>
      </section>

      <hr className="gradient-divider" />

      {/* ═══════════════ VALUE / ROI ═══════════════ */}
      <section id="value" className="section-container">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <div className="animate-on-scroll img-showcase glow-orange">
            <img src="/images/cost_comparison.png" alt="기존 방식 vs Re:PPL 비용 비교 인포그래픽" />
          </div>

          <div>
            <div className="animate-on-scroll">
              <span className="tag-pill">ROI</span>
              <h2 className="mt-5 text-3xl font-bold sm:text-4xl">
                대기업형 VPP 비용을
                <br />
                <span className="gradient-text">소규모 제작에 맞춤</span>
              </h2>
            </div>

            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              {/* Old way */}
              <div className="animate-on-scroll delay-1 compare-old">
                <p className="text-xs font-bold tracking-widest text-orange-300 uppercase">기존 방식</p>
                <ul className="mt-3 space-y-2 text-sm text-slate-300">
                  <li className="flex items-start gap-2"><span className="mt-1 text-orange-400">✕</span> 편집자 섭외 20~50만원</li>
                  <li className="flex items-start gap-2"><span className="mt-1 text-orange-400">✕</span> VFX 작업 30~100만원</li>
                  <li className="flex items-start gap-2"><span className="mt-1 text-orange-400">✕</span> 합성 검수 1~2주</li>
                  <li className="flex items-start gap-2"><span className="mt-1 text-orange-400">✕</span> 브랜드 변경 시 리워크</li>
                </ul>
              </div>
              {/* Re:PPL */}
              <div className="animate-on-scroll delay-2 compare-new">
                <p className="text-xs font-bold tracking-widest text-cyan-300 uppercase">Re:PPL</p>
                <ul className="mt-3 space-y-2 text-sm text-slate-100">
                  <li className="flex items-start gap-2"><span className="mt-1 text-cyan-400">✓</span> 크레딧 기반 저렴한 비용</li>
                  <li className="flex items-start gap-2"><span className="mt-1 text-cyan-400">✓</span> 자동화 파이프라인</li>
                  <li className="flex items-start gap-2"><span className="mt-1 text-cyan-400">✓</span> 24시간 이내 결과</li>
                  <li className="flex items-start gap-2"><span className="mt-1 text-cyan-400">✓</span> 빠른 반복 테스트</li>
                </ul>
              </div>
            </div>

            {/* Big metrics */}
            <div className="mt-8 grid grid-cols-3 gap-3">
              {[
                { value: '70%', label: '제작비 절감', color: 'text-cyan-400' },
                { value: '80%', label: '시간 단축', color: 'text-emerald-400' },
                { value: '∞', label: '쇼츠 수익 확장', color: 'gradient-text-warm' },
              ].map((m, i) => (
                <div key={m.label} className={`animate-on-scroll delay-${i + 1} glass-card p-5 text-center`}>
                  <p className={`metric-big ${m.color}`}>{m.value}</p>
                  <p className="mt-2 text-xs text-slate-400">{m.label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <hr className="gradient-divider" />

      {/* ═══════════════ SHORTS SHOWCASE ═══════════════ */}
      <section className="section-container">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <div>
            <div className="animate-on-scroll">
              <span className="tag-pill">Result</span>
              <h2 className="mt-5 text-3xl font-bold sm:text-4xl">
                결과물은 <span className="gradient-text">쇼츠에 바로 업로드</span>
              </h2>
              <p className="mt-4 text-slate-300 leading-relaxed">
                Re:PPL의 최종 산출물은 단순 합성 이미지가 아닙니다.
                9:16 비율 변환, 자막 보존, 전후 10초 컷팅까지 완료된
                <strong className="text-white"> 유튜브 쇼츠 업로드용 영상</strong>입니다.
              </p>
              <p className="mt-3 text-sm text-slate-400">
                쇼츠 광고 단가 상승 추세에 맞춰, 기존 롱폼 영상에서 추가 수익을 창출하세요.
              </p>
            </div>

            <div className="animate-on-scroll delay-2 mt-8 grid grid-cols-2 gap-3">
              {[
                { icon: '📐', label: '9:16 자동 변환' },
                { icon: '💬', label: '자막 자동 유지' },
                { icon: '✂️', label: '전후 10초 컷' },
                { icon: '🚀', label: '즉시 업로드 가능' },
              ].map((f) => (
                <div key={f.label} className="step-card flex items-center gap-3 !p-4">
                  <span className="text-xl">{f.icon}</span>
                  <p className="text-sm font-semibold text-slate-200">{f.label}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="animate-on-scroll delay-1 img-showcase glow-mint">
            <img src="/images/shorts_mockup.png" alt="Re:PPL 쇼츠 결과물 모업 — 수익 대시보드" />
          </div>
        </div>
      </section>

      <hr className="gradient-divider" />

      {/* ═══════════════ FINAL CTA ═══════════════ */}
      <section className="section-container">
        <div className="animate-on-scroll glass-card-strong p-10 sm:p-16 text-center glow-cyan pulse-glow">
          <h2 className="text-3xl font-bold sm:text-4xl">
            추가 촬영 없이<br />
            <span className="gradient-text">쇼츠 광고 자산</span>을 운영해보세요
          </h2>
          <p className="mt-5 text-slate-300 max-w-xl mx-auto">
            지금은 이미 가진 영상에서 수익화를 확장할 수 있는 타이밍입니다.
            Re:PPL로 쇼츠당 추가 광고 수익을 만들어보세요.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <Link to={ctaLink} className="btn-primary text-base">{ctaLabel} →</Link>
            <a href="#workflow" className="btn-secondary">동작 방식 보기</a>
          </div>
        </div>
      </section>

      {/* ═══════════════ FOOTER ═══════════════ */}
      <footer className="border-t border-white/5 py-10 text-center text-sm text-slate-500">
        <p>© 2025 Re:PPL — AI 기반 가상 간접 광고 자동 합성 서비스</p>
        <p className="mt-1">YouTube Shorts 전용 음료 VPP SaaS</p>
      </footer>
    </div>
  );
}
