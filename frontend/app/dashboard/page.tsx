'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import useSWR from 'swr';
import { 
  fetchDashboardStats, 
  fetchHeatmap, 
  fetchDeserts, 
  fetchVolunteerLocations, 
  fetchActivity,
  HeatmapPoint
} from '@/lib/api';
import HeatMap from '@/app/components/HeatMap';
import ChatPanel from '@/app/components/ChatPanel';
import LoadingBar from '@/app/components/LoadingBar';
import { formatNeedType, timeAgo, urgencyColor, formatPercent } from '@/lib/utils';

// Recharts for Product-Grade Analytics
import { PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis } from 'recharts';

const fadeUp = { hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 } };

export default function DashboardPage() {
  const router = useRouter();
  const [showVol, setShowVol] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [selectedHotspot, setSelectedHotspot] = useState<HeatmapPoint | null>(null);

  // ─── Data Fetching with SWR ─────────────────────────────────
  const { data: stats, error: statsError } = useSWR('dashboard/stats', fetchDashboardStats);
  const { data: heatmap } = useSWR('dashboard/heatmap', () => fetchHeatmap());
  const { data: deserts } = useSWR('dashboard/deserts', () => fetchDeserts());
  const { data: volLocs } = useSWR('dashboard/vol-locations', fetchVolunteerLocations);
  const { data: activity } = useSWR('dashboard/activity', () => fetchActivity(20));

  const isLoading = !stats || !heatmap || !activity;

  if (statsError) {
    return (
      <div className="flex h-screen items-center justify-center bg-red-50 text-red-600 font-semibold">
        Error loading dashboard. Please ensure the backend is running.
      </div>
    );
  }

  const categoryData = stats ? Object.entries(stats.needs_by_type)
    .map(([name, value]) => ({ name: formatNeedType(name), value }))
    .sort((a, b) => b.value - a.value) : [];

  const COLORS = ['#059669', '#10B981', '#34D399', '#6EE7B7', '#A7F3D0', '#D1FAE5', '#ECFDF5'];

  return (
    <div style={{ position: 'relative', width: '100vw', height: 'calc(100vh - 56px)', overflow: 'hidden', background: '#F8FAFC' }}>
      {isLoading && <LoadingBar />}
      
      {/* Background Map */}
      <HeatMap 
        points={heatmap || []} 
        deserts={deserts || []} 
        volunteerLocations={volLocs || []} 
        showVolunteers={showVol} 
        onHotspotClick={setSelectedHotspot}
      />

      {/* Top Floating Header & Stats */}
      <motion.div initial="hidden" animate="visible" variants={fadeUp} transition={{ duration: 0.5, delay: 0.1 }}
        style={{ position: 'absolute', top: 24, left: 24, right: 384 + 48, zIndex: 10, pointerEvents: 'none' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, pointerEvents: 'auto' }}>
          <div style={{ background: 'rgba(255,255,255,0.85)', backdropFilter: 'blur(16px)', padding: '16px 24px', borderRadius: 16, border: '1px solid rgba(255,255,255,0.5)', boxShadow: '0 8px 32px rgba(0,0,0,0.05)' }}>
            <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 28, fontWeight: 700, margin: '0 0 4px', color: '#1C1917' }}>Command Center</h1>
            <p style={{ fontSize: 13, color: '#57534E', margin: 0, fontWeight: 500 }}>Live Humanitarian Coordination</p>
          </div>
          
          <div style={{ display: 'flex', gap: 12 }}>
            <label style={{ 
              background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(12px)', padding: '10px 16px', borderRadius: 12,
              fontSize: 13, fontWeight: 600, color: '#1C1917', display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
              border: '1px solid rgba(255,255,255,0.5)', boxShadow: '0 4px 16px rgba(0,0,0,0.05)'
            }}>
              <input type="checkbox" checked={showVol} onChange={e => setShowVol(e.target.checked)} style={{ accentColor: '#059669', width: 16, height: 16 }} />
              Show Volunteers
            </label>
            <button onClick={() => setChatOpen(true)} style={{
              background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff', border: 'none', borderRadius: 12,
              padding: '10px 20px', fontSize: 13, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
              boxShadow: '0 4px 16px rgba(5, 150, 105, 0.3)', transition: 'transform 200ms'
            }} onMouseDown={e => e.currentTarget.style.transform = 'scale(0.95)'} onMouseUp={e => e.currentTarget.style.transform = 'scale(1)'}>
              💬 Ask SevaBot
            </button>
          </div>
        </div>

        {stats && (
          <div style={{ display: 'flex', gap: 16, pointerEvents: 'auto' }}>
            {[
              { v: stats.total_needs, l: 'Total Needs' },
              { v: stats.active_needs, l: 'Active Needs' },
              { v: stats.critical_needs, l: 'Critical Now', c: '#DC2626' },
              { v: stats.matched_needs, l: 'Matched' },
              { v: stats.active_volunteers, l: 'Volunteers Active' },
            ].map((s, i) => (
              <div key={i} style={{ 
                background: 'rgba(255,255,255,0.85)', backdropFilter: 'blur(16px)', padding: '16px 20px', borderRadius: 16, 
                border: '1px solid rgba(255,255,255,0.5)', boxShadow: '0 8px 32px rgba(0,0,0,0.05)', flex: 1
              }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: s.c || '#1C1917', fontFamily: 'var(--font-heading)' }}>{s.v}</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#78716C', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.l}</div>
              </div>
            ))}
          </div>
        )}
      </motion.div>

      {/* Right Floating Panel (Charts & Activity) */}
      <motion.div initial={{ x: 400, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ duration: 0.6, delay: 0.2, type: 'spring' }}
        style={{
          position: 'absolute', top: 24, right: 24, bottom: 24, width: 384,
          background: 'rgba(255,255,255,0.85)', backdropFilter: 'blur(20px)',
          borderRadius: 24, border: '1px solid rgba(255,255,255,0.6)',
          boxShadow: '0 16px 48px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column',
          overflow: 'hidden', zIndex: 10
        }}
      >
        <div style={{ padding: '20px 20px 8px' }}>
          <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: 17, fontWeight: 700, margin: '0 0 12px', color: '#1C1917' }}>Needs by Category</h2>
          <div style={{ position: 'relative', height: 180, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={categoryData} cx="50%" cy="50%" innerRadius={55} outerRadius={72} paddingAngle={3} dataKey="value" stroke="none">
                  {categoryData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <RechartsTooltip
                  contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 8px 24px rgba(0,0,0,0.12)', fontSize: 13, fontWeight: 600, padding: '8px 14px' }}
                  formatter={(val, name) => [`${Number(val ?? 0)} needs`, String(name)]}
                />
              </PieChart>
            </ResponsiveContainer>
            {/* Center label */}
            <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
              <div style={{ fontSize: 26, fontWeight: 700, color: '#1C1917', fontFamily: 'var(--font-heading)', lineHeight: 1 }}>{categoryData.reduce((s, d) => s + d.value, 0)}</div>
              <div style={{ fontSize: 10, fontWeight: 600, color: '#78716C', textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 2 }}>Total</div>
            </div>
          </div>
          {/* Custom legend */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
            {categoryData.map((entry, i) => {
              const total = categoryData.reduce((s, d) => s + d.value, 0);
              const pct = total > 0 ? Math.round((entry.value / total) * 100) : 0;
              return (
                <div key={entry.name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 3, background: COLORS[i % COLORS.length], flexShrink: 0 }} />
                  <span style={{ fontSize: 12, color: '#475569', flex: 1, fontWeight: 500 }}>{entry.name}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#1C1917' }}>{entry.value}</span>
                  <span style={{ fontSize: 11, color: '#94A3B8', width: 32, textAlign: 'right' }}>{pct}%</span>
                </div>
              );
            })}
          </div>
        </div>

        <div style={{ padding: '16px 24px', borderTop: '1px solid rgba(0,0,0,0.05)', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: 16, fontWeight: 700, margin: '0 0 16px', color: '#1C1917' }}>⚡ Live Activity</h2>
          <div style={{ overflowY: 'auto', flex: 1, paddingRight: 8 }}>
            {activity?.map((item, i) => (
              <div key={i} style={{ marginBottom: 16, display: 'flex', gap: 12 }}>
                <div style={{ 
                  width: 32, height: 32, borderRadius: 10, background: '#F1F5F9', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  fontSize: 14
                }}>
                  {item.type === 'disaster_alert' ? '🚨' : item.type === 'assignment_completed' ? '✅' : item.type === 'volunteer_matched' ? '🤝' : '📋'}
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#1C1917', lineHeight: 1.4 }}>{item.title}</div>
                  <div style={{ fontSize: 11, color: '#78716C', marginTop: 2 }}>{timeAgo(item.timestamp)}</div>
                </div>
              </div>
            ))}
            {(!activity || activity.length === 0) && (
              <div style={{ fontSize: 13, color: '#94A3B8', textAlign: 'center', marginTop: 40 }}>No recent activity</div>
            )}
          </div>
        </div>
      </motion.div>

      {/* Slide-in Analytics Drawer (Click Hotspot) */}
      <AnimatePresence>
        {selectedHotspot && (
          <motion.div
            initial={{ y: '100%', opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            style={{
              position: 'absolute', bottom: 24, left: 24, right: 384 + 48,
              background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(24px)',
              borderRadius: 24, border: '1px solid rgba(255,255,255,0.6)',
              boxShadow: '0 16px 48px rgba(0,0,0,0.15)', zIndex: 20, padding: 24,
              display: 'flex', gap: 24
            }}
          >
            <button onClick={() => setSelectedHotspot(null)} style={{ position: 'absolute', top: 16, right: 16, background: '#F1F5F9', border: 'none', width: 28, height: 28, borderRadius: '50%', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
            
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: urgencyColor(selectedHotspot.urgency ?? 0.5), textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                {formatNeedType(selectedHotspot.need_type)}
              </div>
              <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: 24, fontWeight: 700, margin: '0 0 8px', color: '#1C1917' }}>
                {selectedHotspot.title}
              </h2>
              <p style={{ fontSize: 14, color: '#57534E', margin: '0 0 20px', lineHeight: 1.5, maxWidth: 500 }}>
                {selectedHotspot.description}
              </p>
              
              <div style={{ display: 'flex', gap: 16 }}>
                <div style={{ background: '#F8FAFC', padding: '12px 16px', borderRadius: 12, border: '1px solid #E2E8F0' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#1C1917' }}>{selectedHotspot.affected_count || 'N/A'}</div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#78716C', textTransform: 'uppercase' }}>Affected</div>
                </div>
                <div style={{ background: '#F8FAFC', padding: '12px 16px', borderRadius: 12, border: '1px solid #E2E8F0' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#1C1917' }}>{formatPercent(selectedHotspot.urgency)}</div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#78716C', textTransform: 'uppercase' }}>Urgency Level</div>
                </div>
                <button
                  onClick={() => router.push(`/needs/${selectedHotspot.need_id}`)}
                  style={{ 
                    background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff', border: 'none', borderRadius: 12, padding: '0 24px',
                    fontSize: 14, fontWeight: 700, cursor: 'pointer', marginLeft: 'auto',
                    boxShadow: '0 4px 16px rgba(5,150,105,0.3)',
                  }}>
                  Find Matches →
                </button>
              </div>
            </div>

            {/* Mini Chart for Hotspot */}
            <div style={{ width: 240, borderLeft: '1px solid #E2E8F0', paddingLeft: 24, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#1C1917', marginBottom: 16 }}>Resource Gap (Radius: 20km)</div>
              <div style={{ height: 100, width: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[
                    { name: 'Req.', count: 45, fill: '#EF4444' },
                    { name: 'Avail.', count: 12, fill: '#10B981' }
                  ]} layout="vertical" margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 12, fontWeight: 600, fill: '#78716C' }} />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={20} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div style={{ fontSize: 11, color: '#78716C', marginTop: 8 }}>
                Massive deficit in volunteers with <strong style={{color: '#1C1917'}}>Medical</strong> skills.
              </div>
            </div>

          </motion.div>
        )}
      </AnimatePresence>

      <ChatPanel isOpen={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  );
}
