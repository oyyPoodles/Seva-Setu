'use client';
import { use, useState } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { MOCK_NEEDS, MOCK_MATCHES_N1 } from '@/lib/mock-data';
import { formatNeedType, urgencyLabel, urgencyColor, timeAgo, formatPercent, initialsFromName } from '@/lib/utils';
import { barFill } from '@/lib/animations';

const SIGNAL_LABELS: Record<string, string> = {
  skill_embedding: 'Experience Fit', skill_tags: 'Skills Match',
  geo_proximity: 'Distance', urgency: 'Urgency', availability: 'Availability',
};
const signals = ['skill_embedding', 'skill_tags', 'geo_proximity', 'urgency', 'availability'] as const;

export default function NeedDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const need = MOCK_NEEDS.find(n => n.id === id);
  const matches = id === 'n1' ? MOCK_MATCHES_N1 : [];

  const [assigned, setAssigned] = useState<Record<string, boolean>>({});
  const [expandedBrief, setExpandedBrief] = useState<Record<string, boolean>>({});
  const [validating, setValidating] = useState<string | null>(null);
  const [validated, setValidated] = useState<Record<string, boolean>>({});

  if (!need) return (
    <div style={{ maxWidth: 600, margin: '80px auto', textAlign: 'center' }}>
      <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 28, color: '#1C1917' }}>Need Not Found</h1>
      <p style={{ color: '#78716C' }}>This need may have been resolved.</p>
      <Link href="/needs" style={{ color: '#059669', fontWeight: 500 }}>← Back to Needs</Link>
    </div>
  );

  const urg = need.urgency_current ?? need.urgency_base;

  function handleValidate(vid: string) {
    setValidating(vid);
    setTimeout(() => { setValidated(p => ({ ...p, [vid]: true })); setValidating(null); }, 2000);
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.35 }}
      style={{ maxWidth: 1320, margin: '0 auto', padding: '32px 24px 64px' }}
    >
      <Link href="/needs" style={{ fontSize: 13, color: '#78716C', textDecoration: 'none', marginBottom: 20, display: 'inline-block' }}>← Back to Needs</Link>

      {/* Need Header */}
      <div style={{ border: '1px solid #E7E5E4', borderRadius: 16, padding: 28, background: '#fff', marginBottom: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 9999, background: '#ECFDF5', color: '#059669', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {formatNeedType(need.need_type)}
              </span>
              <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 9999, background: urgencyColor(urg) + '18', color: urgencyColor(urg) }}>
                {urgencyLabel(urg)} ({Math.round(urg * 100)}%)
              </span>
              <span style={{ fontSize: 11, fontWeight: 500, padding: '3px 10px', borderRadius: 9999, background: '#F5F5F4', color: '#78716C', textTransform: 'uppercase' }}>
                {need.status}
              </span>
            </div>
            <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 26, fontWeight: 700, margin: '0 0 8px', color: '#1C1917' }}>{need.title}</h1>
            <p style={{ fontSize: 15, color: '#57534E', lineHeight: 1.7, margin: '0 0 16px' }}>{need.description}</p>
            <div style={{ display: 'flex', gap: 20, fontSize: 13, color: '#78716C', flexWrap: 'wrap' }}>
              <span>📍 {need.location_name}</span>
              <span>👥 {need.affected_count} affected</span>
              <span>🕐 {timeAgo(need.created_at)}</span>
              <span>📱 via {need.source_channel}</span>
            </div>
          </div>
        </div>
        {need.required_skills.length > 0 && (
          <div style={{ marginTop: 16, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: '#A8A29E', alignSelf: 'center' }}>Skills needed:</span>
            {need.required_skills.map(s => (
              <span key={s} style={{ fontSize: 12, padding: '3px 10px', borderRadius: 9999, background: '#F5F5F4', color: '#44403C' }}>
                {s.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Volunteer Matches Section */}
      <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: 22, fontWeight: 700, margin: '0 0 6px', color: '#1C1917' }}>
        🤖 AI-Matched Volunteers
      </h2>
      <p style={{ fontSize: 14, color: '#78716C', margin: '0 0 20px' }}>
        5-signal scoring: skill embedding · tag overlap · geo-proximity · urgency · availability
      </p>

      {matches.length === 0 ? (
        <div style={{ border: '1px dashed #D6D3D1', borderRadius: 14, padding: '48px 24px', textAlign: 'center', background: '#F8FAFC' }}>
          <p style={{ fontSize: 15, color: '#78716C' }}>No matches computed yet. Visit <strong>need n1</strong> to see a full matching demo.</p>
          <Link href="/needs/n1" style={{ color: '#059669', fontWeight: 500, fontSize: 14 }}>View demo matches →</Link>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {matches.map((match, mi) => {
            const { volunteer, score, llm_analysis, dispatch_brief, llm_validated } = match;
            const bd = score!;
            const total = bd.total ?? 0;
            const isValidated = llm_validated || validated[volunteer.id];
            const analysis = llm_analysis;
            const validation = analysis?.validation;
            const valColors: Record<string, { bg: string; text: string; label: string }> = {
              Valid: { bg: '#F0FDF4', text: '#16A34A', label: '✓ Valid Match' },
              Weak:  { bg: '#FFFBEB', text: '#B45309', label: '⚠ Weak Match' },
              Poor:  { bg: '#FEF2F2', text: '#DC2626', label: '✗ Poor Match' },
            };

            return (
              <motion.div key={volunteer.id}
                initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: mi * 0.12, duration: 0.4 }}
                style={{ border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,0.04)', borderRadius: 16, padding: 24, background: '#fff' }}
              >
                {/* Volunteer header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: '50%', background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 16, fontWeight: 600, flexShrink: 0,
                  }}>{initialsFromName(volunteer.name)}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 17, fontWeight: 600, color: '#1C1917' }}>{volunteer.name}</div>
                    <div style={{ fontSize: 13, color: '#78716C', marginTop: 2 }}>
                      {volunteer.skills.slice(0, 4).map(s => s.replace(/_/g, ' ')).join(' · ')}
                      {volunteer.has_vehicle && ' · 🚗'}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontFamily: 'var(--font-heading)', fontSize: 32, fontWeight: 700, color: '#1C1917' }}>
                      {formatPercent(total)}
                    </div>
                    <div style={{ fontSize: 11, color: '#A8A29E' }}>match score</div>
                  </div>
                  {validation && valColors[validation] && (
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: '4px 12px', borderRadius: 9999,
                      background: valColors[validation].bg, color: valColors[validation].text,
                    }}>{valColors[validation].label}</span>
                  )}
                </div>

                {/* 5-Signal Score Bars */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 24px', marginBottom: 20 }}>
                  {signals.map((key, i) => (
                    <div key={key}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#78716C' }}>{SIGNAL_LABELS[key]}</span>
                        <span style={{ fontSize: 13, fontWeight: 600, color: '#1C1917' }}>{formatPercent(bd[key])}</span>
                      </div>
                      <div style={{ height: 8, background: '#F5F5F4', borderRadius: 9999, overflow: 'hidden' }}>
                        <motion.div style={{ height: '100%', background: (bd[key] ?? 0) > 0.7 ? '#059669' : (bd[key] ?? 0) > 0.4 ? '#CA8A04' : '#A8A29E', borderRadius: 9999, transformOrigin: 'left' }}
                          {...barFill(bd[key] ?? 0, mi * 0.1 + i * 0.06)}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                {/* AI Verdict */}
                {isValidated && analysis?.overall_rationale && (
                  <div style={{
                    background: valColors[validation!]?.bg || '#F5F5F4',
                    border: `1px solid ${validation === 'Valid' ? '#BBF7D0' : validation === 'Weak' ? '#FDE68A' : '#FECACA'}`,
                    borderRadius: 10, padding: '12px 16px', marginBottom: 16,
                  }}>
                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: valColors[validation!]?.text || '#78716C', marginBottom: 6 }}>
                      🤖 AI Verdict
                    </div>
                    <p style={{ fontSize: 13, color: '#44403C', margin: 0, lineHeight: 1.7 }}>
                      {analysis.overall_rationale}
                    </p>
                    {analysis.signal_explanations && (
                      <details style={{ marginTop: 8 }}>
                        <summary style={{ fontSize: 11, color: '#78716C', cursor: 'pointer' }}>See per-signal reasoning</summary>
                        <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
                          {signals.map(k => analysis.signal_explanations?.[k] && (
                            <div key={k} style={{ fontSize: 11, color: '#57534E' }}>
                              <strong>{SIGNAL_LABELS[k]}:</strong> {String(analysis.signal_explanations[k])}
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                )}

                {/* Dispatch Brief */}
                {dispatch_brief && typeof dispatch_brief === 'string' && (
                  <div style={{ marginBottom: 16 }}>
                    <button onClick={() => setExpandedBrief(p => ({ ...p, [volunteer.id]: !p[volunteer.id] }))}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: '#059669', padding: 0, display: 'flex', alignItems: 'center', gap: 4 }}>
                      {expandedBrief[volunteer.id] ? '▲ Hide' : '▼ Show'} Dispatch Brief
                    </button>
                    {expandedBrief[volunteer.id] && (
                      <blockquote style={{ borderLeft: '3px solid #059669', paddingLeft: 16, margin: '8px 0 0', fontStyle: 'italic', fontSize: 14, color: '#44403C', lineHeight: 1.7 }}>
                        {dispatch_brief}
                      </blockquote>
                    )}
                  </div>
                )}

                {/* Action Buttons */}
                <div style={{ display: 'flex', gap: 10 }}>
                  {!isValidated && (
                    <button onClick={() => handleValidate(volunteer.id)} disabled={validating === volunteer.id}
                      style={{
                        flex: 1, padding: '12px 0',
                        background: 'linear-gradient(135deg, #7C3AED, #6D28D9)', color: '#fff',
                        border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 500,
                        cursor: validating === volunteer.id ? 'default' : 'pointer',
                        opacity: validating === volunteer.id ? 0.7 : 1,
                      }}>
                      {validating === volunteer.id ? '⏳ Validating with AI…' : '🤖 Validate with AI'}
                    </button>
                  )}
                  <button onClick={() => setAssigned(p => ({ ...p, [volunteer.id]: true }))}
                    disabled={assigned[volunteer.id]}
                    style={{
                      flex: 1, padding: '12px 0',
                      background: assigned[volunteer.id] ? '#16A34A' : 'linear-gradient(135deg, #059669, #10B981)', color: '#fff',
                      border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 600,
                      cursor: assigned[volunteer.id] ? 'default' : 'pointer', transition: 'background 200ms',
                    }}>
                    {assigned[volunteer.id] ? '✓ Assigned' : 'Assign Volunteer'}
                  </button>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
