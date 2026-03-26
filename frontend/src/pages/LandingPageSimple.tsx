import { Link } from 'react-router-dom';

export function LandingPageSimple() {
  return (
    <div style={{ position: 'relative', height: '100vh', overflow: 'hidden', background: '#09090b' }}>

      {/* Fullscreen video background */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(160deg, #0a0a14 0%, #111128 40%, #0a0a14 100%)',
      }}>
        <video
          autoPlay
          muted
          loop
          playsInline
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        >
          <source src="/videos/test_video.mp4" type="video/mp4" />
        </video>
        {/* scan-line texture */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(255,255,255,0.015) 3px, rgba(255,255,255,0.015) 4px)',
        }} />
        {/* vignette */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.55) 100%)',
        }} />
      </div>

      {/* Logo — top-left overlay */}
      <div style={{ position: 'absolute', top: 28, left: 48, zIndex: 10 }}>
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 900, letterSpacing: '-0.5px', color: '#fff' }}>
          Re<span style={{ color: '#4a6cf7' }}>PPL</span>
        </span>
      </div>

      {/* Top-right CTA */}
      <div style={{
        position: 'absolute',
        top: 28,
        right: 48,
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
      }}>
        <Link
          to="/studio"
          style={{
            display: 'inline-block',
            padding: '11px 20px',
            background: 'rgba(9,9,11,0.56)',
            color: 'rgba(255,255,255,0.92)',
            borderRadius: 999,
            border: '1px solid rgba(255,255,255,0.14)',
            fontSize: 14,
            fontWeight: 700,
            letterSpacing: '-0.2px',
            lineHeight: 1.2,
            textDecoration: 'none',
            backdropFilter: 'blur(10px)',
            boxShadow: '0 10px 30px rgba(0,0,0,0.28)',
          }}
        >
          서비스 바로가기 →
        </Link>
      </div>

      {/* Footer overlay */}
      <footer style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10,
        textAlign: 'center', padding: '16px 48px', fontSize: 12,
        color: 'rgba(255,255,255,0.52)',
        textShadow: '0 1px 8px rgba(0,0,0,0.45)',
        borderTop: '1px solid rgba(255,255,255,0.08)',
      }}>
        © 2026 RePPL · 삼성 청년 SW·AI 아카데미 14기 · A401팀
      </footer>
    </div>
  );
}
