'use client';
import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { MOCK_NEEDS } from '@/lib/mock-data';
import NeedCard from '@/app/components/NeedCard';
import EmptyState from '@/app/components/EmptyState';
import { cardVariants } from '@/lib/animations';

const TYPES = ['', 'HEALTHCARE', 'EDUCATION', 'WATER_SANITATION', 'SHELTER', 'FOOD', 'INFRASTRUCTURE', 'LIVELIHOOD'];
const STATUSES = ['', 'new', 'matched', 'assigned', 'in_progress', 'completed'];
const URGENCIES = ['', 'critical', 'high', 'moderate', 'low'];

const TYPE_LABELS: Record<string, string> = { '': 'All Types', HEALTHCARE: 'Healthcare', EDUCATION: 'Education', WATER_SANITATION: 'Water & Sanitation', SHELTER: 'Shelter', FOOD: 'Food', INFRASTRUCTURE: 'Infrastructure', LIVELIHOOD: 'Livelihood' };
const STATUS_LABELS: Record<string, string> = { '': 'All Statuses', new: 'New', matched: 'Matched', assigned: 'Assigned', in_progress: 'In Progress', completed: 'Completed' };
const URGENCY_LABELS: Record<string, string> = { '': 'All Urgency', critical: 'Critical', high: 'High', moderate: 'Moderate', low: 'Low' };

function urgencyBucket(u: number): string {
  if (u >= 0.90) return 'critical';
  if (u >= 0.70) return 'high';
  if (u >= 0.45) return 'moderate';
  return 'low';
}

const sel: React.CSSProperties = {
  height: 40, border: '1px solid #D6D3D1', borderRadius: 8,
  padding: '0 12px', fontSize: 14, color: '#1C1917',
  background: '#fff', outline: 'none', cursor: 'pointer',
  fontFamily: 'var(--font-body)',
};

export default function NeedsPage() {
  const [type, setType] = useState('');
  const [status, setStatus] = useState('');
  const [urgency, setUrgency] = useState('');
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const filtered = useMemo(() => {
    return MOCK_NEEDS.filter(n => {
      if (type && n.need_type !== type) return false;
      if (status && n.status !== status) return false;
      if (urgency && urgencyBucket(n.urgency_current ?? n.urgency_base) !== urgency) return false;
      if (search && !n.title.toLowerCase().includes(search.toLowerCase()) && !n.description.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [type, status, urgency, search]);

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}
      style={{ maxWidth: 1320, margin: '0 auto', padding: '32px 24px 64px' }}
    >
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 30, fontWeight: 700, color: '#1C1917', margin: '0 0 4px' }}>
          Community Needs
        </h1>
        <p style={{ fontSize: 14, color: '#78716C', margin: 0 }}>
          {filtered.length} need{filtered.length !== 1 ? 's' : ''} {type || status || urgency || search ? 'match your filters' : 'reported across India'}
        </p>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 28 }}>
        <select value={type} onChange={e => setType(e.target.value)} style={sel}>
          {TYPES.map(t => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
        </select>
        <select value={status} onChange={e => setStatus(e.target.value)} style={sel}>
          {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
        </select>
        <select value={urgency} onChange={e => setUrgency(e.target.value)} style={sel}>
          {URGENCIES.map(u => <option key={u} value={u}>{URGENCY_LABELS[u]}</option>)}
        </select>
        <div style={{ display: 'flex', gap: 0, flex: '1 1 240px' }}>
          <input value={searchInput} onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') setSearch(searchInput); }}
            placeholder="Search needs…" style={{ ...sel, flex: 1, borderRadius: '8px 0 0 8px', borderRight: 'none' }}
          />
          <button onClick={() => setSearch(searchInput)} style={{
            height: 40, padding: '0 14px', background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff',
            border: 'none', borderRadius: '0 8px 8px 0', cursor: 'pointer', fontSize: 14,
          }}>Search</button>
        </div>
        {(type || status || urgency || search) && (
          <button onClick={() => { setType(''); setStatus(''); setUrgency(''); setSearch(''); setSearchInput(''); }}
            style={{ ...sel, color: '#059669', border: '1px solid #E7E5E4' }}>Clear filters</button>
        )}
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <EmptyState message="No needs match your filters." ctaLabel="Clear filters" ctaHref="/needs" />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
          {filtered.map((need, i) => (
            <motion.div key={need.id} custom={i} variants={cardVariants} initial="hidden" animate="visible">
              <NeedCard need={need} />
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
