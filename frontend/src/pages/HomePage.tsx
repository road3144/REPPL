import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { NavBar } from '../components/NavBar';

function useScrollReveal() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) entry.target.classList.add('visible');
        });
      },
      { threshold: 0.12 }
    );
    el.querySelectorAll('.animate-on-scroll').forEach((child) => observer.observe(child));
    return () => observer.disconnect();
  }, []);
  return ref;
}

const slides = [
  {
    title: 'Before / After',
    image: '/images/before_after_demo.png',
    items: ['음료 자동 교체', '장면 이질감 최소화', '쇼츠용 결과 바로 생성'],
  },
  {
    title: '자동 파이프라인',
    image: '/images/process_flow.png',
    items: ['영상 업로드', '장면 탐지 + 추천', '합성 + 9:16 변환'],
  },
];

export function HomePage() {
  const mainRef = useScrollReveal();
  const ctaLink = '/studio';
  const ctaLabel = '바로 작업 시작';

  return (
    <div className="home-light min-h-screen text-slate-900" ref={mainRef}>
      <NavBar />

      <section className="home-hero">
        <div className="section-container relative z-10">
          <div className="mx-auto max-w-5xl text-center">
            <span className="light-pill">YouTube Shorts AI VPP</span>
            <h1 className="mt-6 text-4xl font-bold tracking-tight sm:text-5xl">
              촬영 끝난 영상으로
              <br />
              광고 컷을 바로 만듭니다
            </h1>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link to={ctaLink} className="btn-primary">{ctaLabel}</Link>
              <a href="#slides" className="btn-light-secondary">데모 보기</a>
            </div>
          </div>
        </div>
      </section>

      <section id="quick" className="section-container !pt-8 sm:!pt-10">
        <div className="animate-on-scroll grid gap-4 sm:grid-cols-3">
          {[
            { value: '촬영 0회', label: '추가 촬영 없음' },
            { value: '24h', label: '결과 도출' },
            { value: '70%+', label: '제작비 절감' },
          ].map((item) => (
            <div key={item.value} className="light-metric-card">
              <p className="text-2xl font-extrabold text-sky-600">{item.value}</p>
              <p className="mt-1 text-sm text-slate-600">{item.label}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="slides" className="section-container">
        <div className="mx-auto max-w-6xl space-y-6">
          {slides.map((slide, idx) => (
            <div key={slide.title} className={`animate-on-scroll ${idx > 0 ? 'delay-1' : ''} light-slide-card`}>
              <div className="grid items-center gap-6 lg:grid-cols-[1.2fr_1fr]">
                <div className="img-showcase !border-slate-200 !rounded-2xl">
                  <img src={slide.image} alt={slide.title} />
                </div>
                <div>
                  <h2 className="text-3xl font-bold text-slate-900">{slide.title}</h2>
                  <div className="mt-5 flex flex-wrap gap-2">
                    {slide.items.map((item) => (
                      <span key={item} className="light-chip">{item}</span>
                    ))}
                  </div>
                  <div className="mt-8">
                    <Link to={ctaLink} className="btn-primary">{ctaLabel}</Link>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section-container !pt-2 sm:!pt-4 !pb-16">
        <div className="animate-on-scroll light-cta-box text-center">
          <h2 className="text-2xl font-bold sm:text-3xl">긴 설명 없이, 바로 작업</h2>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link to={ctaLink} className="btn-primary">{ctaLabel}</Link>
            <a href="#slides" className="btn-light-secondary">핵심 화면 다시 보기</a>
          </div>
        </div>
      </section>
    </div>
  );
}
