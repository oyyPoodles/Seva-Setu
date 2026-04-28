import type { Metadata } from 'next';
import { Outfit, Inter } from 'next/font/google';
import Link from 'next/link';

const outfit = Outfit({ subsets: ['latin'], variable: '--font-heading', display: 'swap' });
const inter = Inter({ subsets: ['latin'], variable: '--font-body', display: 'swap', weight: ['300', '400', '500', '600'] });

export const metadata: Metadata = {
  title: 'SevaSetu — AI-Powered Resource Allocation for India',
  description: 'Matching community humanitarian needs with qualified volunteers across India using a 5-signal AI matching engine.',
};

const navLinks = [
  { label: 'Home', href: '/' },
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'Needs', href: '/needs' },
  { label: 'Volunteers', href: '/volunteers' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${outfit.variable} ${inter.variable}`}>
      <body style={{
        margin: 0,
        fontFamily: 'var(--font-body), -apple-system, BlinkMacSystemFont, sans-serif',
        color: '#1C1917',
        background: '#ffffff',
        WebkitFontSmoothing: 'antialiased',
        MozOsxFontSmoothing: 'grayscale',
      }}>
        {/* ─── Navbar ──────────────────────────────────── */}
        <nav style={{
          borderBottom: '1px solid #E7E5E4',
          padding: '0 24px', height: 56,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          maxWidth: 1320, margin: '0 auto',
          position: 'sticky', top: 0, background: 'rgba(255,255,255,0.85)',
          backdropFilter: 'blur(16px)', zIndex: 100,
          boxShadow: '0 4px 24px rgba(0,0,0,0.03)',
        }}>
          <Link href="/" style={{
            fontFamily: 'var(--font-heading)', fontSize: 20, fontWeight: 700,
            color: '#1C1917', textDecoration: 'none',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{ fontSize: 22 }}>🌱</span> SevaSetu
          </Link>
          <div style={{ display: 'flex', gap: 28, alignItems: 'center' }}>
            {navLinks.map(link => (
              <Link key={link.href} href={link.href} style={{
                fontSize: 14, fontWeight: 500, color: '#57534E',
                textDecoration: 'none', transition: 'color 200ms',
                position: 'relative', padding: '4px 0',
              }}>
                {link.label}
              </Link>
            ))}
            <Link href="/needs/new" style={{
              fontSize: 13, fontWeight: 600, color: '#fff',
              background: 'linear-gradient(135deg, #059669, #10B981)', padding: '8px 20px',
              borderRadius: 8, textDecoration: 'none',
              transition: 'transform 200ms, box-shadow 200ms',
              boxShadow: '0 4px 12px rgba(5, 150, 105, 0.2)',
            }}>
              + Report Need
            </Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
