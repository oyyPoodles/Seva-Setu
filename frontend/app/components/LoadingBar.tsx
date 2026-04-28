'use client';

/** Thin progress bar shown at the top of the page during loading. */
export default function LoadingBar() {
  return (
    <>
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, height: 3,
        background: '#F5F5F4', zIndex: 9999,
      }}>
        <div style={{
          height: '100%', background: 'linear-gradient(90deg, #059669, #10B981)', borderRadius: '0 2px 2px 0',
          animation: 'loadbar 1.2s ease-in-out infinite',
        }} />
      </div>
      <style>{`
        @keyframes loadbar {
          0%   { width: 0; margin-left: 0; }
          50%  { width: 60%; margin-left: 20%; }
          100% { width: 0; margin-left: 100%; }
        }
      `}</style>
    </>
  );
}
