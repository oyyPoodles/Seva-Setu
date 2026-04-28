'use client';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { MOCK_STATS } from '@/lib/mock-data';

function AnimatedCounter({ target, duration = 1.5 }: { target: number; duration?: number }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let start = 0;
    const end = target;
    const increment = end / (duration * 60);
    const timer = setInterval(() => {
      start += increment;
      if (start >= end) { setCount(end); clearInterval(timer); }
      else setCount(Math.floor(start));
    }, 1000 / 60);
    return () => clearInterval(timer);
  }, [target, duration]);
  return <>{count.toLocaleString('en-IN')}</>;
}

const fadeUp = { hidden: { opacity: 0, y: 24 }, visible: { opacity: 1, y: 0 } };

export default function LandingPage() {
  const stats = MOCK_STATS;
  const steps = [
    { icon: '📢', title: 'Report', desc: 'Community needs flow in from WhatsApp, Google Forms, dashboards, and field agents — in any Indian language.' },
    { icon: '🤖', title: 'Match', desc: 'Our 5-signal AI engine scores volunteers on skill fit, proximity, urgency, availability, and tag overlap.' },
    { icon: '🤝', title: 'Resolve', desc: 'Matched volunteers receive AI-generated dispatch briefs and the system learns from every outcome.' },
  ];

  return (
    <div style={{ overflow: 'hidden' }}>
      {/* ─── Hero ──────────────────────────────────── */}
      <section style={{
        maxWidth: 1320, margin: '0 auto', padding: '80px 24px 60px',
        display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
      }}>
        <motion.div initial="hidden" animate="visible" variants={fadeUp} transition={{ duration: 0.6 }}
          style={{
            display: 'inline-block', fontSize: 12, fontWeight: 600, letterSpacing: '0.12em',
            textTransform: 'uppercase', color: '#059669', background: '#ECFDF5',
            padding: '6px 16px', borderRadius: 9999, marginBottom: 24,
          }}
        >
          🌱 AI-Powered Humanitarian Coordination
        </motion.div>

        <motion.h1 initial="hidden" animate="visible" variants={fadeUp} transition={{ duration: 0.6, delay: 0.1 }}
          style={{
            fontFamily: 'var(--font-heading)', fontSize: 'clamp(36px, 5vw, 60px)', fontWeight: 700,
            color: '#1C1917', lineHeight: 1.1, margin: '0 0 20px', maxWidth: 780,
            letterSpacing: '-0.025em',
          }}
        >
          The Right Help,<br />
          <span style={{ color: '#059669' }}>Where It Matters Most</span>
        </motion.h1>

        <motion.p initial="hidden" animate="visible" variants={fadeUp} transition={{ duration: 0.6, delay: 0.2 }}
          style={{ fontSize: 18, color: '#57534E', lineHeight: 1.7, maxWidth: 600, margin: '0 0 36px' }}
        >
          SevaSetu gathers scattered community information, surfaces the most urgent needs, and intelligently matches volunteers to tasks using a multi-signal AI engine.
        </motion.p>

        <motion.div initial="hidden" animate="visible" variants={fadeUp} transition={{ duration: 0.6, delay: 0.3 }}
          style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}
        >
          <Link href="/dashboard" style={{
            background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff', padding: '14px 32px',
            borderRadius: 10, fontSize: 15, fontWeight: 600, textDecoration: 'none',
            transition: 'all 300ms', boxShadow: '0 4px 14px rgba(5, 150, 105, 0.25)',
          }}>
            Open Dashboard →
          </Link>
          <Link href="/needs/new" style={{
            border: '1.5px solid #D6D3D1', color: '#1C1917', padding: '14px 32px',
            borderRadius: 10, fontSize: 15, fontWeight: 500, textDecoration: 'none',
            background: '#fff', transition: 'all 300ms',
          }}>
            Report a Need
          </Link>
        </motion.div>
      </section>

      {/* ─── Live Stats Strip ──────────────────────── */}
      <section style={{ background: '#F8FAFC', borderTop: '1px solid #F1F5F9', borderBottom: '1px solid #F1F5F9', padding: '40px 24px' }}>
        <div style={{
          maxWidth: 1000, margin: '0 auto',
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 32, textAlign: 'center',
        }}>
          {[
            { value: stats.total_needs, label: 'Needs Tracked' },
            { value: stats.active_volunteers, label: 'Active Volunteers' },
            { value: stats.completed_assignments, label: 'Tasks Completed' },
            { value: stats.critical_needs, label: 'Critical Right Now', accent: true },
          ].map((s, i) => (
            <motion.div key={s.label} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1, duration: 0.5 }} viewport={{ once: true }}
            >
              <div style={{
                fontFamily: 'var(--font-heading)', fontSize: 42, fontWeight: 700,
                color: s.accent ? '#059669' : '#1C1917', letterSpacing: '-0.03em',
              }}>
                <AnimatedCounter target={s.value} />
              </div>
              <div style={{ fontSize: 13, color: '#78716C', marginTop: 4, fontWeight: 500 }}>{s.label}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ─── How It Works ──────────────────────────── */}
      <section style={{ maxWidth: 1000, margin: '0 auto', padding: '80px 24px' }}>
        <motion.h2 initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}
          style={{ fontFamily: 'var(--font-heading)', fontSize: 32, fontWeight: 700, textAlign: 'center', color: '#1C1917', marginBottom: 48 }}
        >
          How SevaSetu Works
        </motion.h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 32 }}>
          {steps.map((step, i) => (
            <motion.div key={step.title}
              initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.15, duration: 0.5 }} viewport={{ once: true }}
              style={{
                background: '#fff', borderRadius: 16,
                padding: 32, textAlign: 'center', position: 'relative', overflow: 'hidden',
                boxShadow: '0 4px 24px rgba(0,0,0,0.04)',
              }}
            >
              <div style={{ fontSize: 40, marginBottom: 16 }}>{step.icon}</div>
              <div style={{
                position: 'absolute', top: 12, right: 16, fontSize: 11, fontWeight: 600,
                color: '#059669', background: '#ECFDF5', padding: '2px 10px', borderRadius: 9999,
              }}>Step {i + 1}</div>
              <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: 22, fontWeight: 600, margin: '0 0 8px', color: '#1C1917' }}>{step.title}</h3>
              <p style={{ fontSize: 14, color: '#78716C', lineHeight: 1.7, margin: 0 }}>{step.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ─── Footer ────────────────────────────────── */}
      <footer style={{
        borderTop: '1px solid #E7E5E4', padding: '32px 24px', textAlign: 'center',
        fontSize: 13, color: '#A8A29E',
      }}>
        <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, color: '#1C1917' }}>🌱 SevaSetu</span>
        {' '} — Bridge of Service · Built for India&apos;s Communities
      </footer>
    </div>
  );
}
