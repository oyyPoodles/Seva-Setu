'use client';
import { DesertZone } from '@/lib/api';

interface Props {
  deserts: DesertZone[];
}

/** Displays a list of detected "need desert" zones — areas with low report density. */
export default function NeedDesertOverlay({ deserts }: Props) {
  if (!deserts || deserts.length === 0) return null;

  return (
    <div style={{
      border: '1px solid #E7E5E4', borderRadius: 12,
      background: '#fff', overflow: 'hidden',
    }}>
      <div style={{
        padding: '14px 20px', borderBottom: '1px solid #E7E5E4',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ fontSize: 16 }}>🏜️</span>
        <h2 style={{
          fontFamily: "'Source Serif 4', serif",
          fontSize: 16, fontWeight: 600, color: '#1C1917', margin: 0,
        }}>
          Need Deserts
        </h2>
        <span style={{
          fontSize: 11, color: '#78716C', marginLeft: 'auto',
        }}>
          {deserts.length} zone{deserts.length !== 1 ? 's' : ''} detected
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 1, background: '#F5F5F4' }}>
        {deserts.map((d, i) => (
          <div key={i} style={{ background: '#fff', padding: '14px 20px' }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: '#1C1917', marginBottom: 4 }}>
              {d.area_name}
            </div>
            <div style={{ fontSize: 12, color: '#78716C', lineHeight: 1.6 }}>
              {d.report_count} report{d.report_count !== 1 ? 's' : ''} in {d.radius_km}km radius
              {d.population_estimate && (
                <span> · ~{d.population_estimate.toLocaleString('en-IN')} population</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
