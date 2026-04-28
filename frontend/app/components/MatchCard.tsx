'use client';
import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  MatchResult, AssignmentCreate, createAssignment, fetchMatchExplanation,
  LLMExplanationResponse,
} from '@/lib/api';
import { initialsFromName, formatPercent } from '@/lib/utils';
import { barFill, buttonTap } from '@/lib/animations';

interface Props {
  match: MatchResult;
  needId: string;
  onAssigned?: (assignmentId: string) => void;
}

const SIGNAL_LABELS: Record<string, string> = {
  skill_embedding: 'Experience Fit',
  skill_tags:      'Skills Match',
  geo_proximity:   'Distance',
  urgency:         'Urgency',
  availability:    'Availability',
};

export default function MatchCard({ match, needId, onAssigned }: Props) {
  const { volunteer } = match;
  // Backend returns 'score', frontend type has both 'score' and 'score_breakdown' for compat
  const score_breakdown = match.score ?? match.score_breakdown!;
  const total_score = score_breakdown?.total ?? match.total_score ?? 0;

  const [assigning, setAssigning] = useState(false);
  const [assigned, setAssigned] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [briefExpanded, setBriefExpanded] = useState(false);

  // LLM on-demand state
  const [llmData, setLlmData] = useState<LLMExplanationResponse | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);

  // Use LLM data if available, otherwise fall back to initial match data
  const llm_analysis = llmData?.llm_analysis ?? match.llm_analysis;
  const dispatch_brief = llmData?.dispatch_brief ?? match.dispatch_brief;
  const isLlmValidated = match.llm_validated || llmData?.llm_validated;

  const validation = llm_analysis?.validation;
  const validationColors: Record<string, { bg: string; text: string; label: string }> = {
    Valid: { bg: '#F7FEE7', text: '#4D7C0F', label: '✓ Valid Match' },
    Weak:  { bg: '#FFFBEB', text: '#B45309', label: '⚠ Weak Match' },
    Poor:  { bg: '#FEF2F2', text: '#DC2626', label: '✗ Poor Match' },
  };

  const signals = ['skill_embedding', 'skill_tags', 'geo_proximity', 'urgency', 'availability'] as const;

  async function handleValidateWithAI() {
    if (llmLoading || isLlmValidated) return;
    setLlmLoading(true);
    setLlmError(null);
    try {
      const result = await fetchMatchExplanation(needId, volunteer.id);
      setLlmData(result);
    } catch (e: unknown) {
      setLlmError(e instanceof Error ? e.message : 'AI validation failed. Try again.');
    } finally {
      setLlmLoading(false);
    }
  }

  async function handleAssign() {
    setAssigning(true);
    setError(null);
    try {
      // Strip non-float values from score_breakdown to prevent 422
      const cleanBreakdown: Record<string, number> = {};
      if (score_breakdown) {
        for (const [k, v] of Object.entries(score_breakdown)) {
          if (typeof v === 'number') {
            cleanBreakdown[k] = v;
          }
        }
      }

      const data: AssignmentCreate = {
        need_id: needId,
        volunteer_id: volunteer.id,
        match_score: total_score,
        score_breakdown: cleanBreakdown,
        dispatch_brief: typeof dispatch_brief === 'string' ? dispatch_brief : undefined,
      };
      const assignment = await createAssignment(data);
      setAssigned(true);
      onAssigned?.(assignment.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Assignment failed');
    } finally {
      setAssigning(false);
    }
  }

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #E7E5E4',
      borderRadius: 12,
      padding: 24,
    }}>
      {/* Volunteer header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <div style={{
          width: 44, height: 44, borderRadius: '50%',
          background: '#C2410C', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 15, fontWeight: 500, flexShrink: 0,
        }}>
          {initialsFromName(volunteer.name)}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 16, fontWeight: 500, color: '#1C1917' }}>{volunteer.name}</div>
          <div style={{ fontSize: 13, color: '#78716C', marginTop: 2 }}>
            {volunteer.skills.slice(0, 3).join(' · ')}
          </div>
        </div>
        {validation && validationColors[validation] && (
          <span style={{
            fontSize: 11, fontWeight: 500,
            padding: '3px 10px', borderRadius: 9999,
            background: validationColors[validation].bg,
            color: validationColors[validation].text,
          }}>
            {validationColors[validation].label}
            {!isLlmValidated && (
              <span style={{ fontSize: 9, opacity: 0.7 }}> (preliminary)</span>
            )}
          </span>
        )}
      </div>

      {/* Score bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 20 }}>
        {signals.map((key, i) => (
          <div key={key}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{
                fontSize: 11, letterSpacing: '0.08em',
                textTransform: 'uppercase', color: '#78716C',
              }}>
                {SIGNAL_LABELS[key]}
              </span>
              <span style={{ fontSize: 13, fontWeight: 500, color: '#1C1917' }}>
                {formatPercent(score_breakdown[key])}
              </span>
            </div>
            <div style={{ height: 8, background: '#F5F5F4', borderRadius: 9999, overflow: 'hidden' }}>
              <motion.div
                style={{ height: '100%', background: '#C2410C', borderRadius: 9999, transformOrigin: 'left' }}
                {...barFill(score_breakdown[key], i * 0.08)}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Total score */}
      <div style={{
        borderTop: '1px solid #E7E5E4',
        paddingTop: 16,
        display: 'flex',
        alignItems: 'baseline',
        gap: 8,
        marginBottom: 16,
      }}>
        <span style={{ fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#78716C' }}>
          Total Score
        </span>
        <span style={{
          fontFamily: "'Source Serif 4', Georgia, serif",
          fontSize: 32, fontWeight: 400, color: '#1C1917',
          marginLeft: 'auto', letterSpacing: '-0.02em',
        }}>
          {formatPercent(total_score)}
        </span>
      </div>

      {/* Validate with AI button — only if not yet validated */}
      {!isLlmValidated && (
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleValidateWithAI}
          disabled={llmLoading}
          style={{
            width: '100%', padding: '10px 0',
            background: 'linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%)',
            color: '#fff', border: 'none', borderRadius: 8,
            fontSize: 13, fontWeight: 500,
            cursor: llmLoading ? 'default' : 'pointer',
            opacity: llmLoading ? 0.7 : 1,
            marginBottom: 12,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            transition: 'opacity 200ms',
          }}
        >
          {llmLoading ? (
            <>
              <span style={{
                width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)',
                borderTopColor: '#fff', borderRadius: '50%',
                display: 'inline-block',
                animation: 'spin 0.8s linear infinite',
              }} />
              Validating with AI…
            </>
          ) : (
            <>🤖 Validate with AI</>
          )}
        </motion.button>
      )}

      {llmError && (
        <p style={{ fontSize: 12, color: '#DC2626', marginBottom: 8 }}>{llmError}</p>
      )}

      {/* Dispatch brief */}
      {dispatch_brief && typeof dispatch_brief === 'string' && (
        <div style={{ marginBottom: 16 }}>
          <button
            onClick={() => setBriefExpanded(x => !x)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 12, color: '#C2410C', padding: 0,
              display: 'flex', alignItems: 'center', gap: 4, marginBottom: 8,
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d={briefExpanded ? 'M18 15l-6-6-6 6' : 'M6 9l6 6 6-6'}/>
            </svg>
            {briefExpanded ? 'Hide' : 'Show'} Dispatch Brief
          </button>
          {briefExpanded && (
            <blockquote style={{
              borderLeft: '2px solid #C2410C',
              paddingLeft: 16, margin: 0,
              fontFamily: "'Source Serif 4', Georgia, serif",
              fontSize: 14, fontStyle: 'italic',
              color: '#44403C', lineHeight: 1.7,
            }}>
              {dispatch_brief}
            </blockquote>
          )}
        </div>
      )}

      {/* LLM rationale — shown only when AI has validated */}
      {isLlmValidated && llm_analysis?.overall_rationale && (
        <div style={{
          background: validation === 'Valid' ? '#F7FEE7'
                    : validation === 'Weak'  ? '#FFFBEB'
                    : '#FEF2F2',
          border: `1px solid ${validation === 'Valid' ? '#BEF264' : validation === 'Weak' ? '#FDE68A' : '#FECACA'}`,
          borderRadius: 8, padding: '10px 14px', marginBottom: 12,
        }}>
          <div style={{
            fontSize: 11, fontWeight: 600, letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: validation === 'Valid' ? '#4D7C0F' : validation === 'Weak' ? '#B45309' : '#DC2626',
            marginBottom: 6,
          }}>
            🤖 AI Verdict
          </div>
          <p style={{ fontSize: 12, color: '#44403C', margin: 0, lineHeight: 1.6 }}>
            {typeof llm_analysis.overall_rationale === 'string'
              ? llm_analysis.overall_rationale
              : 'AI analysis complete.'}
          </p>
          {/* Per-signal explanations — collapsed by default */}
          {llm_analysis.signal_explanations && Object.keys(llm_analysis.signal_explanations).length > 0 && (
            <details style={{ marginTop: 8 }}>
              <summary style={{ fontSize: 11, color: '#78716C', cursor: 'pointer', userSelect: 'none' }}>
                See detailed breakdown
              </summary>
              <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {signals.map(k => llm_analysis.signal_explanations[k] && (
                  <div key={k} style={{ fontSize: 11, color: '#57534E' }}>
                    <strong>{SIGNAL_LABELS[k]}:</strong>{' '}
                    {typeof llm_analysis.signal_explanations[k] === 'string'
                      ? llm_analysis.signal_explanations[k]
                      : JSON.stringify(llm_analysis.signal_explanations[k])}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <p style={{ fontSize: 13, color: '#DC2626', marginBottom: 8 }}>{error}</p>
      )}

      {/* Assign CTA */}
      <motion.button
        whileTap={buttonTap}
        onClick={handleAssign}
        disabled={assigning || assigned}
        style={{
          width: '100%', padding: '12px 0',
          background: assigned ? '#4D7C0F' : '#C2410C',
          color: '#fff', border: 'none', borderRadius: 8,
          fontSize: 14, fontWeight: 500, cursor: assigned || assigning ? 'default' : 'pointer',
          transition: 'background 200ms',
        }}
        onMouseEnter={e => { if (!assigned && !assigning) (e.currentTarget as HTMLElement).style.background = '#9A3412'; }}
        onMouseLeave={e => { if (!assigned && !assigning) (e.currentTarget as HTMLElement).style.background = '#C2410C'; }}
      >
        {assigned ? '✓ Assigned' : assigning ? 'Assigning…' : 'Assign This Volunteer'}
      </motion.button>

      {/* Spinner keyframe */}
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
