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

/** Mascot Component */
function SevaMascot({ isTyping }: { isTyping?: boolean }) {
  return (
    <div style={{ position: 'relative', width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg viewBox="0 0 100 100" width="100%" height="100%">
        <defs>
          <linearGradient id="mascotGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#10B981" />
            <stop offset="100%" stopColor="#059669" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="45" fill="url(#mascotGrad)" />
        {/* Eyes */}
        <circle cx="35" cy="45" r="5" fill="#fff" className="mascot-eye" />
        <circle cx="65" cy="45" r="5" fill="#fff" className="mascot-eye" />
        {/* Smile */}
        <path d="M 30 65 Q 50 80 70 65" fill="none" stroke="#fff" strokeWidth="6" strokeLinecap="round" />
        {/* Leaf */}
        <path d="M 50 5 Q 65 -5 70 15 Q 55 25 50 5" fill="#A7F3D0" />
      </svg>
      {isTyping && (
        <div style={{
          position: 'absolute', top: -4, right: -4, width: 14, height: 14,
          background: '#fff', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          <span style={{ display: 'block', width: 6, height: 6, background: '#10B981', borderRadius: '50%', animation: 'pulse 1s infinite' }} />
        </div>
      )}
      <style>{`
        @keyframes pulse {
          0% { transform: scale(0.8); opacity: 0.5; }
          50% { transform: scale(1.2); opacity: 1; }
          100% { transform: scale(0.8); opacity: 0.5; }
        }
        @keyframes blink {
          0%, 96%, 98% { transform: scaleY(1); }
          97% { transform: scaleY(0.1); }
        }
        .mascot-eye {
          transform-origin: 50% 45px;
          animation: blink 4s infinite;
        }
        @keyframes slideInUp {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .msg-bubble {
          animation: slideInUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
      `}</style>
    </div>
  );
}

/** Slide-out chat panel that connects to the WebSocket RAG assistant. */
export default function ChatPanel({ isOpen, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    try {
      const ws = createChatWebSocket();
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onmessage = (e) => {
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

  function send() {
    if (!input.trim()) return;
    const userText = input;
    setMessages(prev => [...prev, { role: 'user', text: userText }]);
    setInput('');
    
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(userText);
    } else {
      // Mock response for hackathon demo
      setIsTyping(true);
      setTimeout(() => {
        setMessages(prev => [...prev, { role: 'assistant', text: `I understand you're asking about "${userText}". Since I am running in demo mode without the backend, I can tell you that we currently have 12 active needs tracked across India, and Dr. Arun Mehta is our top available volunteer.` }]);
        setIsTyping(false);
      }, 1500);
    }
  }

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.2)', backdropFilter: 'blur(4px)',
          zIndex: 999, transition: 'all 300ms',
        }}
      />
      {/* Panel */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0,
        width: 420, maxWidth: '100vw', background: '#fff',
        boxShadow: '-8px 0 32px rgba(0,0,0,0.1)',
        zIndex: 1000, display: 'flex', flexDirection: 'column',
        animation: 'slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards',
      }}>
        <style>{`
          @keyframes slideInRight {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
          }
        `}</style>

        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: '1px solid #E7E5E4',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: '#F8FAFC'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <SevaMascot isTyping={isTyping} />
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#1C1917', fontFamily: 'var(--font-heading)' }}>SevaBot Assistant</div>
              <div style={{ fontSize: 11, color: connected ? '#10B981' : '#A8A29E', marginTop: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: connected ? '#10B981' : '#A8A29E' }} />
                {connected ? 'Online' : 'Demo Mode'}
              </div>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: '#fff', border: '1px solid #E7E5E4', borderRadius: 8, fontSize: 18,
            cursor: 'pointer', color: '#78716C', width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
          }}>✕</button>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflow: 'auto', padding: '20px', background: '#fff' }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', marginTop: 40, color: '#78716C' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>👋</div>
              <p style={{ fontSize: 14, fontWeight: 500, margin: '0 0 8px' }}>Hi, I'm SevaBot!</p>
              <p style={{ fontSize: 13, color: '#A8A29E', margin: 0, lineHeight: 1.5 }}>
                Ask me about active needs,<br/>volunteer availability, or regional status.
              </p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className="msg-bubble" style={{
              marginBottom: 16,
              display: 'flex',
              justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
            }}>
              {m.role === 'assistant' && (
                <div style={{ width: 28, height: 28, marginRight: 8, flexShrink: 0 }}>
                  <SevaMascot />
                </div>
              )}
              <span style={{
                display: 'inline-block', maxWidth: '75%',
                padding: '10px 16px', borderRadius: 16,
                borderBottomRightRadius: m.role === 'user' ? 4 : 16,
                borderBottomLeftRadius: m.role === 'assistant' ? 4 : 16,
                fontSize: 14, lineHeight: 1.5,
                background: m.role === 'user' ? 'linear-gradient(135deg, #059669, #10B981)' : '#F1F5F9',
                color: m.role === 'user' ? '#fff' : '#334155',
                boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
              }}>
                {m.text}
              </span>
            </div>
          ))}
          {isTyping && (
            <div className="msg-bubble" style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
               <div style={{ width: 28, height: 28, marginRight: 8, flexShrink: 0 }}>
                  <SevaMascot isTyping />
                </div>
              <span style={{
                display: 'flex', gap: 4, padding: '12px 16px', borderRadius: 16,
                borderBottomLeftRadius: 4, background: '#F1F5F9',
              }}>
                <span style={{ width: 6, height: 6, background: '#94A3B8', borderRadius: '50%', animation: 'pulse 1s infinite 0s' }} />
                <span style={{ width: 6, height: 6, background: '#94A3B8', borderRadius: '50%', animation: 'pulse 1s infinite 0.2s' }} />
                <span style={{ width: 6, height: 6, background: '#94A3B8', borderRadius: '50%', animation: 'pulse 1s infinite 0.4s' }} />
              </span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{
          padding: '16px 20px', borderTop: '1px solid #E7E5E4',
          background: '#F8FAFC',
        }}>
          <div style={{ display: 'flex', gap: 8, background: '#fff', padding: 4, borderRadius: 12, border: '1px solid #D6D3D1', boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.02)' }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') send(); }}
              placeholder="Ask SevaBot..."
              style={{
                flex: 1, height: 40, border: 'none', background: 'transparent',
                padding: '0 12px', fontSize: 14, outline: 'none', color: '#1C1917'
              }}
            />
            <button
              onClick={send}
              style={{
                height: 40, width: 40, display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff', border: 'none',
                borderRadius: 8, cursor: 'pointer',
                transition: 'transform 200ms',
              }}
              onMouseDown={e => e.currentTarget.style.transform = 'scale(0.95)'}
              onMouseUp={e => e.currentTarget.style.transform = 'scale(1)'}
              onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
