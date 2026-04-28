import { MOCK_NEEDS } from '@/lib/mock-data';
import NeedDetailClient from './NeedDetailClient';

export function generateStaticParams() {
  return MOCK_NEEDS.map((need) => ({ id: need.id }));
}

export default async function NeedDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <NeedDetailClient id={id} />;
}
