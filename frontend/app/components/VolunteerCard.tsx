'use client';
import { VolunteerResponse } from '@/lib/api';
import { initialsFromName } from '@/lib/utils';

interface Props {
  volunteer: VolunteerResponse;
}

/** Card displaying a volunteer profile with skills and reliability. */
export default function VolunteerCard({ volunteer }: Props) {
  const rel = volunteer.reliability ?? 0;
  const relColor = rel >= 0.8 ? '#16A34A' : rel >= 0.5 ? '#CA8A04' : '#DC2626';

  return (
    <div style={{
      background: '#fff', border: 'none', borderRadius: 16,
      padding: 20, transition: 'transform 200ms, box-shadow 200ms',
      boxShadow: '0 4px 20px rgba(0,0,0,0.03)'
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
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <div style={{
          width: 42, height: 42, borderRadius: '50%',
          background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, fontWeight: 500, flexShrink: 0,
        }}>
          {initialsFromName(volunteer.name)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 500, color: '#1C1917', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {volunteer.name}
          </div>
          <div style={{ fontSize: 12, color: '#A8A29E', marginTop: 2 }}>
            {volunteer.status === 'available' ? '🟢 Available' :
             volunteer.status === 'on_assignment' ? '🟡 On Assignment' : '⚪ Inactive'}
          </div>
        </div>
      </div>

      {/* Skills */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 12 }}>
        {(volunteer.skills ?? []).slice(0, 4).map(s => (
          <span key={s} style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 9999,
            background: '#F5F5F4', color: '#44403C',
          }}>
            {s.replace(/_/g, ' ')}
          </span>
        ))}
        {volunteer.skills.length > 4 && (
          <span style={{ fontSize: 11, color: '#A8A29E' }}>+{volunteer.skills.length - 4}</span>
        )}
      </div>

      {/* Stats row */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        borderTop: '1px solid #F5F5F4', paddingTop: 10,
        fontSize: 12, color: '#78716C',
      }}>
        <span>
          Reliability: <span style={{ fontWeight: 600, color: relColor }}>{Math.round(rel * 100)}%</span>
        </span>
        <span>{volunteer.completed_tasks}/{volunteer.total_tasks} tasks</span>
        {volunteer.has_vehicle && <span>🚗</span>}
      </div>
    </div>
  );
}
