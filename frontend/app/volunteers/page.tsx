'use client';
import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import useSWR from 'swr';
import { fetchVolunteers } from '@/lib/api';
import VolunteerCard from '@/app/components/VolunteerCard';
import EmptyState from '@/app/components/EmptyState';
import LoadingBar from '@/app/components/LoadingBar';
import { cardVariants } from '@/lib/animations';
import Link from 'next/link';

const STATUSES = ['', 'available', 'on_assignment', 'inactive'];
const STATUS_LABELS: Record<string, string> = { '': 'All Statuses', available: 'Available', on_assignment: 'On Assignment', inactive: 'Inactive' };

const sel: React.CSSProperties = {
  height: 40, border: '1px solid #D6D3D1', borderRadius: 8,
  padding: '0 12px', fontSize: 14, color: '#1C1917',
  background: '#fff', outline: 'none', cursor: 'pointer',
  fontFamily: 'var(--font-body)',
};

export default function VolunteersPage() {
  const [status, setStatus] = useState('');
  const [skill, setSkill] = useState('');
  const [skillInput, setSkillInput] = useState('');

  // ─── Data Fetching with SWR ─────────────────────────────────
  const { data: volunteers, error, isLoading } = useSWR(
    ['volunteers', status, skill],
    () => fetchVolunteers({ status: status || undefined, skill: skill || undefined })
  );

  const list = volunteers || [];

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}
      style={{ maxWidth: 1320, margin: '0 auto', padding: '32px 24px 64px' }}
    >
      {isLoading && <LoadingBar />}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 30, fontWeight: 700, color: '#1C1917', margin: '0 0 4px' }}>Volunteers</h1>
          <p style={{ fontSize: 14, color: '#78716C', margin: 0 }}>{list.length} registered volunteers</p>
        </div>
        <Link href="/needs/new" style={{
          background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff', padding: '10px 20px',
          borderRadius: 8, fontSize: 14, fontWeight: 500, textDecoration: 'none',
        }}>+ Register New</Link>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 28 }}>
        <select value={status} onChange={e => setStatus(e.target.value)} style={sel}>
          {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
        </select>
        <div style={{ display: 'flex', gap: 0 }}>
          <input value={skillInput} onChange={e => setSkillInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') setSkill(skillInput); }}
            placeholder="Filter by skill…" style={{ ...sel, borderRadius: '8px 0 0 8px', borderRight: 'none', width: 200 }}
          />
          <button onClick={() => setSkill(skillInput)} style={{
            height: 40, padding: '0 14px', background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff',
            border: 'none', borderRadius: '0 8px 8px 0', cursor: 'pointer', fontSize: 14,
          }}>Filter</button>
        </div>
        {(status || skill) && (
          <button onClick={() => { setStatus(''); setSkill(''); setSkillInput(''); }}
            style={{ ...sel, color: '#059669', border: '1px solid #E7E5E4' }}>Clear</button>
        )}
      </div>

      {error && (
        <div style={{ padding: 40, textAlign: 'center', color: '#EF4444', fontWeight: 600 }}>
          Error loading volunteers. Please check your connection.
        </div>
      )}

      {!isLoading && list.length === 0 ? (
        <EmptyState message="No volunteers match your filters." ctaLabel="Clear filters" ctaHref="/volunteers" />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {list.map((vol, i) => (
            <motion.div key={vol.id} custom={i} variants={cardVariants} initial="hidden" animate="visible">
              <VolunteerCard volunteer={vol} />
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
