'use client';
import { useState, useEffect, useRef } from 'react';
import { createChatWebSocket } from '@/lib/api';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

interface Message {
  role: 'user' | 'assistant';
  text: string;
}

// ── SevaDrone Mascot (Proper animated SVG robot) ────────────────
function SevaDrone({ size = 64, isTyping = false, idle = false }: { size?: number; isTyping?: boolean; idle?: boolean }) {
  return (
    <div style={{
      width: size, height: size, position: 'relative',
      animation: idle ? 'droneFloat 3s ease-in-out infinite' : undefined,
      display: 'inline-block',
    }}>
      <style>{`
        @keyframes droneFloat {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-6px); }
        }
        @keyframes droneBlink {
          0%, 92%, 96% { transform: scaleY(1); }
          94% { transform: scaleY(0.1); }
        }
        @keyframes droneGlow {
          0%, 100% { opacity: 0.4; r: 3; }
          50% { opacity: 1; r: 5; }
        }
        @keyframes droneSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes droneTypePulse {
          0%, 100% { fill: #10B981; }
          50% { fill: #059669; }
        }
        .drone-eye { animation: droneBlink 4s infinite; transform-box: fill-box; transform-origin: center; }
        .drone-glow { animation: droneGlow 2s ease-in-out infinite; }
        .drone-antenna { animation: droneGlow 1.5s ease-in-out infinite; }
        .drone-typing { animation: droneTypePulse 0.8s ease-in-out infinite; }
      `}</style>
      <svg viewBox="0 0 100 100" width={size} height={size} fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bodyGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10B981"/>
            <stop offset="100%" stopColor="#059669"/>
          </linearGradient>
          <linearGradient id="faceGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ECFDF5"/>
            <stop offset="100%" stopColor="#D1FAE5"/>
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        {/* Antenna */}
        <line x1="50" y1="6" x2="50" y2="16" stroke="#059669" strokeWidth="2.5" strokeLinecap="round"/>
        <circle cx="50" cy="5" r="3.5" fill={isTyping ? undefined : "#10B981"} filter="url(#glow)"
          className={isTyping ? 'drone-typing drone-antenna' : 'drone-antenna'}
        />

        {/* Body */}
        <rect x="20" y="22" width="60" height="52" rx="16" fill="url(#bodyGrad)" />
        
        {/* Body highlight */}
        <rect x="24" y="24" width="52" height="20" rx="10" fill="rgba(255,255,255,0.15)" />

        {/* Face screen */}
        <rect x="24" y="30" width="52" height="34" rx="10" fill="url(#faceGrad)" />

        {/* Eyes */}
        <g className="drone-eye">
          <rect x="31" y="38" width="14" height="12" rx="4" fill="#059669" />
          <circle cx="36" cy="44" r="3" fill="#ECFDF5" />
          <circle cx="37" cy="43" r="1.5" fill="#1C1917" />
        </g>
        <g className="drone-eye">
          <rect x="55" y="38" width="14" height="12" rx="4" fill="#059669" />
          <circle cx="60" cy="44" r="3" fill="#ECFDF5" />
          <circle cx="61" cy="43" r="1.5" fill="#1C1917" />
        </g>

        {/* Mouth */}
        {isTyping ? (
          /* Thinking dots */
          <g>
            <circle cx="40" cy="58" r="2.5" fill="#059669" style={{ animation: 'droneGlow 0.6s infinite 0s' }} />
            <circle cx="50" cy="58" r="2.5" fill="#059669" style={{ animation: 'droneGlow 0.6s infinite 0.2s' }} />
            <circle cx="60" cy="58" r="2.5" fill="#059669" style={{ animation: 'droneGlow 0.6s infinite 0.4s' }} />
          </g>
        ) : (
          <path d="M 36 57 Q 50 66 64 57" stroke="#10B981" strokeWidth="3" strokeLinecap="round" />
        )}

        {/* Ear bolts */}
        <circle cx="20" cy="46" r="4" fill="#047857" />
        <circle cx="80" cy="46" r="4" fill="#047857" />
        <circle cx="20" cy="46" r="2" fill="#10B981" />
        <circle cx="80" cy="46" r="2" fill="#10B981" />

        {/* Propeller arms */}
        <line x1="20" y1="72" x2="8" y2="82" stroke="#059669" strokeWidth="3" strokeLinecap="round"/>
        <line x1="80" y1="72" x2="92" y2="82" stroke="#059669" strokeWidth="3" strokeLinecap="round"/>

        {/* Propeller rotors */}
        <ellipse cx="8" cy="84" rx="7" ry="2.5" fill="#10B981" opacity="0.7" style={{ transformOrigin: '8px 84px', animation: 'droneSpin 0.4s linear infinite' }} />
        <ellipse cx="92" cy="84" rx="7" ry="2.5" fill="#10B981" opacity="0.7" style={{ transformOrigin: '92px 84px', animation: 'droneSpin 0.4s linear infinite reverse' }} />
      </svg>
    </div>
  );
}

// ── QUICK PROMPTS ───────────────────────────────────────────────
const QUICK_PROMPTS = [
  '🔴 Critical needs now',
  '👥 Top volunteers',
  '📍 Dharavi status',
  '🌊 Flood zones',
];

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
    setTimeout(() => inputRef.current?.focus(), 300);
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
    } catch {
      setConnected(false);
    }
  }, [isOpen]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  function send(text?: string) {
    const userText = text ?? input;
    if (!userText.trim()) return;
    setMessages(prev => [...prev, { role: 'user', text: userText }]);
    setInput('');

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(userText);
    } else {
      setIsTyping(true);
      setTimeout(() => {
        const demoResponses: Record<string, string> = {
          '🔴 Critical needs now': 'There are 12 critical needs right now. The top 3 are: (1) Emergency Medical Camp — Dharavi, Mumbai — 2,500 affected. (2) Flood Relief — Silchar, Assam — 15,000 affected. (3) Bridge Washout — Tapovan — 800 affected.',
          '👥 Top volunteers': 'Our top available volunteers are Dr. Arun Mehta (Score: 94%, Medical), Priya Krishnamurthy (Score: 88%, Logistics), and Ramesh Patel (Score: 82%, Engineering).',
          '📍 Dharavi status': 'Dharavi Medical Camp is at CRITICAL urgency (98%). 2,500 people are affected. Dr. Arun Mehta has been AI-matched with a 94% compatibility score. Awaiting dispatch confirmation.',
          '🌊 Flood zones': 'Active flood zones: Silchar, Assam (HIGH - 15,000 affected), Barpeta, Assam (MODERATE - 3,200 affected). 3 need deserts also detected in the northeast region.',
        };
        const reply = demoResponses[userText] || `I understand you're asking about "${userText}". In demo mode, I can confirm we have 12 active needs across India and 156 volunteers currently active. The most critical area is Dharavi, Mumbai.`;
        setMessages(prev => [...prev, { role: 'assistant', text: reply }]);
        setIsTyping(false);
      }, 1800);
    }
  }

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.4)', backdropFilter: 'blur(6px)', zIndex: 999 }}
      />

      {/* Panel */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0,
        width: 440, maxWidth: '100vw',
        background: '#F8FAFC',
        boxShadow: '-12px 0 40px rgba(0,0,0,0.15)',
        zIndex: 1000, display: 'flex', flexDirection: 'column',
        animation: 'chatSlideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards',
      }}>
        <style>{`
          @keyframes chatSlideIn {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
          }
          @keyframes msgPop {
            from { opacity: 0; transform: translateY(12px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
          }
        `}</style>

        {/* Header */}
        <div style={{
          padding: '20px 24px', background: 'linear-gradient(135deg, #059669, #10B981)',
          display: 'flex', alignItems: 'center', gap: 16,
          boxShadow: '0 4px 16px rgba(5, 150, 105, 0.3)',
        }}>
          <div style={{ flexShrink: 0, background: 'rgba(255,255,255,0.15)', borderRadius: 16, padding: 6 }}>
            <SevaDrone size={52} idle isTyping={isTyping} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#fff', fontFamily: 'var(--font-heading)', letterSpacing: '-0.01em' }}>SevaBot</div>
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.8)', marginTop: 2, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: connected ? '#A7F3D0' : 'rgba(255,255,255,0.5)', display: 'inline-block' }} />
              {isTyping ? 'Analyzing needs data…' : connected ? 'Live — Backend Connected' : 'Demo Mode Active'}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: 10, fontSize: 18,
            cursor: 'pointer', color: '#fff', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>✕</button>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px 20px' }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center' }}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
                <SevaDrone size={90} idle />
              </div>
              <p style={{ fontSize: 18, fontWeight: 700, margin: '0 0 4px', color: '#1C1917', fontFamily: 'var(--font-heading)' }}>Hi, I'm SevaBot! 👋</p>
              <p style={{ fontSize: 13, color: '#64748B', margin: '0 0 24px', lineHeight: 1.6 }}>
                I have live access to all needs,<br/>volunteers and regional data.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {QUICK_PROMPTS.map(p => (
                  <button key={p} onClick={() => send(p)} style={{
                    background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12,
                    padding: '10px 12px', fontSize: 12, fontWeight: 600, color: '#475569',
                    cursor: 'pointer', textAlign: 'left', transition: 'all 150ms',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
                  }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = '#059669'; e.currentTarget.style.color = '#059669'; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = '#E2E8F0'; e.currentTarget.style.color = '#475569'; }}
                  >{p}</button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} style={{
              marginBottom: 16,
              display: 'flex', flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
              alignItems: 'flex-end', gap: 10,
              animation: 'msgPop 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards'
            }}>
              {m.role === 'assistant' && (
                <div style={{ flexShrink: 0, background: 'linear-gradient(135deg, #059669, #10B981)', borderRadius: 12, padding: 4 }}>
                  <SevaDrone size={28} />
                </div>
              )}
              <div style={{
                maxWidth: '75%', padding: '12px 16px', borderRadius: 18,
                borderBottomRightRadius: m.role === 'user' ? 4 : 18,
                borderBottomLeftRadius: m.role === 'assistant' ? 4 : 18,
                fontSize: 14, lineHeight: 1.6,
                background: m.role === 'user'
                  ? 'linear-gradient(135deg, #059669, #10B981)'
                  : '#fff',
                color: m.role === 'user' ? '#fff' : '#334155',
                boxShadow: m.role === 'user'
                  ? '0 4px 12px rgba(5,150,105,0.3)'
                  : '0 2px 12px rgba(0,0,0,0.06)',
              }}>
                {m.text}
              </div>
            </div>
          ))}

          {isTyping && (
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, marginBottom: 16, animation: 'msgPop 0.3s forwards' }}>
              <div style={{ flexShrink: 0, background: 'linear-gradient(135deg, #059669, #10B981)', borderRadius: 12, padding: 4 }}>
                <SevaDrone size={28} isTyping />
              </div>
              <div style={{ background: '#fff', borderRadius: '18px 18px 18px 4px', padding: '14px 18px', boxShadow: '0 2px 12px rgba(0,0,0,0.06)', display: 'flex', gap: 5, alignItems: 'center' }}>
                {[0, 0.2, 0.4].map(delay => (
                  <span key={delay} style={{ width: 7, height: 7, borderRadius: '50%', background: '#10B981', display: 'inline-block', animation: `droneGlow 1s ease-in-out ${delay}s infinite` }} />
                ))}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{ padding: '16px 20px 24px', background: '#fff', borderTop: '1px solid #E2E8F0' }}>
          <div style={{ display: 'flex', gap: 10, background: '#F8FAFC', borderRadius: 16, padding: '6px 6px 6px 16px', border: '2px solid #E2E8F0', transition: 'border-color 200ms' }}
            onFocus={() => { }} // visual only
          >
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') send(); }}
              placeholder="Ask about needs, volunteers, regions…"
              style={{ flex: 1, border: 'none', background: 'transparent', fontSize: 14, outline: 'none', color: '#1C1917', fontFamily: 'var(--font-body)' }}
            />
            <button
              onClick={() => send()}
              disabled={!input.trim()}
              style={{
                width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: input.trim() ? 'linear-gradient(135deg, #059669, #10B981)' : '#E2E8F0',
                color: '#fff', border: 'none', borderRadius: 12, cursor: input.trim() ? 'pointer' : 'default',
                transition: 'all 200ms', flexShrink: 0,
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
          <p style={{ fontSize: 11, color: '#94A3B8', margin: '8px 0 0', textAlign: 'center' }}>SevaBot is in demo mode — real AI connects to the backend</p>
        </div>
      </div>
    </>
  );
}
