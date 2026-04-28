'use client';
import Link from 'next/link';
import { NeedResponse } from '@/lib/api';
import { formatNeedType, urgencyLabel, urgencyColor, timeAgo } from '@/lib/utils';

interface Props {
  need: NeedResponse;
}

/** Card displaying a single community need with urgency indicator. */
export default function NeedCard({ need }: Props) {
  const urg = need.urgency_current ?? need.urgency_base ?? 0;

  return (
    <Link href={`/needs/${need.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
      <div style={{
        background: '#fff', border: 'none', borderRadius: 16,
        padding: 20, transition: 'box-shadow 200ms, transform 200ms',
        cursor: 'pointer', height: '100%',
        display: 'flex', flexDirection: 'column',
        boxShadow: '0 4px 20px rgba(0,0,0,0.03)',
      }}
        onMouseEnter={e => {
          (e.currentTarget).style.transform = 'translateY(-2px)';
          (e.currentTarget).style.boxShadow = '0 12px 32px rgba(5, 150, 105, 0.08)';
        }}
        onMouseLeave={e => {
          (e.currentTarget).style.transform = 'translateY(0)';
          (e.currentTarget).style.boxShadow = '0 4px 20px rgba(0,0,0,0.03)';
        }}
      >
        {/* Header row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
          <span style={{
            fontSize: 11, fontWeight: 500, letterSpacing: '0.08em',
            textTransform: 'uppercase', color: '#78716C',
          }}>
            {formatNeedType(need.need_type)}
          </span>
          <span style={{
            fontSize: 11, fontWeight: 600,
            padding: '2px 8px', borderRadius: 9999,
            background: urgencyColor(urg) + '18',
            color: urgencyColor(urg),
          }}>
            {urgencyLabel(urg)}
          </span>
        </div>

        {/* Title */}
        <h3 style={{
          fontFamily: 'var(--font-heading)',
          fontSize: 17, fontWeight: 600, color: '#1C1917',
          margin: '0 0 8px', lineHeight: 1.35,
          display: '-webkit-box', WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>
          {need.title}
        </h3>

        {/* Description snippet */}
        <p style={{
          fontSize: 13, color: '#78716C', lineHeight: 1.6,
          margin: '0 0 12px', flex: 1,
          display: '-webkit-box', WebkitLineClamp: 3,
          WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>
          {need.description}
        </p>

        {/* Footer */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          borderTop: '1px solid #F5F5F4', paddingTop: 10,
          fontSize: 12, color: '#A8A29E',
        }}>
          <span>{need.location_name || 'Location unknown'}</span>
          <span>{timeAgo(need.created_at)}</span>
        </div>

        {/* Status pill */}
        <div style={{ marginTop: 8 }}>
          <span style={{
            fontSize: 10, fontWeight: 500, textTransform: 'uppercase',
            padding: '2px 8px', borderRadius: 9999,
            background: need.status === 'completed' ? '#F0FDF4' : '#F5F5F4',
            color: need.status === 'completed' ? '#16A34A' : '#78716C',
            letterSpacing: '0.06em',
          }}>
            {need.status}
          </span>
          {need.affected_count && (
            <span style={{ fontSize: 11, color: '#A8A29E', marginLeft: 8 }}>
              {need.affected_count} affected
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
