'use client';
import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { createChatWebSocket } from '@/lib/api';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

interface Message {
  role: 'user' | 'assistant';
  text: string;
}

// ════════════════════════════════════════════════════════════════
// SEVABOT MASCOT – Holographic Drone with full CSS animation
// ════════════════════════════════════════════════════════════════
function SevaDrone({ size = 72, isTyping = false, floating = false }: {
  size?: number; isTyping?: boolean; floating?: boolean;
}) {
  return (
    <>
      <style>{`
        @keyframes droneFloat {
          0%,100% { transform: translateY(0) rotate(-1deg); }
          50% { transform: translateY(-8px) rotate(1deg); }
        }
        @keyframes rotorSpin {
          from { transform: rotateX(70deg) rotate(0deg); }
          to { transform: rotateX(70deg) rotate(360deg); }
        }
        @keyframes eyeBlink {
          0%,90%,100% { transform: scaleY(1); }
          95% { transform: scaleY(0.08); }
        }
        @keyframes glowPulse {
          0%,100% { filter: drop-shadow(0 0 4px #10B98188); }
          50% { filter: drop-shadow(0 0 12px #10B981cc); }
        }
        @keyframes antennaGlow {
          0%,100% { fill: #10B981; r: 3; }
          50% { fill: #6EE7B7; r: 4.5; }
        }
        @keyframes typingMouth {
          0%,100% { d: path("M 33 60 Q 50 65 67 60"); }
          50%   { d: path("M 33 63 Q 50 57 67 63"); }
        }
        @keyframes scanLine {
          from { transform: translateY(0); opacity: 0.6; }
          to { transform: translateY(24px); opacity: 0; }
        }
        @keyframes bodyGlow {
          0%,100% { opacity: 0.08; }
          50% { opacity: 0.2; }
        }
        .drone-wrap { animation: ${floating ? 'droneFloat 3s ease-in-out infinite' : 'none'}; }
        .drone-glow { animation: glowPulse 2.5s ease-in-out infinite; }
        .drone-eye-l { animation: eyeBlink 5s infinite 0.1s; transform-box: fill-box; transform-origin: 50% 50%; }
        .drone-eye-r { animation: eyeBlink 5s infinite 0.4s; transform-box: fill-box; transform-origin: 50% 50%; }
        .drone-antenna { animation: antennaGlow 1.6s ease-in-out infinite; }
        .rotor-l { transform-origin: 18px 86px; animation: rotorSpin 0.25s linear infinite; }
        .rotor-r { transform-origin: 82px 86px; animation: rotorSpin 0.25s linear infinite reverse; }
        .scan-line { animation: scanLine 1.2s linear infinite; }
        .body-inner-glow { animation: bodyGlow 2s ease-in-out infinite; }
      `}</style>
      <div className="drone-wrap" style={{ width: size, height: size, display: 'inline-block' }}>
        <svg viewBox="0 0 100 100" width={size} height={size} className="drone-glow">
          <defs>
            <linearGradient id="dBodyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1D8A5A" />
              <stop offset="100%" stopColor="#0D5C3C" />
            </linearGradient>
            <linearGradient id="dFaceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#E0FEF4" />
              <stop offset="100%" stopColor="#CCFBEB" />
            </linearGradient>
            <linearGradient id="dRotorGrad" x1="-1" y1="0" x2="1" y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#10B981" stopOpacity="0.9" />
              <stop offset="50%" stopColor="#6EE7B7" />
              <stop offset="100%" stopColor="#10B981" stopOpacity="0.9" />
            </linearGradient>
            <filter id="dShadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#059669" floodOpacity="0.4" />
            </filter>
          </defs>

          {/* Antenna post */}
          <line x1="50" y1="4" x2="50" y2="16" stroke="#059669" strokeWidth="2" strokeLinecap="round" />
          {/* Antenna tip */}
          <circle className="drone-antenna" cx="50" cy="3.5" r="3" />

          {/* Main body */}
          <rect x="18" y="18" width="64" height="56" rx="16" fill="url(#dBodyGrad)" filter="url(#dShadow)" />

          {/* Inner glow overlay */}
          <rect className="body-inner-glow" x="22" y="22" width="56" height="48" rx="12" fill="#10B981" />

          {/* Face screen */}
          <rect x="22" y="26" width="56" height="38" rx="10" fill="url(#dFaceGrad)" />

          {/* Scanline (typing mode) */}
          {isTyping && (
            <rect className="scan-line" x="22" y="26" width="56" height="3" rx="1" fill="#10B98144" />
          )}

          {/* Left Eye */}
          <g className="drone-eye-l">
            <rect x="29" y="36" width="15" height="13" rx="5" fill="#059669" />
            <circle cx="34" cy="42.5" r="3.5" fill="#E0FEF4" />
            <circle cx="35.2" cy="41.5" r="2" fill="#0F172A" />
            <circle cx="36.5" cy="40.5" r="0.8" fill="#fff" opacity="0.8" />
          </g>

          {/* Right Eye */}
          <g className="drone-eye-r">
            <rect x="56" y="36" width="15" height="13" rx="5" fill="#059669" />
            <circle cx="61" cy="42.5" r="3.5" fill="#E0FEF4" />
            <circle cx="62.2" cy="41.5" r="2" fill="#0F172A" />
            <circle cx="63.5" cy="40.5" r="0.8" fill="#fff" opacity="0.8" />
          </g>

          {/* Mouth */}
          {isTyping ? (
            /* Animated typing dots */
            <>
              <circle cx="39" cy="58" r="2.5" fill="#059669" style={{ animation: 'antennaGlow 0.6s infinite 0s' }} />
              <circle cx="50" cy="58" r="2.5" fill="#059669" style={{ animation: 'antennaGlow 0.6s infinite 0.2s' }} />
              <circle cx="61" cy="58" r="2.5" fill="#059669" style={{ animation: 'antennaGlow 0.6s infinite 0.4s' }} />
            </>
          ) : (
            <path d="M 34 58 Q 50 68 66 58" stroke="#059669" strokeWidth="3.5" strokeLinecap="round" fill="none" />
          )}

          {/* Cheek indicator lights */}
          <circle cx="22" cy="47" r="3.5" fill="#0D5C3C" />
          <circle cx="22" cy="47" r="1.8" fill="#10B981" style={{ animation: 'antennaGlow 2.5s infinite 0.5s' }} />
          <circle cx="78" cy="47" r="3.5" fill="#0D5C3C" />
          <circle cx="78" cy="47" r="1.8" fill="#10B981" style={{ animation: 'antennaGlow 2.5s infinite 0.8s' }} />

          {/* Arm struts */}
          <line x1="24" y1="70" x2="10" y2="84" stroke="#059669" strokeWidth="3" strokeLinecap="round" />
          <line x1="76" y1="70" x2="90" y2="84" stroke="#059669" strokeWidth="3" strokeLinecap="round" />

          {/* Rotors */}
          <ellipse className="rotor-l" cx="18" cy="86" rx="11" ry="3" fill="url(#dRotorGrad)" opacity="0.85" />
          <ellipse className="rotor-r" cx="82" cy="86" rx="11" ry="3" fill="url(#dRotorGrad)" opacity="0.85" />

          {/* Rotor hubs */}
          <circle cx="18" cy="86" r="2" fill="#059669" />
          <circle cx="82" cy="86" r="2" fill="#059669" />
        </svg>
      </div>
    </>
  );
}

// ════════════════════════════════════════════════════════════════
// QUICK PROMPT CHIPS
// ════════════════════════════════════════════════════════════════
const QUICK_PROMPTS = [
  { label: '🔴 Critical needs', query: '🔴 Critical needs now' },
  { label: '👥 Top volunteers', query: '👥 Top volunteers' },
  { label: '📍 Dharavi status', query: '📍 Dharavi status' },
  { label: '🌊 Flood zones', query: '🌊 Flood zones' },
];

const DEMO_RESPONSES: Record<string, string> = {
  '🔴 Critical needs now': 'We have 12 critical needs right now. Top 3: (1) Emergency Medical Camp — Dharavi, Mumbai — 2,500 affected. (2) Flood Relief — Silchar, Assam — 15,000 affected. (3) Bridge Washout — Tapovan — 800 affected.',
  '👥 Top volunteers': 'Top available volunteers: Dr. Arun Mehta (94% score, Medical, Mumbai), Priya Nair (91%, Nursing, Kerala), Anjali Krishnan (88%, Teaching, Bangalore).',
  '📍 Dharavi status': 'Dharavi Medical Camp is CRITICAL (98% urgency). 2,500 people affected. Dr. Arun Mehta is AI-matched (94% compatibility) and awaiting dispatch confirmation.',
  '🌊 Flood zones': 'Active flood zones: Silchar, Assam (CRITICAL — 15,000 affected), Barpeta, Assam (HIGH — 3,200 affected). 3 need deserts detected in NE India.',
};

// ════════════════════════════════════════════════════════════════
// CHAT PANEL
// ════════════════════════════════════════════════════════════════
export default function ChatPanel({ isOpen, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    setTimeout(() => inputRef.current?.focus(), 400);
    try {
      const ws = createChatWebSocket();
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onmessage = (e) => {
        setIsTyping(false);
        setMessages(prev => [...prev, { role: 'assistant', text: e.data }]);
      };
      return () => ws.close();
    } catch { setConnected(false); }
  }, [isOpen]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  function send(text?: string) {
    const userText = (text ?? input).trim();
    if (!userText) return;
    setMessages(prev => [...prev, { role: 'user', text: userText }]);
    setInput('');

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(userText);
    } else {
      setIsTyping(true);
      setTimeout(() => {
        const reply = DEMO_RESPONSES[userText] ??
          `In demo mode, I can tell you we have 12 active critical needs tracked across India and 156 volunteers currently available. The most critical area is Dharavi, Mumbai. Ask me for specifics!`;
        setMessages(prev => [...prev, { role: 'assistant', text: reply }]);
        setIsTyping(false);
      }, 1600);
    }
  }

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(2,10,20,0.5)', backdropFilter: 'blur(8px)', zIndex: 999 }}
      />

      {/* Panel */}
      <motion.div
        initial={{ x: '100%', opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: '100%', opacity: 0 }}
        transition={{ type: 'spring', damping: 28, stiffness: 250 }}
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0,
          width: 460, maxWidth: '100vw',
          background: 'linear-gradient(180deg, #0F1F16 0%, #0A1710 100%)',
          zIndex: 1000, display: 'flex', flexDirection: 'column',
          boxShadow: '-16px 0 48px rgba(0,0,0,0.3)',
          overflow: 'hidden',
        }}
      >
        {/* Subtle grid background */}
        <div style={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(circle at 50% 0%, rgba(16,185,129,0.12) 0%, transparent 60%)', pointerEvents: 'none' }} />

        {/* ── Header ── */}
        <div style={{ padding: '20px 24px 0', position: 'relative', zIndex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ background: 'rgba(16,185,129,0.12)', borderRadius: 20, padding: '8px 10px', border: '1px solid rgba(16,185,129,0.2)' }}>
                <SevaDrone size={56} floating isTyping={isTyping} />
              </div>
              <div>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', fontFamily: 'var(--font-heading)', letterSpacing: '-0.01em' }}>SevaBot</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: isTyping ? '#F59E0B' : connected ? '#10B981' : '#6EE7B7', display: 'inline-block', boxShadow: `0 0 6px ${isTyping ? '#F59E0B' : '#10B981'}` }} />
                  <span style={{ fontSize: 12, color: '#6EE7B7', fontWeight: 600 }}>
                    {isTyping ? 'Analyzing data…' : connected ? 'Live Connected' : 'Demo Mode'}
                  </span>
                </div>
              </div>
            </div>
            <button onClick={onClose} style={{
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10,
              color: '#94A3B8', cursor: 'pointer', width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16,
              transition: 'all 150ms',
            }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.12)'}
              onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
            >✕</button>
          </div>
          <div style={{ height: 1, background: 'linear-gradient(90deg, rgba(16,185,129,0.3), transparent)', marginTop: 20 }} />
        </div>

        {/* ── Messages ── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px 12px', position: 'relative', zIndex: 1 }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', paddingTop: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
                <SevaDrone size={110} floating />
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', marginBottom: 6, fontFamily: 'var(--font-heading)' }}>Hi, I'm SevaBot! 👋</div>
              <p style={{ fontSize: 14, color: '#6EE7B7', margin: '0 0 28px', lineHeight: 1.6 }}>
                I have live access to all needs,<br />volunteers and regional crisis data.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {QUICK_PROMPTS.map(p => (
                  <button key={p.label} onClick={() => send(p.query)} style={{
                    background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
                    borderRadius: 12, padding: '11px 14px', fontSize: 13, fontWeight: 600, color: '#A7F3D0',
                    cursor: 'pointer', textAlign: 'left', transition: 'all 150ms', lineHeight: 1.3,
                  }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'rgba(16,185,129,0.16)'; e.currentTarget.style.borderColor = 'rgba(16,185,129,0.4)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'rgba(16,185,129,0.08)'; e.currentTarget.style.borderColor = 'rgba(16,185,129,0.2)'; }}
                  >{p.label}</button>
                ))}
              </div>
            </div>
          )}

          <AnimatePresence>
            {messages.map((m, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 14, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                style={{
                  marginBottom: 16, display: 'flex',
                  flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
                  alignItems: 'flex-end', gap: 10,
                }}
              >
                {m.role === 'assistant' && (
                  <div style={{ flexShrink: 0, background: 'rgba(16,185,129,0.12)', borderRadius: 12, padding: '4px 5px', border: '1px solid rgba(16,185,129,0.2)' }}>
                    <SevaDrone size={28} />
                  </div>
                )}
                <div style={{
                  maxWidth: '76%', padding: '12px 16px', fontSize: 14, lineHeight: 1.65,
                  borderRadius: m.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                  background: m.role === 'user'
                    ? 'linear-gradient(135deg, #059669, #10B981)'
                    : 'rgba(255,255,255,0.06)',
                  color: m.role === 'user' ? '#fff' : '#E2E8F0',
                  border: m.role === 'user' ? 'none' : '1px solid rgba(255,255,255,0.08)',
                  boxShadow: m.role === 'user' ? '0 4px 16px rgba(5,150,105,0.3)' : 'none',
                }}>
                  {m.text}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isTyping && (
            <motion.div
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              style={{ display: 'flex', alignItems: 'flex-end', gap: 10, marginBottom: 16 }}
            >
              <div style={{ flexShrink: 0, background: 'rgba(16,185,129,0.12)', borderRadius: 12, padding: '4px 5px', border: '1px solid rgba(16,185,129,0.2)' }}>
                <SevaDrone size={28} isTyping />
              </div>
              <div style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px 16px 16px 4px', padding: '14px 18px', display: 'flex', gap: 5, alignItems: 'center' }}>
                {[0, 0.25, 0.5].map(delay => (
                  <span key={delay} style={{ width: 7, height: 7, borderRadius: '50%', background: '#10B981', display: 'inline-block', animation: `antennaGlow 1s ease-in-out ${delay}s infinite` }} />
                ))}
              </div>
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* ── Input ── */}
        <div style={{ padding: '16px 20px 24px', borderTop: '1px solid rgba(255,255,255,0.06)', position: 'relative', zIndex: 1 }}>
          <div style={{ display: 'flex', gap: 10, background: 'rgba(255,255,255,0.05)', borderRadius: 16, padding: '6px 6px 6px 16px', border: '1px solid rgba(16,185,129,0.2)', transition: 'border-color 200ms' }}>
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') send(); }}
              placeholder="Ask about needs, volunteers, disasters…"
              style={{ flex: 1, border: 'none', background: 'transparent', fontSize: 14, outline: 'none', color: '#E2E8F0', fontFamily: 'var(--font-body)' }}
            />
            <button
              onClick={() => send()}
              disabled={!input.trim()}
              style={{
                width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: input.trim() ? 'linear-gradient(135deg, #059669, #10B981)' : 'rgba(255,255,255,0.06)',
                color: input.trim() ? '#fff' : '#475569', border: 'none', borderRadius: 12,
                cursor: input.trim() ? 'pointer' : 'default', transition: 'all 200ms', flexShrink: 0,
                boxShadow: input.trim() ? '0 4px 12px rgba(5,150,105,0.4)' : 'none',
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
          <p style={{ fontSize: 11, color: '#334155', margin: '8px 0 0', textAlign: 'center', fontWeight: 500 }}>
            SevaBot runs in demo mode · Real AI connects to backend
          </p>
        </div>
      </motion.div>
    </>
  );
}
