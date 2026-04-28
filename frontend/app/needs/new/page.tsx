'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { createNeed, NeedCreate } from '@/lib/api';
import LoadingBar from '@/app/components/LoadingBar';

const NEED_TYPES = [
  { value: 'HEALTHCARE',       label: '🏥 Healthcare',       color: '#EF4444' },
  { value: 'EDUCATION',        label: '📚 Education',         color: '#8B5CF6' },
  { value: 'WATER_SANITATION', label: '💧 Water & Sanitation', color: '#3B82F6' },
  { value: 'SHELTER',          label: '🏠 Shelter',           color: '#F59E0B' },
  { value: 'FOOD',             label: '🌾 Food',              color: '#10B981' },
  { value: 'INFRASTRUCTURE',   label: '🏗️ Infrastructure',    color: '#6366F1' },
  { value: 'LIVELIHOOD',       label: '💼 Livelihood',        color: '#EC4899' },
];

const stagger = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.07, delayChildren: 0.1 } }
};
const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as const } }
};

function Field({ children }: { children: React.ReactNode }) {
  return (
    <motion.div variants={fadeUp}>
      {children}
    </motion.div>
  );
}

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 11, letterSpacing: '0.12em',
  textTransform: 'uppercase', color: '#64748B', marginBottom: 8, fontWeight: 700,
};

function InputField({ style, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  const [focused, setFocused] = useState(false);
  return (
    <input
      {...props}
      onFocus={e => { setFocused(true); props.onFocus?.(e); }}
      onBlur={e => { setFocused(false); props.onBlur?.(e); }}
      style={{
        width: '100%', height: 48,
        border: `2px solid ${focused ? '#059669' : '#E2E8F0'}`,
        borderRadius: 12, padding: '0 16px', fontSize: 15, color: '#1C1917',
        outline: 'none', transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)',
        boxSizing: 'border-box', fontFamily: 'var(--font-body)',
        background: focused ? '#F0FDF4' : '#FAFAFA',
        boxShadow: focused ? '0 0 0 4px rgba(5, 150, 105, 0.1)' : 'none',
        ...style,
      }}
    />
  );
}

export default function SubmitNeedPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [skillInput, setSkillInput] = useState('');
  const [focusedTextarea, setFocusedTextarea] = useState(false);

  const [form, setForm] = useState<{
    title: string; description: string; need_type: string;
    location_name: string; urgency_base: number;
    affected_count: string; required_skills: string[];
  }>({
    title: '', description: '', need_type: 'HEALTHCARE',
    location_name: '', urgency_base: 0.7,
    affected_count: '', required_skills: [],
  });

  function addSkill(e: React.KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const trimmed = skillInput.trim().replace(/,$/, '');
      if (trimmed && !form.required_skills.includes(trimmed)) {
        setForm(f => ({ ...f, required_skills: [...f.required_skills, trimmed] }));
      }
      setSkillInput('');
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim() || !form.description.trim()) {
      setError('Title and description are required.'); return;
    }
    setSubmitting(true); setError(null);
    try {
      const payload: NeedCreate = {
        title: form.title.trim(), description: form.description.trim(),
        need_type: form.need_type, location_name: form.location_name.trim() || undefined,
        urgency_base: form.urgency_base,
        affected_count: form.affected_count ? parseInt(form.affected_count) : undefined,
        required_skills: form.required_skills, source_channel: 'dashboard',
      };
      const result = await createNeed(payload);
      router.push(`/needs/${result.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Submission failed.');
      setSubmitting(false);
    }
  }

  const urgencyLabel = form.urgency_base >= 0.85 ? 'Critical' :
    form.urgency_base >= 0.65 ? 'High' :
    form.urgency_base >= 0.40 ? 'Moderate' : 'Low';

  const urgencyColor = form.urgency_base >= 0.85 ? '#DC2626' :
    form.urgency_base >= 0.65 ? '#EA580C' :
    form.urgency_base >= 0.40 ? '#CA8A04' : '#16A34A';

  const urgencyBg = form.urgency_base >= 0.85 ? '#FEF2F2' :
    form.urgency_base >= 0.65 ? '#FFF7ED' :
    form.urgency_base >= 0.40 ? '#FEFCE8' : '#F0FDF4';

  return (
    <div style={{ minHeight: 'calc(100vh - 56px)', background: 'linear-gradient(135deg, #F0FDF4 0%, #F8FAFC 50%, #EFF6FF 100%)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '48px 24px 80px' }}>
      {submitting && <LoadingBar />}

      <motion.div
        initial="hidden"
        animate="visible"
        variants={stagger}
        style={{ width: '100%', maxWidth: 680 }}
      >
        {/* Header */}
        <Field>
          <div style={{ textAlign: 'center', marginBottom: 40 }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>📍</div>
            <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 32, fontWeight: 700, color: '#1C1917', margin: '0 0 8px', letterSpacing: '-0.02em' }}>
              Report a Community Need
            </h1>
            <p style={{ fontSize: 15, color: '#64748B', margin: 0, lineHeight: 1.6 }}>
              Our AI will classify and match this with the best available volunteers.
            </p>
          </div>
        </Field>

        {/* Card */}
        <motion.div
          variants={fadeUp}
          style={{ background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(16px)', borderRadius: 24, padding: '36px 40px', boxShadow: '0 16px 48px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)', border: '1px solid rgba(255,255,255,0.8)' }}
        >
          <form onSubmit={handleSubmit}>
            <motion.div variants={stagger} initial="hidden" animate="visible" style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>

              {/* Title */}
              <Field>
                <label style={labelStyle}>Title *</label>
                <InputField
                  value={form.title}
                  onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="e.g., Medical camp needed in Dharavi Ward 5"
                  required
                />
              </Field>

              {/* Description */}
              <Field>
                <label style={labelStyle}>Description *</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Describe the situation, who is affected, and what kind of help is needed…"
                  rows={4}
                  onFocus={() => setFocusedTextarea(true)}
                  onBlur={() => setFocusedTextarea(false)}
                  style={{
                    width: '100%', border: `2px solid ${focusedTextarea ? '#059669' : '#E2E8F0'}`,
                    borderRadius: 12, padding: '14px 16px', fontSize: 15, color: '#1C1917',
                    outline: 'none', transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)',
                    boxSizing: 'border-box', fontFamily: 'var(--font-body)', lineHeight: 1.6,
                    resize: 'vertical', background: focusedTextarea ? '#F0FDF4' : '#FAFAFA',
                    boxShadow: focusedTextarea ? '0 0 0 4px rgba(5, 150, 105, 0.1)' : 'none',
                  }}
                  required
                />
              </Field>

              {/* Need Type Cards */}
              <Field>
                <label style={labelStyle}>Need Type</label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                  {NEED_TYPES.map(t => (
                    <button
                      key={t.value}
                      type="button"
                      onClick={() => setForm(f => ({ ...f, need_type: t.value }))}
                      style={{
                        padding: '10px 8px', borderRadius: 12,
                        border: `2px solid ${form.need_type === t.value ? t.color : '#E2E8F0'}`,
                        background: form.need_type === t.value ? `${t.color}15` : '#FAFAFA',
                        cursor: 'pointer', fontSize: 11, fontWeight: 700,
                        color: form.need_type === t.value ? t.color : '#78716C',
                        transition: 'all 200ms', textAlign: 'center', lineHeight: 1.4,
                        transform: form.need_type === t.value ? 'scale(1.03)' : 'scale(1)',
                      }}
                    >
                      <div style={{ fontSize: 18, marginBottom: 2 }}>{t.label.split(' ')[0]}</div>
                      <div>{t.label.split(' ').slice(1).join(' ')}</div>
                    </button>
                  ))}
                </div>
              </Field>

              {/* Location & Count */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <Field>
                  <label style={labelStyle}>Location</label>
                  <InputField
                    value={form.location_name}
                    onChange={e => setForm(f => ({ ...f, location_name: e.target.value }))}
                    placeholder="e.g., Dharavi, Mumbai"
                  />
                </Field>
                <Field>
                  <label style={labelStyle}>Estimated Affected</label>
                  <InputField
                    type="number" min={0}
                    value={form.affected_count}
                    onChange={e => setForm(f => ({ ...f, affected_count: e.target.value }))}
                    placeholder="e.g., 200"
                  />
                </Field>
              </div>

              {/* Urgency Slider */}
              <Field>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <label style={{ ...labelStyle, margin: 0 }}>Urgency Level</label>
                  <AnimatePresence mode="wait">
                    <motion.span
                      key={urgencyLabel}
                      initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}
                      transition={{ duration: 0.2 }}
                      style={{ fontSize: 13, fontWeight: 700, color: urgencyColor, background: urgencyBg, padding: '4px 12px', borderRadius: 999 }}
                    >
                      {urgencyLabel} — {Math.round(form.urgency_base * 100)}%
                    </motion.span>
                  </AnimatePresence>
                </div>

                {/* Custom gradient slider */}
                <div style={{ position: 'relative', height: 8, borderRadius: 999, background: 'linear-gradient(to right, #16A34A, #CA8A04, #EA580C, #DC2626)', marginBottom: 12 }}>
                  <div style={{
                    position: 'absolute', top: 0, bottom: 0, left: 0,
                    width: `${form.urgency_base * 100}%`, borderRadius: 999,
                    background: 'transparent', transition: 'width 100ms'
                  }} />
                  <input
                    type="range" min={0} max={1} step={0.01}
                    value={form.urgency_base}
                    onChange={e => setForm(f => ({ ...f, urgency_base: parseFloat(e.target.value) }))}
                    style={{
                      position: 'absolute', top: '50%', transform: 'translateY(-50%)',
                      width: '100%', opacity: 0, cursor: 'pointer', height: 24, margin: 0
                    }}
                  />
                  {/* Thumb visual */}
                  <div style={{
                    position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)',
                    left: `${form.urgency_base * 100}%`,
                    width: 20, height: 20, borderRadius: '50%',
                    background: '#fff', border: `3px solid ${urgencyColor}`,
                    boxShadow: `0 2px 8px ${urgencyColor}40`,
                    transition: 'border-color 200ms, box-shadow 200ms',
                    pointerEvents: 'none'
                  }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94A3B8', fontWeight: 600 }}>
                  <span>Low</span><span>Moderate</span><span>High</span><span>Critical</span>
                </div>
              </Field>

              {/* Skills */}
              <Field>
                <label style={labelStyle}>Required Skills</label>
                <div style={{
                  display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center',
                  border: '2px solid #E2E8F0', borderRadius: 12, padding: '10px 12px',
                  minHeight: 52, background: '#FAFAFA', transition: 'all 200ms',
                }}>
                  {form.required_skills.map(skill => (
                    <motion.span
                      key={skill}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                      style={{
                        background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff',
                        fontSize: 12, fontWeight: 600, borderRadius: 999, padding: '4px 12px',
                        display: 'flex', alignItems: 'center', gap: 6, boxShadow: '0 2px 8px rgba(5,150,105,0.2)'
                      }}
                    >
                      {skill}
                      <button type="button" onClick={() => setForm(f => ({ ...f, required_skills: f.required_skills.filter(s => s !== skill) }))}
                        style={{ background: 'rgba(255,255,255,0.3)', border: 'none', cursor: 'pointer', padding: '1px 4px', borderRadius: '50%', color: '#fff', fontSize: 11, lineHeight: 1 }}>×</button>
                    </motion.span>
                  ))}
                  <input
                    value={skillInput}
                    onChange={e => setSkillInput(e.target.value)}
                    onKeyDown={addSkill}
                    placeholder={form.required_skills.length === 0 ? 'Type skill & press Enter (nursing, logistics…)' : 'Add more…'}
                    style={{ border: 'none', outline: 'none', fontSize: 14, flex: '1 1 140px', minWidth: 100, color: '#1C1917', background: 'transparent', fontFamily: 'var(--font-body)' }}
                  />
                </div>
              </Field>

              {/* Error */}
              <AnimatePresence>
                {error && (
                  <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    style={{ background: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: 10, padding: '12px 16px', color: '#DC2626', fontSize: 14, fontWeight: 500 }}>
                    ⚠️ {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Submit Button */}
              <Field>
                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.98 }}
                  type="submit"
                  disabled={submitting}
                  style={{
                    width: '100%', height: 56,
                    background: submitting ? '#D1D5DB' : 'linear-gradient(135deg, #059669, #10B981)',
                    color: '#fff', border: 'none', borderRadius: 14,
                    fontSize: 16, fontWeight: 700, cursor: submitting ? 'default' : 'pointer',
                    fontFamily: 'var(--font-body)',
                    boxShadow: submitting ? 'none' : '0 8px 24px rgba(5, 150, 105, 0.35)',
                    transition: 'all 300ms',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                  }}
                >
                  {submitting ? (
                    <>
                      <span style={{ display: 'inline-block', width: 18, height: 18, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                      Submitting…
                    </>
                  ) : (
                    <>
                      🚀 Submit Need Report
                    </>
                  )}
                </motion.button>
                <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
              </Field>
            </motion.div>
          </form>
        </motion.div>
      </motion.div>
    </div>
  );
}
