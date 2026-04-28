'use client';
import Link from 'next/link';

interface Props {
  message: string;
  ctaLabel?: string;
  ctaHref?: string;
}

/** Friendly empty state with optional CTA button. */
export default function EmptyState({ message, ctaLabel, ctaHref }: Props) {
  return (
    <div style={{
      textAlign: 'center', padding: '64px 24px',
      border: '1px dashed #E2E8F0', borderRadius: 12,
      background: '#F8FAFC',
    }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
      <p style={{ fontSize: 16, color: '#78716C', marginBottom: 20 }}>{message}</p>
      {ctaLabel && ctaHref && (
        <Link
          href={ctaHref}
          style={{
            display: 'inline-block',
            background: 'linear-gradient(135deg, #059669, #10B981)', color: '#fff',
            padding: '10px 24px', borderRadius: 8,
            fontSize: 14, fontWeight: 500, textDecoration: 'none',
          }}
        >
          {ctaLabel}
        </Link>
      )}
    </div>
  );
}
