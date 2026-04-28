'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { createNeed, NeedCreate } from '@/lib/api';
import { pageTransition, buttonTap } from '@/lib/animations';
import LoadingBar from '@/app/components/LoadingBar';

const NEED_TYPES = [
  { value: 'HEALTHCARE',       label: 'Healthcare' },
  { value: 'EDUCATION',        label: 'Education' },
  { value: 'WATER_SANITATION', label: 'Water & Sanitation' },
  { value: 'SHELTER',          label: 'Shelter' },
  { value: 'FOOD',             label: 'Food' },
  { value: 'INFRASTRUCTURE',   label: 'Infrastructure' },
  { value: 'LIVELIHOOD',       label: 'Livelihood' },
];

const inputStyle: React.CSSProperties = {
  width: '100%', height: 44,
  border: '1px solid #D6D3D1', borderRadius: 8,
  padding: '0 12px', fontSize: 16, color: '#1C1917',
  outline: 'none', transition: 'border-color 200ms',
  boxSizing: 'border-box', fontFamily: 'var(--font-body)',
};

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 11,
  letterSpacing: '0.1em', textTransform: 'uppercase',
  color: '#78716C', marginBottom: 6,
};

export default function SubmitNeedPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [skillInput, setSkillInput] = useState('');

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

  function removeSkill(skill: string) {
    setForm(f => ({ ...f, required_skills: f.required_skills.filter(s => s !== skill) }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim() || !form.description.trim()) {
      setError('Title and description are required.'); return;
    }
    setSubmitting(true); setError(null);
    try {
      const payload: NeedCreate = {
        title: form.title.trim(),
        description: form.description.trim(),
        need_type: form.need_type,
        location_name: form.location_name.trim() || undefined,
        urgency_base: form.urgency_base,
        affected_count: form.affected_count ? parseInt(form.affected_count) : undefined,
        required_skills: form.required_skills,
        source_channel: 'dashboard',
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

  return (
    <motion.div {...pageTransition} style={{ maxWidth: 680, margin: '0 auto', padding: '40px 24px 80px' }}>
      {submitting && <LoadingBar />}

      <h1 style={{
        fontFamily: 'var(--font-heading)',
        fontSize: 28, fontWeight: 400, color: '#1C1917',
        margin: '0 0 6px', letterSpacing: '-0.01em',
      }}>
        Report a Community Need
      </h1>
      <p style={{ fontSize: 15, color: '#78716C', marginBottom: 36 }}>
        Provide as much detail as possible. Our AI will help classify and match this need to available volunteers.
      </p>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Title */}
        <div>
          <label style={labelStyle}>Title *</label>
          <input
            value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            placeholder="e.g., Medical camp needed in Dharavi Ward 5"
            style={inputStyle}
            onFocus={e => (e.target.style.borderColor = '#059669')}
            onBlur={e => (e.target.style.borderColor = '#D6D3D1')}
            required
          />
        </div>

        {/* Description */}
        <div>
          <label style={labelStyle}>Description *</label>
          <textarea
            value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            placeholder="Describe the situation, who is affected, and what help is needed."
            rows={5}
            style={{ ...inputStyle, height: 'auto', padding: '12px', resize: 'vertical', lineHeight: 1.6 }}
            onFocus={e => (e.target.style.borderColor = '#059669')}
            onBlur={e => (e.target.style.borderColor = '#D6D3D1')}
            required
          />
        </div>

        {/* Type + Location */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <label style={labelStyle}>Need Type</label>
            <select
              value={form.need_type}
              onChange={e => setForm(f => ({ ...f, need_type: e.target.value }))}
              style={{ ...inputStyle, cursor: 'pointer' }}
              onFocus={e => (e.target.style.borderColor = '#C2410C')}
              onBlur={e => (e.target.style.borderColor = '#D6D3D1')}
            >
              {NEED_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Location</label>
            <input
              value={form.location_name}
              onChange={e => setForm(f => ({ ...f, location_name: e.target.value }))}
              placeholder="e.g., Dharavi, Mumbai"
              style={inputStyle}
              onFocus={e => (e.target.style.borderColor = '#C2410C')}
              onBlur={e => (e.target.style.borderColor = '#D6D3D1')}
            />
          </div>
        </div>

        {/* Urgency Slider */}
        <div>
          <label style={labelStyle}>
            Urgency —{' '}
            <span style={{ color: urgencyColor, fontWeight: 500 }}>{urgencyLabel}</span>
            <span style={{ color: '#A8A29E', fontWeight: 400, marginLeft: 6 }}>
              ({Math.round(form.urgency_base * 100)}%)
            </span>
          </label>
          <input
            type="range" min={0} max={1} step={0.01}
            value={form.urgency_base}
            onChange={e => setForm(f => ({ ...f, urgency_base: parseFloat(e.target.value) }))}
            style={{ width: '100%', accentColor: urgencyColor, cursor: 'pointer' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#A8A29E', marginTop: 4 }}>
            <span>Low</span><span>Moderate</span><span>High</span><span>Critical</span>
          </div>
        </div>

        {/* Affected Count */}
        <div>
          <label style={labelStyle}>Estimated Affected Count</label>
          <input
            type="number" min={0}
            value={form.affected_count}
            onChange={e => setForm(f => ({ ...f, affected_count: e.target.value }))}
            placeholder="e.g., 200"
            style={inputStyle}
            onFocus={e => (e.target.style.borderColor = '#059669')}
            onBlur={e => (e.target.style.borderColor = '#D6D3D1')}
          />
        </div>

        {/* Skills Tag Input */}
        <div>
          <label style={labelStyle}>Required Skills (press Enter to add)</label>
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center',
            border: '1px solid #D6D3D1', borderRadius: 8, padding: '6px 10px',
            minHeight: 44,
          }}>
            {form.required_skills.map(skill => (
              <span key={skill} style={{
                background: '#ECFDF5', color: '#44403C',
                fontSize: 13, borderRadius: 9999,
                padding: '3px 10px',
                display: 'flex', alignItems: 'center', gap: 6,
              }}>
                {skill}
                <button
                  type="button"
                  onClick={() => removeSkill(skill)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: '#A8A29E', lineHeight: 1 }}
                >×</button>
              </span>
            ))}
            <input
              value={skillInput}
              onChange={e => setSkillInput(e.target.value)}
              onKeyDown={addSkill}
              placeholder={form.required_skills.length === 0 ? 'nursing, first-aid, logistics…' : 'Add more…'}
              style={{ border: 'none', outline: 'none', fontSize: 14, flex: '1 1 120px', minWidth: 80, color: '#1C1917' }}
            />
          </div>
        </div>

        {error && (
          <p style={{ color: '#DC2626', fontSize: 14, margin: 0 }}>{error}</p>
        )}

        <motion.button
          whileTap={buttonTap}
          type="submit"
          disabled={submitting}
          style={{
            height: 48, background: '#059669', color: '#fff',
            border: 'none', borderRadius: 8, fontSize: 16, fontWeight: 500,
            cursor: submitting ? 'default' : 'pointer',
            opacity: submitting ? 0.7 : 1,
            transition: 'background 200ms',
            fontFamily: 'var(--font-body)',
            boxShadow: '0 4px 12px rgba(5, 150, 105, 0.25)',
          }}
          onMouseEnter={e => { if (!submitting) (e.currentTarget).style.background = '#047857'; }}
          onMouseLeave={e => { if (!submitting) (e.currentTarget).style.background = '#059669'; }}
        >
          {submitting ? 'Submitting…' : 'Submit Need Report'}
        </motion.button>
      </form>
    </motion.div>
  );
}
