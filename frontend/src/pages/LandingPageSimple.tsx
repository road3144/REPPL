import { Link } from 'react-router-dom';

export function LandingPageSimple() {
  return (
    <div style={{ position: 'relative', height: '100vh', overflow: 'hidden', background: '#09090b' }}>

      {/* Fullscreen video background */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(160deg, #0a0a14 0%, #111128 40%, #0a0a14 100%)',
      }}>
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
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 900, letterSpacing: '-0.5px', color: '#fff' }}>
          RE:<span style={{ color: '#4a6cf7' }}>PPL</span>
        </span>
      </div>

      {/* Center overlay */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 5,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 32,
      }}>
        {/* Play button */}
        <div style={{
          width: 88, height: 88, borderRadius: '50%', cursor: 'pointer',
          background: 'rgba(74,108,247,0.22)', border: '2px solid rgba(74,108,247,0.55)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backdropFilter: 'blur(4px)',
        }}>
          <div style={{
            borderLeft: '30px solid rgba(255,255,255,0.92)',
            borderTop: '18px solid transparent', borderBottom: '18px solid transparent',
            marginLeft: 7,
          }} />
        </div>

        <p style={{ fontSize: 11, letterSpacing: 3, textTransform: 'uppercase', color: 'rgba(255,255,255,0.3)', whiteSpace: 'nowrap' }}>
          ▶ &nbsp; Before / After 데모 영상
        </p>

        <Link
          to="/studio"
          style={{
            display: 'inline-block', padding: '18px 56px',
            background: '#4a6cf7', color: '#fff', borderRadius: 12,
            fontSize: 17, fontWeight: 800, letterSpacing: '-0.3px',
            textDecoration: 'none', boxShadow: '0 8px 32px rgba(74,108,247,0.4)',
          }}
        >
          서비스 바로가기 →
        </Link>
      </div>

      {/* Footer overlay */}
      <footer style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10,
        textAlign: 'center', padding: '16px 48px', fontSize: 12,
        color: 'rgba(255,255,255,0.18)', borderTop: '1px solid rgba(255,255,255,0.06)',
      }}>
        © 2025 RE:PPL · 삼성 청년 SW 아카데미 S14 · A401팀
      </footer>
    </div>
  );
}
