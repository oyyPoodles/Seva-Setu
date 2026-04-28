'use client';
import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { createChatWebSocket } from '@/lib/api';

interface Props { isOpen: boolean; onClose: () => void; }
interface Message { role: 'user' | 'assistant'; text: string; }

// ═══════════════════════════════════════════════════════════════
// SEVA MASCOT – Friendly round robot face (light theme)
// ═══════════════════════════════════════════════════════════════
function SevaMascot({ size = 80, isTyping = false, idle = false }: {
  size?: number; isTyping?: boolean; idle?: boolean;
}) {
  return (
    <>
      <style>{`
        @keyframes mascotBob { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
        @keyframes mascotBlink { 0%,88%,100%{transform:scaleY(1)} 92%{transform:scaleY(0.1)} }
        @keyframes mascotGlow { 0%,100%{opacity:.5;r:3.5} 50%{opacity:1;r:5} }
        @keyframes mascotEar { 0%,100%{fill:#A7F3D0} 50%{fill:#6EE7B7} }
        @keyframes spinProp { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        @keyframes mouthWave { 0%,100%{d:path('M28 54 Q42 62 56 54')} 50%{d:path('M28 57 Q42 50 56 57')} }
        .m-bob { animation: ${idle ? 'mascotBob 2.8s ease-in-out infinite' : 'none'}; }
        .m-blink { animation: mascotBlink 4s infinite; transform-box:fill-box; transform-origin:50% 50%; }
        .m-glow { animation: mascotGlow 2s ease-in-out infinite; }
        .m-ear { animation: mascotEar 3s ease-in-out infinite; }
        .m-prop { animation: spinProp 0.3s linear infinite; transform-box:fill-box; }
        .m-prop-l { transform-origin: 12px 88px; }
        .m-prop-r { transform-origin: 72px 88px; }
      `}</style>
      <div className="m-bob" style={{ width: size, height: size, display: 'inline-block' }}>
        <svg viewBox="0 0 84 96" width={size} height={size}>
          <defs>
            <linearGradient id="mBodyG" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#34D399"/>
              <stop offset="100%" stopColor="#059669"/>
            </linearGradient>
            <linearGradient id="mFaceG" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ECFDF5"/>
              <stop offset="100%" stopColor="#D1FAE5"/>
            </linearGradient>
            <filter id="mSoft">
              <feGaussianBlur stdDeviation="1.5" result="blur"/>
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>

          {/* Propeller arm + rotor */}
          <line x1="14" y1="74" x2="6" y2="86" stroke="#059669" strokeWidth="3" strokeLinecap="round"/>
          <line x1="70" y1="74" x2="78" y2="86" stroke="#059669" strokeWidth="3" strokeLinecap="round"/>
          <ellipse className="m-prop m-prop-l" cx="12" cy="88" rx="10" ry="2.8" fill="#10B981" opacity="0.75"/>
          <ellipse className="m-prop m-prop-r" cx="72" cy="88" rx="10" ry="2.8" fill="#10B981" opacity="0.75"/>
          <circle cx="12" cy="88" r="2.2" fill="#047857"/>
          <circle cx="72" cy="88" r="2.2" fill="#047857"/>

          {/* Main body */}
          <rect x="10" y="14" width="64" height="62" rx="18" fill="url(#mBodyG)" filter="url(#mSoft)"/>
          <rect x="14" y="17" width="56" height="20" rx="10" fill="rgba(255,255,255,0.18)"/>

          {/* Face screen */}
          <rect x="14" y="20" width="56" height="46" rx="14" fill="url(#mFaceG)"/>

          {/* Ears */}
          <rect className="m-ear" x="5" y="36" width="10" height="18" rx="5"/>
          <rect className="m-ear" x="69" y="36" width="10" height="18" rx="5"/>
          <rect x="7" y="40" width="6" height="10" rx="3" fill="#059669" opacity="0.6"/>
          <rect x="71" y="40" width="6" height="10" rx="3" fill="#059669" opacity="0.6"/>

          {/* Left eye */}
          <g className="m-blink">
            <rect x="22" y="31" width="14" height="14" rx="5" fill="#059669"/>
            <circle cx="28" cy="38" r="4" fill="#ECFDF5"/>
            <circle cx="29.5" cy="36.5" r="2.2" fill="#1C1917"/>
            <circle cx="31" cy="35.5" r="0.9" fill="white" opacity="0.9"/>
          </g>

          {/* Right eye */}
          <g className="m-blink" style={{ animationDelay: '0.3s' }}>
            <rect x="48" y="31" width="14" height="14" rx="5" fill="#059669"/>
            <circle cx="54" cy="38" r="4" fill="#ECFDF5"/>
            <circle cx="55.5" cy="36.5" r="2.2" fill="#1C1917"/>
            <circle cx="57" cy="35.5" r="0.9" fill="white" opacity="0.9"/>
          </g>

          {/* Cheek blush */}
          <ellipse cx="22" cy="50" rx="6" ry="3.5" fill="#FCA5A5" opacity="0.4"/>
          <ellipse cx="62" cy="50" rx="6" ry="3.5" fill="#FCA5A5" opacity="0.4"/>

          {/* Mouth */}
          {isTyping ? (
            <g>
              <circle cx="35" cy="54" r="2.5" fill="#059669" style={{ animation: 'mascotGlow 0.5s infinite 0s' }}/>
              <circle cx="42" cy="54" r="2.5" fill="#059669" style={{ animation: 'mascotGlow 0.5s infinite 0.2s' }}/>
              <circle cx="49" cy="54" r="2.5" fill="#059669" style={{ animation: 'mascotGlow 0.5s infinite 0.4s' }}/>
            </g>
          ) : (
            <path d="M28 54 Q42 64 56 54" stroke="#059669" strokeWidth="3.5" strokeLinecap="round" fill="none"/>
          )}

          {/* Antenna */}
          <line x1="42" y1="14" x2="42" y2="5" stroke="#059669" strokeWidth="2.5" strokeLinecap="round"/>
          <circle className="m-glow" cx="42" cy="4" r="3.5" fill="#10B981"/>
        </svg>
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
const QUICK_PROMPTS = [
  { label: '🔴 Critical needs', query: '🔴 Critical needs now' },
  { label: '👥 Top volunteers', query: '👥 Top volunteers' },
  { label: '📍 Dharavi status', query: '📍 Dharavi status' },
  { label: '🌊 Flood zones', query: '🌊 Flood zones' },
];

const DEMO_RESPONSES: Record<string, string> = {
  '🔴 Critical needs now': '12 critical needs are active right now. Top 3: (1) Emergency Medical Camp — Dharavi, Mumbai — 2,500 affected. (2) Flood Relief — Silchar, Assam — 15,000 affected. (3) Bridge Washout — Tapovan, Uttarakhand — 800 affected.',
  '👥 Top volunteers': 'Top available volunteers: Dr. Arun Mehta (94%, Medical, Mumbai), Priya Nair (91%, Nursing, Kerala), Anjali Krishnan (88%, Teaching, Bangalore).',
  '📍 Dharavi status': 'Dharavi Medical Camp is CRITICAL (98% urgency). 2,500 people affected. Dr. Arun Mehta is AI-matched at 94% compatibility and awaiting dispatch confirmation.',
  '🌊 Flood zones': 'Active flood zones: Silchar, Assam (CRITICAL — 15,000 affected), Barpeta, Assam (HIGH — 3,200 affected). 3 need deserts also detected in NE India.',
};

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
    setTimeout(() => inputRef.current?.focus(), 350);
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
    const t = (text ?? input).trim();
    if (!t) return;
    setMessages(prev => [...prev, { role: 'user', text: t }]);
    setInput('');
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(t);
    } else {
      setIsTyping(true);
      setTimeout(() => {
        setMessages(prev => [...prev, { role: 'assistant', text: DEMO_RESPONSES[t] ?? `In demo mode — we have 12 critical needs and 156 active volunteers across India. The most urgent area is Dharavi, Mumbai. Ask me anything specific!` }]);
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
        style={{ position: 'fixed', inset: 0, background: 'rgba(30,41,59,0.35)', backdropFilter: 'blur(6px)', zIndex: 999 }}
      />

      {/* Panel */}
      <motion.div
        initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 260 }}
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0,
          width: 440, maxWidth: '100vw', zIndex: 1000,
          display: 'flex', flexDirection: 'column',
          background: '#FAFAFA',
          boxShadow: '-12px 0 48px rgba(0,0,0,0.1)',
          overflow: 'hidden',
        }}
      >
        {/* ── Header ── */}
        <div style={{
          background: 'linear-gradient(135deg, #059669 0%, #10B981 100%)',
          padding: '18px 20px 0',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ background: 'rgba(255,255,255,0.2)', borderRadius: 18, padding: '6px 8px' }}>
                <SevaMascot size={52} idle isTyping={isTyping} />
              </div>
              <div>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', fontFamily: 'var(--font-heading)', letterSpacing: '-0.01em' }}>SevaBot</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%', display: 'inline-block',
                    background: isTyping ? '#FDE68A' : '#A7F3D0',
                    boxShadow: `0 0 6px ${isTyping ? '#FDE68A' : '#A7F3D0'}`,
                  }} />
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.85)', fontWeight: 600 }}>
                    {isTyping ? 'Thinking…' : connected ? 'Live Connected' : 'Demo Mode'}
                  </span>
                </div>
              </div>
            </div>
            <button onClick={onClose} style={{
              background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: 10,
              color: '#fff', cursor: 'pointer', width: 34, height: 34,
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16,
              transition: 'background 150ms',
            }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.32)'}
              onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.2)'}
            >✕</button>
          </div>

          {/* Wave bottom */}
          <svg viewBox="0 0 440 24" height={24} style={{ display: 'block', width: '100%', marginTop: 8 }}>
            <path d="M0 24 C110 0 330 24 440 8 L440 24 Z" fill="#FAFAFA"/>
          </svg>
        </div>

        {/* ── Messages ── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 18px 8px' }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', paddingTop: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
                <SevaMascot size={100} idle />
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#0F172A', marginBottom: 5, fontFamily: 'var(--font-heading)' }}>
                Hi, I'm SevaBot! 👋
              </div>
              <p style={{ fontSize: 14, color: '#64748B', margin: '0 0 24px', lineHeight: 1.65 }}>
                I have live access to all needs,<br />volunteers & regional crisis data.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {QUICK_PROMPTS.map(p => (
                  <button key={p.label} onClick={() => send(p.query)} style={{
                    background: '#fff', border: '1.5px solid #E2E8F0', borderRadius: 12,
                    padding: '11px 14px', fontSize: 13, fontWeight: 600, color: '#334155',
                    cursor: 'pointer', textAlign: 'left', transition: 'all 160ms',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                  }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = '#059669'; e.currentTarget.style.color = '#059669'; e.currentTarget.style.background = '#F0FDF4'; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = '#E2E8F0'; e.currentTarget.style.color = '#334155'; e.currentTarget.style.background = '#fff'; }}
                  >{p.label}</button>
                ))}
              </div>
            </div>
          )}

          <AnimatePresence>
            {messages.map((m, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 12, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                style={{
                  marginBottom: 14,
                  display: 'flex',
                  flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
                  alignItems: 'flex-end', gap: 9,
                }}
              >
                {m.role === 'assistant' && (
                  <div style={{ flexShrink: 0, background: '#ECFDF5', borderRadius: 12, padding: '3px 4px', border: '1px solid #A7F3D0' }}>
                    <SevaMascot size={28} />
                  </div>
                )}
                <div style={{
                  maxWidth: '76%', padding: '11px 15px', fontSize: 14, lineHeight: 1.65,
                  borderRadius: m.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                  background: m.role === 'user'
                    ? 'linear-gradient(135deg, #059669, #10B981)'
                    : '#fff',
                  color: m.role === 'user' ? '#fff' : '#334155',
                  border: m.role === 'user' ? 'none' : '1px solid #F1F5F9',
                  boxShadow: m.role === 'user'
                    ? '0 4px 14px rgba(5,150,105,0.28)'
                    : '0 2px 10px rgba(0,0,0,0.05)',
                }}>
                  {m.text}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Typing indicator */}
          {isTyping && (
            <motion.div
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              style={{ display: 'flex', alignItems: 'flex-end', gap: 9, marginBottom: 14 }}
            >
              <div style={{ flexShrink: 0, background: '#ECFDF5', borderRadius: 12, padding: '3px 4px', border: '1px solid #A7F3D0' }}>
                <SevaMascot size={28} isTyping />
              </div>
              <div style={{ background: '#fff', border: '1px solid #F1F5F9', borderRadius: '16px 16px 16px 4px', padding: '12px 16px', display: 'flex', gap: 5, alignItems: 'center', boxShadow: '0 2px 10px rgba(0,0,0,0.05)' }}>
                {[0, 0.22, 0.44].map(d => (
                  <span key={d} style={{ width: 7, height: 7, borderRadius: '50%', background: '#10B981', display: 'inline-block', animation: `mascotGlow 1s ease-in-out ${d}s infinite` }} />
                ))}
              </div>
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* ── Input Bar ── */}
        <div style={{ padding: '12px 18px 20px', background: '#fff', borderTop: '1px solid #F1F5F9' }}>
          <div style={{
            display: 'flex', gap: 10, background: '#F8FAFC', borderRadius: 16,
            padding: '6px 6px 6px 16px', border: '1.5px solid #E2E8F0',
            transition: 'border-color 200ms',
          }}>
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') send(); }}
              onFocus={e => (e.target.parentElement!.style.borderColor = '#059669')}
              onBlur={e => (e.target.parentElement!.style.borderColor = '#E2E8F0')}
              placeholder="Ask about needs, volunteers, regions…"
              style={{ flex: 1, border: 'none', background: 'transparent', fontSize: 14, outline: 'none', color: '#1C1917', fontFamily: 'var(--font-body)' }}
            />
            <button
              onClick={() => send()}
              disabled={!input.trim()}
              style={{
                width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: input.trim() ? 'linear-gradient(135deg, #059669, #10B981)' : '#E2E8F0',
                color: input.trim() ? '#fff' : '#94A3B8',
                border: 'none', borderRadius: 12, cursor: input.trim() ? 'pointer' : 'default',
                transition: 'all 200ms', flexShrink: 0,
                boxShadow: input.trim() ? '0 4px 12px rgba(5,150,105,0.35)' : 'none',
              }}
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
          <p style={{ fontSize: 11, color: '#94A3B8', margin: '8px 0 0', textAlign: 'center' }}>
            SevaBot runs in demo mode · Real AI connects to backend
          </p>
        </div>
      </motion.div>
    </>
  );
}
