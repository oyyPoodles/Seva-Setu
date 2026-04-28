'use client';
import { motion } from 'framer-motion';

interface Props {
  value: number;
  label: string;
  accent?: boolean;
  urgencyColor?: string;
}

/** Dashboard stat card with animated counter. */
export default function StatsCard({ value, label, accent, urgencyColor: uc }: Props) {
  const color = uc ?? (accent ? '#059669' : '#1C1917');
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{
        background: '#fff', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.04)',
        borderRadius: 16, padding: '16px 20px',
      }}
    >
      <div style={{
        fontFamily: 'var(--font-heading)',
        fontSize: 32, fontWeight: 700, color,
        letterSpacing: '-0.02em', lineHeight: 1,
      }}>
        {value.toLocaleString('en-IN')}
      </div>
      <div style={{ fontSize: 12, color: '#78716C', marginTop: 6 }}>
        {label}
      </div>
    </motion.div>
  );
}
