'use client';
import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import useSWR from 'swr';
import { fetchNeeds } from '@/lib/api';
import NeedCard from '@/app/components/NeedCard';
import EmptyState from '@/app/components/EmptyState';
import LoadingBar from '@/app/components/LoadingBar';

const TYPES = ['', 'HEALTHCARE', 'EDUCATION', 'WATER_SANITATION', 'SHELTER', 'FOOD', 'INFRASTRUCTURE', 'LIVELIHOOD'];
const STATUSES = ['', 'new', 'matched', 'assigned', 'in_progress', 'completed'];
const URGENCIES = ['', 'critical', 'high', 'moderate', 'low'];

const TYPE_LABELS: Record<string, string> = { '': 'All Types', HEALTHCARE: '🏥 Healthcare', EDUCATION: '📚 Education', WATER_SANITATION: '💧 Water', SHELTER: '🏠 Shelter', FOOD: '🌾 Food', INFRASTRUCTURE: '🏗️ Infrastructure', LIVELIHOOD: '💼 Livelihood' };
const STATUS_LABELS: Record<string, string> = { '': 'All Status', new: 'New', matched: 'Matched', assigned: 'Assigned', in_progress: 'In Progress', completed: 'Completed' };
const URGENCY_LABELS: Record<string, string> = { '': 'All Urgency', critical: '🔴 Critical', high: '🟠 High', moderate: '🟡 Moderate', low: '🟢 Low' };

const URGENCY_COLORS: Record<string, string> = { critical: '#DC2626', high: '#EA580C', moderate: '#CA8A04', low: '#16A34A' };

function urgencyBucket(u: number): string {
  if (u >= 0.90) return 'critical';
  if (u >= 0.70) return 'high';
  if (u >= 0.45) return 'moderate';
  return 'low';
}

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.04, duration: 0.35, ease: [0.16, 1, 0.3, 1] as const }
  }),
};

function FilterSelect({ value, onChange, options, labels }: { value: string; onChange: (v: string) => void; options: string[]; labels: Record<string, string> }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      style={{
        height: 40, border: '1.5px solid #E2E8F0', borderRadius: 10,
        padding: '0 14px', fontSize: 13, fontWeight: 600, color: value ? '#1C1917' : '#64748B',
        background: '#fff', outline: 'none', cursor: 'pointer',
        fontFamily: 'var(--font-body)', transition: 'border-color 200ms',
        appearance: 'none', paddingRight: 32,
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394A3B8' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
        backgroundRepeat: 'no-repeat', backgroundPosition: 'right 10px center',
      }}
      onFocus={e => e.target.style.borderColor = '#059669'}
      onBlur={e => e.target.style.borderColor = '#E2E8F0'}
    >
      {options.map(o => <option key={o} value={o}>{labels[o]}</option>)}
    </select>
  );
}

export default function NeedsPage() {
  const [type, setType] = useState('');
  const [status, setStatus] = useState('');
  const [urgency, setUrgency] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [focused, setFocused] = useState(false);

  // ─── Data Fetching with SWR ─────────────────────────────────
  const { data, error, isLoading } = useSWR(
    ['needs', type, status, urgency, search],
    () => fetchNeeds({ type, status, urgency, search, page_size: 50 })
  );

  const needs = data?.needs || [];
  const hasFilters = type || status || urgency || search;

  return (
    <div style={{ minHeight: 'calc(100vh - 56px)', background: 'linear-gradient(180deg, #F8FAFC 0%, #fff 200px)' }}>
      {isLoading && <LoadingBar />}
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '40px 28px 80px' }}>

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
            <div>
              <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 34, fontWeight: 800, color: '#0F172A', margin: '0 0 6px', letterSpacing: '-0.02em' }}>
                Community Needs
              </h1>
              <p style={{ fontSize: 15, color: '#64748B', margin: 0 }}>
                {needs.length} {needs.length === 1 ? 'need' : 'needs'} {hasFilters ? 'match your filters' : 'reported across India'}
              </p>
            </div>
            <Link href="/needs/new" style={{
              background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff', padding: '12px 24px',
              borderRadius: 12, fontSize: 14, fontWeight: 700, textDecoration: 'none',
              boxShadow: '0 4px 16px rgba(5,150,105,0.3)', display: 'flex', alignItems: 'center', gap: 8,
              transition: 'transform 200ms',
            }}
              onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-1px)'}
              onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
            >
              + Report a Need
            </Link>
          </div>
        </motion.div>

        {/* Filters */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}
          style={{ background: '#fff', borderRadius: 16, padding: '16px 20px', marginBottom: 28, boxShadow: '0 2px 16px rgba(0,0,0,0.04)', border: '1px solid #F1F5F9', display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          
          <div style={{ display: 'flex', flex: '1 1 240px', gap: 0 }}>
            <input
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') setSearch(searchInput); }}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="Search needs by title or description…"
              style={{
                flex: 1, height: 40, border: `1.5px solid ${focused ? '#059669' : '#E2E8F0'}`, borderRight: 'none',
                borderRadius: '10px 0 0 10px', padding: '0 14px', fontSize: 13, fontWeight: 500,
                color: '#1C1917', background: '#fff', outline: 'none', fontFamily: 'var(--font-body)',
                transition: 'border-color 200ms',
              }}
            />
            <button onClick={() => setSearch(searchInput)} style={{
              height: 40, padding: '0 16px', background: 'linear-gradient(135deg, #059669, #10B981)',
              color: '#fff', border: 'none', borderRadius: '0 10px 10px 0', cursor: 'pointer', fontSize: 13, fontWeight: 700,
            }}>Search</button>
          </div>

          <div style={{ width: 1, height: 32, background: '#E2E8F0', flexShrink: 0 }} />

          <FilterSelect value={type} onChange={setType} options={TYPES} labels={TYPE_LABELS} />
          <FilterSelect value={status} onChange={setStatus} options={STATUSES} labels={STATUS_LABELS} />
          <FilterSelect value={urgency} onChange={setUrgency} options={URGENCIES} labels={URGENCY_LABELS} />

          <AnimatePresence>
            {hasFilters && (
              <motion.button
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                onClick={() => { setType(''); setStatus(''); setUrgency(''); setSearch(''); setSearchInput(''); }}
                style={{ height: 40, padding: '0 14px', fontSize: 13, fontWeight: 600, color: '#EF4444', background: '#FEF2F2', border: '1.5px solid #FCA5A5', borderRadius: 10, cursor: 'pointer', whiteSpace: 'nowrap' }}
              >
                ✕ Clear
              </motion.button>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Error State */}
        {error && (
          <div style={{ padding: 40, textAlign: 'center', color: '#EF4444', fontWeight: 600 }}>
            Error loading needs. Please check your connection.
          </div>
        )}

        {/* Active filter chips */}
        <AnimatePresence>
          {hasFilters && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
              style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
              {type && <span style={{ background: '#EFF6FF', color: '#2563EB', fontSize: 12, fontWeight: 700, padding: '4px 12px', borderRadius: 999 }}>Type: {TYPE_LABELS[type]}</span>}
              {status && <span style={{ background: '#F0FDF4', color: '#16A34A', fontSize: 12, fontWeight: 700, padding: '4px 12px', borderRadius: 999 }}>Status: {STATUS_LABELS[status]}</span>}
              {urgency && <span style={{ background: URGENCY_COLORS[urgency] + '18', color: URGENCY_COLORS[urgency], fontSize: 12, fontWeight: 700, padding: '4px 12px', borderRadius: 999 }}>Urgency: {URGENCY_LABELS[urgency]}</span>}
              {search && <span style={{ background: '#F8FAFC', color: '#475569', fontSize: 12, fontWeight: 700, padding: '4px 12px', borderRadius: 999 }}>{search}</span>}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Grid */}
        {!isLoading && needs.length === 0 ? (
          <EmptyState message="No needs match your filters." ctaLabel="Clear filters" ctaHref="/needs" />
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 20 }}>
            {needs.map((need, i) => (
              <motion.div key={need.id} custom={i} variants={cardVariants} initial="hidden" animate="visible" style={{ height: '100%' }}>
                <NeedCard need={need} />
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
