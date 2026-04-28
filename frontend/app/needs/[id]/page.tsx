'use client';
import { use, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import { MOCK_NEEDS, MOCK_MATCHES_N1 } from '@/lib/mock-data';
import { formatNeedType, urgencyLabel, urgencyColor, timeAgo, formatPercent, initialsFromName } from '@/lib/utils';
import { barFill } from '@/lib/animations';

const SIGNAL_LABELS: Record<string, string> = {
  skill_embedding: 'Experience Fit', skill_tags: 'Skills Match',
  geo_proximity: 'Distance', urgency: 'Urgency', availability: 'Availability',
};
const SIGNAL_ICONS: Record<string, string> = {
  skill_embedding: '🧠', skill_tags: '🏷️', geo_proximity: '📍', urgency: '⚡', availability: '📅',
};
const signals = ['skill_embedding', 'skill_tags', 'geo_proximity', 'urgency', 'availability'] as const;

const TYPE_ICONS: Record<string, string> = {
  HEALTHCARE: '🏥', EDUCATION: '📚', WATER_SANITATION: '💧',
  SHELTER: '🏠', FOOD: '🌾', INFRASTRUCTURE: '🏗️', LIVELIHOOD: '💼',
};

const stagger = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08 } }
};
const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } }
};

export default function NeedDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const need = MOCK_NEEDS.find(n => n.id === id);
  const matches = id === 'n1' ? MOCK_MATCHES_N1 : [];

  const [assigned, setAssigned] = useState<Record<string, boolean>>({});
  const [expandedBrief, setExpandedBrief] = useState<Record<string, boolean>>({});
  const [validating, setValidating] = useState<string | null>(null);
  const [validated, setValidated] = useState<Record<string, boolean>>({});

  if (!need) return (
    <div style={{ minHeight: 'calc(100vh - 56px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 64, marginBottom: 16 }}>🔍</div>
        <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 28, color: '#0F172A', margin: '0 0 8px' }}>Need Not Found</h1>
        <p style={{ color: '#64748B', margin: '0 0 24px' }}>This need may have been resolved or removed.</p>
        <Link href="/needs" style={{ background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff', padding: '12px 24px', borderRadius: 12, fontWeight: 700, textDecoration: 'none', fontSize: 14 }}>← Back to Needs</Link>
      </div>
    </div>
  );

  const urg = need.urgency_current ?? need.urgency_base;
  const urgColor = urgencyColor(urg);
  const icon = TYPE_ICONS[need.need_type ?? ''] ?? '📌';

  function handleValidate(vid: string) {
    setValidating(vid);
    setTimeout(() => { setValidated(p => ({ ...p, [vid]: true })); setValidating(null); }, 2000);
  }

  return (
    <div style={{ minHeight: 'calc(100vh - 56px)', background: 'linear-gradient(180deg, #F8FAFC 0%, #fff 400px)' }}>
      <div style={{ maxWidth: 1120, margin: '0 auto', padding: '32px 24px 80px' }}>
        
        {/* Back */}
        <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3 }}>
          <Link href="/needs" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, color: '#64748B', textDecoration: 'none', marginBottom: 24, padding: '8px 14px', background: '#fff', borderRadius: 10, border: '1px solid #E2E8F0', transition: 'all 200ms' }}
            onMouseEnter={e => { e.currentTarget.style.background = '#F0FDF4'; e.currentTarget.style.color = '#059669'; }}
            onMouseLeave={e => { e.currentTarget.style.background = '#fff'; e.currentTarget.style.color = '#64748B'; }}
          >
            ← Back to Needs
          </Link>
        </motion.div>

        <motion.div variants={stagger} initial="hidden" animate="visible">

          {/* ─── Need Header Card ─── */}
          <motion.div variants={fadeUp} style={{
            background: '#fff', borderRadius: 24, overflow: 'hidden',
            boxShadow: '0 8px 40px rgba(0,0,0,0.06)', marginBottom: 28,
            border: '1px solid #F1F5F9',
          }}>
            {/* Urgency gradient header bar */}
            <div style={{ height: 6, background: `linear-gradient(90deg, ${urgColor}, ${urgColor}88)` }} />
            
            <div style={{ padding: '32px 36px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 24, flexWrap: 'wrap' }}>
                <div style={{ flex: 1 }}>
                  {/* Tags */}
                  <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 12, fontWeight: 700, padding: '5px 14px', borderRadius: 999, background: '#F0FDF4', color: '#059669', display: 'flex', alignItems: 'center', gap: 5 }}>
                      {icon} {formatNeedType(need.need_type)}
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 700, padding: '5px 14px', borderRadius: 999, background: urgColor + '18', color: urgColor }}>
                      {urgencyLabel(urg)} ({Math.round(urg * 100)}%)
                    </span>
                    <span style={{ fontSize: 11, fontWeight: 700, padding: '5px 14px', borderRadius: 999, background: '#F8FAFC', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      {need.status?.replace(/_/g, ' ')}
                    </span>
                  </div>
                  
                  <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 30, fontWeight: 800, margin: '0 0 12px', color: '#0F172A', letterSpacing: '-0.02em', lineHeight: 1.3 }}>
                    {need.title}
                  </h1>
                  <p style={{ fontSize: 15, color: '#475569', lineHeight: 1.75, margin: '0 0 24px', maxWidth: 680 }}>
                    {need.description}
                  </p>

                  {/* Meta info pills */}
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {[
                      { icon: '📍', text: need.location_name },
                      { icon: '👥', text: `${need.affected_count?.toLocaleString()} affected` },
                      { icon: '🕐', text: timeAgo(need.created_at) },
                      { icon: '📱', text: `via ${need.source_channel}` },
                    ].filter(m => m.text).map(m => (
                      <span key={m.text} style={{ fontSize: 13, fontWeight: 500, color: '#475569', background: '#F8FAFC', border: '1px solid #E2E8F0', padding: '6px 14px', borderRadius: 999, display: 'flex', alignItems: 'center', gap: 5 }}>
                        {m.icon} {m.text}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Urgency meter */}
                <div style={{ textAlign: 'center', background: '#F8FAFC', borderRadius: 18, padding: '20px 28px', border: '1px solid #E2E8F0', flexShrink: 0 }}>
                  <div style={{ fontSize: 42, fontWeight: 800, color: urgColor, fontFamily: 'var(--font-heading)', lineHeight: 1 }}>{Math.round(urg * 100)}%</div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: 4 }}>Urgency</div>
                </div>
              </div>

              {/* Skills row */}
              {need.required_skills.length > 0 && (
                <div style={{ marginTop: 20, paddingTop: 20, borderTop: '1px solid #F1F5F9', display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Skills needed:</span>
                  {need.required_skills.map(s => (
                    <span key={s} style={{ fontSize: 12, fontWeight: 600, padding: '5px 12px', borderRadius: 999, background: '#EFF6FF', color: '#2563EB' }}>
                      {s.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </motion.div>

          {/* ─── AI Matches Header ─── */}
          <motion.div variants={fadeUp} style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
            <div>
              <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: 26, fontWeight: 800, margin: '0 0 6px', color: '#0F172A', letterSpacing: '-0.01em' }}>
                🤖 AI-Matched Volunteers
              </h2>
              <p style={{ fontSize: 14, color: '#64748B', margin: 0 }}>
                5-signal scoring: experience fit · skills · geo-proximity · urgency · availability
              </p>
            </div>
            {matches.length > 0 && (
              <div style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: 12, padding: '8px 16px', fontSize: 13, fontWeight: 700, color: '#059669' }}>
                {matches.length} matches found
              </div>
            )}
          </motion.div>

          {/* ─── No Matches State ─── */}
          {matches.length === 0 ? (
            <motion.div variants={fadeUp} style={{ background: '#fff', borderRadius: 20, padding: '56px 32px', textAlign: 'center', border: '2px dashed #E2E8F0', boxShadow: '0 4px 16px rgba(0,0,0,0.03)' }}>
              <div style={{ fontSize: 56, marginBottom: 16 }}>🤖</div>
              <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: 20, fontWeight: 700, margin: '0 0 8px', color: '#0F172A' }}>No matches computed yet</h3>
              <p style={{ fontSize: 15, color: '#64748B', margin: '0 0 24px' }}>Visit the demo need to see a full AI matching flow in action.</p>
              <Link href="/needs/n1" style={{ background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff', padding: '12px 28px', borderRadius: 12, fontWeight: 700, textDecoration: 'none', fontSize: 14, boxShadow: '0 4px 16px rgba(5,150,105,0.3)' }}>
                View Demo Matches →
              </Link>
            </motion.div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {matches.map((match, mi) => {
                const { volunteer, score, llm_analysis, dispatch_brief, llm_validated } = match;
                const bd = score!;
                const total = bd.total ?? 0;
                const isValidated = llm_validated || validated[volunteer.id];
                const analysis = llm_analysis;
                const validation = analysis?.validation;
                const valStyles: Record<string, { bg: string; border: string; text: string; badge: string }> = {
                  Valid: { bg: '#F0FDF4', border: '#86EFAC', text: '#15803D', badge: '✓ Valid Match' },
                  Weak:  { bg: '#FFFBEB', border: '#FDE68A', text: '#B45309', badge: '⚠ Weak Match' },
                  Poor:  { bg: '#FEF2F2', border: '#FECACA', text: '#DC2626', badge: '✗ Poor Match' },
                };
                const vs = validation ? valStyles[validation] : null;
                const rankColors = ['linear-gradient(135deg, #F59E0B, #F97316)', 'linear-gradient(135deg, #94A3B8, #64748B)', 'linear-gradient(135deg, #C084FC, #A855F7)'];
                const rankLabels = ['#1 Best Match', '#2 Match', '#3 Match'];

                return (
                  <motion.div
                    key={volunteer.id}
                    variants={fadeUp}
                    style={{
                      background: '#fff', borderRadius: 20, overflow: 'hidden',
                      boxShadow: '0 4px 24px rgba(0,0,0,0.05)',
                      border: `1px solid ${isValidated && vs ? vs.border : '#F1F5F9'}`,
                      transition: 'border-color 400ms',
                    }}
                  >
                    {/* Rank banner */}
                    <div style={{ height: 4, background: rankColors[mi] || '#E2E8F0' }} />
                    
                    <div style={{ padding: '24px 28px' }}>
                      {/* Volunteer Header */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
                        <div style={{ position: 'relative' }}>
                          <div style={{
                            width: 56, height: 56, borderRadius: 16,
                            background: rankColors[mi] || 'linear-gradient(135deg, #059669, #10B981)',
                            color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 18, fontWeight: 700, flexShrink: 0,
                            boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                          }}>
                            {initialsFromName(volunteer.name)}
                          </div>
                          <div style={{ position: 'absolute', bottom: -4, right: -4, background: '#fff', borderRadius: 6, padding: '1px 5px', fontSize: 9, fontWeight: 700, color: '#475569', border: '1px solid #E2E8F0' }}>
                            {rankLabels[mi]}
                          </div>
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 18, fontWeight: 700, color: '#0F172A', marginBottom: 3 }}>{volunteer.name}</div>
                          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            {volunteer.skills.slice(0, 4).map(s => (
                              <span key={s} style={{ fontSize: 11, fontWeight: 600, background: '#F8FAFC', color: '#475569', padding: '2px 8px', borderRadius: 999, border: '1px solid #E2E8F0' }}>{s.replace(/_/g, ' ')}</span>
                            ))}
                            {volunteer.has_vehicle && <span style={{ fontSize: 11, fontWeight: 600, background: '#EFF6FF', color: '#2563EB', padding: '2px 8px', borderRadius: 999 }}>🚗 Has Vehicle</span>}
                          </div>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                          <div style={{ fontFamily: 'var(--font-heading)', fontSize: 40, fontWeight: 800, color: total > 0.8 ? '#059669' : total > 0.6 ? '#D97706' : '#94A3B8', lineHeight: 1 }}>
                            {formatPercent(total)}
                          </div>
                          <div style={{ fontSize: 10, fontWeight: 600, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Match Score</div>
                          {vs && (
                            <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 12px', borderRadius: 999, background: vs.bg, color: vs.text, border: `1px solid ${vs.border}` }}>
                              {vs.badge}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* 5-Signal Bars */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px 28px', marginBottom: 20 }}>
                        {signals.map((key, i) => {
                          const val = bd[key] ?? 0;
                          const barColor = val > 0.7 ? '#059669' : val > 0.4 ? '#D97706' : '#EF4444';
                          return (
                            <div key={key}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, alignItems: 'center' }}>
                                <span style={{ fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#94A3B8', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
                                  {SIGNAL_ICONS[key]} {SIGNAL_LABELS[key]}
                                </span>
                                <span style={{ fontSize: 14, fontWeight: 700, color: barColor }}>{formatPercent(val)}</span>
                              </div>
                              <div style={{ height: 8, background: '#F1F5F9', borderRadius: 999, overflow: 'hidden' }}>
                                <motion.div
                                  style={{ height: '100%', background: `linear-gradient(90deg, ${barColor}88, ${barColor})`, borderRadius: 999 }}
                                  {...barFill(val, mi * 0.1 + i * 0.06)}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* AI Verdict */}
                      <AnimatePresence>
                        {isValidated && analysis?.overall_rationale && vs && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            transition={{ duration: 0.4 }}
                            style={{ background: vs.bg, border: `1px solid ${vs.border}`, borderRadius: 14, padding: '16px 20px', marginBottom: 16, overflow: 'hidden' }}
                          >
                            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: vs.text, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                              🤖 AI Verdict
                            </div>
                            <p style={{ fontSize: 14, color: '#334155', margin: 0, lineHeight: 1.7 }}>
                              {analysis.overall_rationale}
                            </p>
                            {analysis.signal_explanations && (
                              <details style={{ marginTop: 10 }}>
                                <summary style={{ fontSize: 12, color: '#64748B', cursor: 'pointer', fontWeight: 600 }}>See per-signal reasoning</summary>
                                <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
                                  {signals.map(k => analysis.signal_explanations?.[k] && (
                                    <div key={k} style={{ fontSize: 12, color: '#475569', lineHeight: 1.6 }}>
                                      <strong style={{ color: '#334155' }}>{SIGNAL_ICONS[k]} {SIGNAL_LABELS[k]}:</strong> {String(analysis.signal_explanations[k])}
                                    </div>
                                  ))}
                                </div>
                              </details>
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>

                      {/* Dispatch Brief */}
                      <AnimatePresence>
                        {dispatch_brief && expandedBrief[volunteer.id] && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            style={{ borderLeft: '3px solid #059669', paddingLeft: 16, margin: '0 0 16px', overflow: 'hidden' }}
                          >
                            <p style={{ fontStyle: 'italic', fontSize: 14, color: '#334155', lineHeight: 1.75, margin: 0 }}>{dispatch_brief}</p>
                          </motion.div>
                        )}
                      </AnimatePresence>

                      {dispatch_brief && (
                        <button
                          onClick={() => setExpandedBrief(p => ({ ...p, [volunteer.id]: !p[volunteer.id] }))}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 700, color: '#059669', padding: '0 0 14px', display: 'flex', alignItems: 'center', gap: 4 }}
                        >
                          {expandedBrief[volunteer.id] ? '▲ Hide' : '▼ Show'} Dispatch Brief
                        </button>
                      )}

                      {/* Action Buttons */}
                      <div style={{ display: 'flex', gap: 10 }}>
                        {!isValidated && (
                          <motion.button
                            whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}
                            onClick={() => handleValidate(volunteer.id)}
                            disabled={validating === volunteer.id}
                            style={{
                              flex: 1, padding: '14px 0',
                              background: validating === volunteer.id ? '#E2E8F0' : 'linear-gradient(135deg, #7C3AED, #6D28D9)',
                              color: validating === volunteer.id ? '#94A3B8' : '#fff',
                              border: 'none', borderRadius: 12, fontSize: 14, fontWeight: 700,
                              cursor: validating === volunteer.id ? 'default' : 'pointer',
                              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                              boxShadow: validating !== volunteer.id ? '0 4px 16px rgba(124,58,237,0.3)' : 'none',
                              transition: 'all 300ms',
                            }}
                          >
                            {validating === volunteer.id ? (
                              <>
                                <span style={{ display: 'inline-block', width: 14, height: 14, border: '2px solid rgba(0,0,0,0.1)', borderTopColor: '#64748B', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                                Validating with AI…
                              </>
                            ) : '🤖 Validate with AI'}
                          </motion.button>
                        )}
                        <motion.button
                          whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}
                          onClick={() => setAssigned(p => ({ ...p, [volunteer.id]: true }))}
                          disabled={assigned[volunteer.id]}
                          style={{
                            flex: 1, padding: '14px 0',
                            background: assigned[volunteer.id] ? '#15803D' : 'linear-gradient(135deg, #059669, #10B981)',
                            color: '#fff', border: 'none', borderRadius: 12, fontSize: 14, fontWeight: 700,
                            cursor: assigned[volunteer.id] ? 'default' : 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                            boxShadow: !assigned[volunteer.id] ? '0 4px 16px rgba(5,150,105,0.3)' : 'none',
                            transition: 'all 300ms',
                          }}
                        >
                          {assigned[volunteer.id] ? '✓ Assigned!' : 'Assign Volunteer'}
                        </motion.button>
                      </div>
                    </div>
                    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                  </motion.div>
                );
              })}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
