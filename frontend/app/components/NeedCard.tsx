'use client';
import Link from 'next/link';
import { NeedResponse } from '@/lib/api';
import { formatNeedType, urgencyLabel, urgencyColor, timeAgo } from '@/lib/utils';

interface Props {
  need: NeedResponse;
}

const TYPE_ICONS: Record<string, string> = {
  HEALTHCARE: '🏥', EDUCATION: '📚', WATER_SANITATION: '💧',
  SHELTER: '🏠', FOOD: '🌾', INFRASTRUCTURE: '🏗️', LIVELIHOOD: '💼',
};

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  new:         { bg: '#EFF6FF', text: '#2563EB' },
  matched:     { bg: '#F0FDF4', text: '#16A34A' },
  assigned:    { bg: '#FFF7ED', text: '#EA580C' },
  in_progress: { bg: '#FEF3C7', text: '#D97706' },
  completed:   { bg: '#F0FDF4', text: '#059669' },
};

export default function NeedCard({ need }: Props) {
  const urg = need.urgency_current ?? need.urgency_base ?? 0;
  const urgColor = urgencyColor(urg);
  const icon = TYPE_ICONS[need.need_type ?? ''] ?? '📌';
  const statusStyle = STATUS_COLORS[need.status ?? 'new'] ?? STATUS_COLORS.new;

  return (
    <Link href={`/needs/${need.id}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block', height: '100%' }}>
      <div style={{
        background: '#fff', borderRadius: 18, overflow: 'hidden',
        height: '100%', display: 'flex', flexDirection: 'column',
        boxShadow: '0 2px 16px rgba(0,0,0,0.04)',
        transition: 'box-shadow 220ms, transform 220ms',
        cursor: 'pointer', border: '1px solid #F1F5F9',
      }}
        onMouseEnter={e => {
          e.currentTarget.style.transform = 'translateY(-3px)';
          e.currentTarget.style.boxShadow = `0 16px 40px rgba(0,0,0,0.08), 0 0 0 2px ${urgColor}22`;
        }}
        onMouseLeave={e => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = '0 2px 16px rgba(0,0,0,0.04)';
        }}
      >
        {/* Urgency accent bar */}
        <div style={{ height: 4, background: urgColor, opacity: 0.7 }} />

        <div style={{ padding: '18px 20px', flex: 1, display: 'flex', flexDirection: 'column' }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 18 }}>{icon}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {formatNeedType(need.need_type)}
              </span>
            </div>
            <span style={{
              fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 999,
              background: urgColor + '16', color: urgColor, letterSpacing: '0.04em'
            }}>
              {urgencyLabel(urg)}
            </span>
          </div>

          {/* Title */}
          <h3 style={{
            fontFamily: 'var(--font-heading)', fontSize: 16, fontWeight: 700, color: '#0F172A',
            margin: '0 0 8px', lineHeight: 1.4,
            display: '-webkit-box', WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical', overflow: 'hidden',
          }}>
            {need.title}
          </h3>

          {/* Description */}
          <p style={{
            fontSize: 13, color: '#64748B', lineHeight: 1.65,
            margin: '0 0 16px', flex: 1,
            display: '-webkit-box', WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical', overflow: 'hidden',
          }}>
            {need.description}
          </p>

          {/* Affected + Skills row */}
          {(need.affected_count || (need.required_skills && need.required_skills.length > 0)) && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
              {need.affected_count && (
                <span style={{ fontSize: 12, background: '#F8FAFC', border: '1px solid #E2E8F0', color: '#475569', padding: '3px 10px', borderRadius: 999, fontWeight: 600 }}>
                  👥 {need.affected_count.toLocaleString()}
                </span>
              )}
              {need.required_skills?.slice(0, 2).map(s => (
                <span key={s} style={{ fontSize: 11, background: '#F0FDF4', color: '#059669', padding: '3px 10px', borderRadius: 999, fontWeight: 600 }}>
                  {s.replace(/_/g, ' ')}
                </span>
              ))}
              {(need.required_skills?.length ?? 0) > 2 && (
                <span style={{ fontSize: 11, color: '#94A3B8', padding: '3px 0' }}>+{(need.required_skills?.length ?? 0) - 2} more</span>
              )}
            </div>
          )}

          {/* Footer */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 12, borderTop: '1px solid #F1F5F9' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ background: statusStyle.bg, color: statusStyle.text, padding: '3px 10px', borderRadius: 999, fontWeight: 700, textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.06em' }}>
                {need.status?.replace(/_/g, ' ')}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94A3B8' }}>
              <span>📍 {need.location_name?.split(',')[0] || '—'}</span>
              <span>·</span>
              <span>{timeAgo(need.created_at)}</span>
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}
