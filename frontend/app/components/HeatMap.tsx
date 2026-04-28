'use client';
import { useState, useMemo, useEffect } from 'react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, IconLayer } from '@deck.gl/layers';
import { Map } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { HeatmapPoint, DesertZone, VolunteerLocation } from '@/lib/api';
import { urgencyColor, formatNeedType } from '@/lib/utils';
import { FlyToInterpolator } from '@deck.gl/core';

interface Props {
  points: HeatmapPoint[];
  deserts?: DesertZone[];
  volunteerLocations?: VolunteerLocation[];
  showVolunteers?: boolean;
  onHotspotClick?: (point: HeatmapPoint) => void;
}

type HoverInfo = {
  object: Partial<HeatmapPoint & VolunteerLocation>;
  x: number;
  y: number;
  isVol?: boolean;
};

const INITIAL_VIEW_STATE = {
  longitude: 78.9629,
  latitude: 20.5937,
  zoom: 4,
  pitch: 35,
  bearing: 0,
  transitionDuration: 1000,
  transitionInterpolator: new FlyToInterpolator()
};

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/positron-nolabels-gl-style/style.json';

// ─── Inline SVG Data URL for a red map pin (Google Maps style) ──────────────
const PIN_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 42" width="32" height="42">
  <defs>
    <radialGradient id="pg" cx="40%" cy="35%">
      <stop offset="0%" stop-color="#FF6B6B"/>
      <stop offset="100%" stop-color="#C0392B"/>
    </radialGradient>
    <filter id="shadow">
      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#00000044"/>
    </filter>
  </defs>
  <path d="M16 0 C7.16 0 0 7.16 0 16 C0 26 16 42 16 42 C16 42 32 26 32 16 C32 7.16 24.84 0 16 0Z"
    fill="url(#pg)" filter="url(#shadow)"/>
  <circle cx="16" cy="15" r="7" fill="white" opacity="0.9"/>
  <circle cx="16" cy="15" r="4" fill="#C0392B"/>
</svg>`;

const PIN_DATA_URL = `data:image/svg+xml;base64,${typeof window !== 'undefined' ? btoa(unescape(encodeURIComponent(PIN_SVG))) : ''}`;

// Fallback: build it at module level safely
function makePinUrl() {
  try {
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(PIN_SVG)}`;
  } catch {
    return '';
  }
}

const ICON_ATLAS = makePinUrl();

const ICON_MAPPING = {
  pin: { x: 0, y: 0, width: 32, height: 42, anchorY: 42, mask: false }
};

export default function HeatMap({ points, volunteerLocations = [], showVolunteers, onHotspotClick }: Props) {
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  const [hoverInfo, setHoverInfo] = useState<HoverInfo | null>(null);
  const [selectedVol, setSelectedVol] = useState<VolunteerLocation | null>(null);
  const [volCardPos, setVolCardPos] = useState({ x: 0, y: 0 });

  // ── Needs layer (urgency-colored circles) ──────────────────────────────────
  const needsLayer = new ScatterplotLayer({
    id: 'needs-layer',
    data: points,
    pickable: true,
    opacity: 0.85,
    stroked: true,
    filled: true,
    radiusScale: 1000,
    radiusMinPixels: 5,
    radiusMaxPixels: 32,
    lineWidthMinPixels: 1.5,
    getPosition: (d) => [d.longitude, d.latitude],
    getFillColor: (d) => {
      const hex = urgencyColor(d.urgency ?? 0.5);
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return [r, g, b, 210];
    },
    getLineColor: [255, 255, 255, 255],
    getRadius: (d) => d.affected_count ? Math.max(15, Math.log2(d.affected_count) * 9) : 15,
    onHover: (info) => {
      if (info.object) setHoverInfo({ object: info.object, x: info.x, y: info.y, isVol: false });
      else setHoverInfo(null);
    },
    onClick: (info) => {
      if (info.object) {
        setSelectedVol(null);
        setViewState(v => ({
          ...v,
          longitude: info.object.longitude,
          latitude: info.object.latitude,
          zoom: 7,
          transitionDuration: 800,
          transitionInterpolator: new FlyToInterpolator()
        }));
        if (onHotspotClick) onHotspotClick(info.object as HeatmapPoint);
      }
    },
  });

  // ── Volunteer drop-pin layer (red map pins) ────────────────────────────────
  const volPinLayer = new IconLayer({
    id: 'vol-pin-layer',
    data: showVolunteers ? volunteerLocations : [],
    pickable: true,
    iconAtlas: ICON_ATLAS,
    iconMapping: ICON_MAPPING,
    getIcon: () => 'pin',
    getPosition: (d) => [d.longitude, d.latitude],
    getSize: 48,
    sizeScale: 1,
    sizeMinPixels: 32,
    sizeMaxPixels: 56,
    onHover: (info) => {
      if (info.object) setHoverInfo({ object: info.object, x: info.x, y: info.y, isVol: true });
      else setHoverInfo(null);
    },
    onClick: (info) => {
      if (info.object) {
        setSelectedVol(info.object as VolunteerLocation);
        setVolCardPos({ x: info.x, y: info.y });
        setViewState(v => ({
          ...v,
          longitude: (info.object as VolunteerLocation).longitude,
          latitude: (info.object as VolunteerLocation).latitude,
          zoom: 7,
          transitionDuration: 600,
          transitionInterpolator: new FlyToInterpolator()
        }));
      }
    },
  });

  // ── Pulse rings for critical needs ─────────────────────────────────────────
  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    let raf: number;
    const start = Date.now();
    const animate = () => {
      setPulse(((Date.now() - start) % 2000) / 2000);
      raf = requestAnimationFrame(animate);
    };
    animate();
    return () => cancelAnimationFrame(raf);
  }, []);

  const criticalPoints = useMemo(() => points.filter(p => (p.urgency ?? 0) >= 0.7), [points]);

  const pulseLayer = new ScatterplotLayer({
    id: 'pulse-layer',
    data: criticalPoints,
    pickable: false,
    opacity: (1 - pulse) * 0.55,
    stroked: true,
    filled: false,
    radiusScale: 1000,
    radiusMinPixels: 4,
    lineWidthMinPixels: 2,
    getPosition: (d) => [d.longitude, d.latitude],
    getLineColor: (d) => {
      const hex = urgencyColor(d.urgency ?? 0.5);
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return [r, g, b, Math.floor(255 * (1 - pulse))];
    },
    getRadius: (d) => {
      const base = d.affected_count ? Math.max(15, Math.log2(d.affected_count) * 9) : 15;
      return base + pulse * 35;
    },
    updateTriggers: { getRadius: [pulse], getLineColor: [pulse], opacity: [pulse] }
  });

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: vs }) => setViewState(vs as typeof INITIAL_VIEW_STATE)}
        controller={{ doubleClickZoom: false }}
        layers={[needsLayer, pulseLayer, volPinLayer]}
        getCursor={({ isHovering }) => isHovering ? 'pointer' : 'grab'}
        onClick={() => { if (selectedVol) setSelectedVol(null); }}
      >
        <Map mapStyle={MAP_STYLE} />
      </DeckGL>

      {/* Hover Tooltip */}
      {hoverInfo?.object && (
        <div style={{
          position: 'absolute', zIndex: 5, pointerEvents: 'none',
          left: hoverInfo.x, top: hoverInfo.y,
          transform: 'translate(-50%, -120%)',
          background: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(20px)',
          padding: '12px 16px', borderRadius: 14,
          boxShadow: '0 12px 32px rgba(0,0,0,0.12)', border: '1px solid rgba(255,255,255,0.8)',
          fontFamily: 'var(--font-body)', minWidth: 190, maxWidth: 240
        }}>
          {hoverInfo.isVol ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#C0392B', flexShrink: 0 }} />
                <div style={{ fontSize: 13, fontWeight: 700, color: '#1C1917' }}>{(hoverInfo.object as VolunteerLocation).name}</div>
              </div>
              <div style={{ fontSize: 11, color: '#64748B', lineHeight: 1.5 }}>
                {(hoverInfo.object as VolunteerLocation).skills?.join(' · ')}
              </div>
              <div style={{ fontSize: 10, color: '#94A3B8', marginTop: 4 }}>Click to see profile</div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 10, fontWeight: 700, color: urgencyColor((hoverInfo.object as HeatmapPoint).urgency ?? 0.5), textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
                {formatNeedType((hoverInfo.object as HeatmapPoint).need_type)}
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#1C1917', marginBottom: 6, lineHeight: 1.3 }}>
                {(hoverInfo.object as HeatmapPoint).title}
              </div>
              <div style={{ fontSize: 12, color: '#64748B' }}>👥 {(hoverInfo.object as HeatmapPoint).affected_count || '?'} affected</div>
              <div style={{ fontSize: 10, color: '#94A3B8', marginTop: 4 }}>Click to see analytics</div>
            </>
          )}
          <div style={{ position: 'absolute', bottom: -7, left: '50%', transform: 'translateX(-50%) rotate(45deg)', width: 14, height: 14, background: 'rgba(255,255,255,0.95)', borderBottom: '1px solid rgba(0,0,0,0.05)', borderRight: '1px solid rgba(0,0,0,0.05)' }} />
        </div>
      )}

      {/* Volunteer Flashcard */}
      {selectedVol && (
        <div style={{
          position: 'absolute', zIndex: 30,
          left: Math.min(volCardPos.x + 16, 880),
          top: Math.max(volCardPos.y - 200, 16),
          width: 300,
          background: '#fff', borderRadius: 20,
          border: '1px solid #F1F5F9',
          boxShadow: '0 24px 64px rgba(0,0,0,0.16)',
          fontFamily: 'var(--font-body)',
          animation: 'volCardIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards',
          overflow: 'hidden',
        }}>
          <style>{`@keyframes volCardIn { from { opacity:0; transform:scale(0.92) translateY(8px); } to { opacity:1; transform:scale(1) translateY(0); } }`}</style>

          {/* Red gradient header — matching the pin color */}
          <div style={{ background: 'linear-gradient(135deg, #C0392B, #E74C3C)', padding: '20px 20px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ width: 48, height: 48, borderRadius: 14, background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 800, color: '#fff' }}>
                {selectedVol.name.charAt(0)}
              </div>
              <button onClick={() => setSelectedVol(null)} style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer', width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>✕</button>
            </div>
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>{selectedVol.name}</div>
              <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.75)', marginTop: 2 }}>
                📍 Volunteer {selectedVol.has_vehicle ? '· 🚗 Has Vehicle' : ''}
              </div>
            </div>
          </div>

          {/* Body */}
          <div style={{ padding: '16px 20px 20px' }}>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#94A3B8', marginBottom: 8 }}>Skills</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {selectedVol.skills?.map(skill => (
                  <span key={skill} style={{ background: '#FEF2F2', color: '#C0392B', fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 999, border: '1px solid #FECACA' }}>{skill.replace(/_/g, ' ')}</span>
                ))}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: selectedVol.status === 'available' ? '#10B981' : '#F59E0B', flexShrink: 0 }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: '#334155', textTransform: 'capitalize' }}>{selectedVol.status}</span>
            </div>
          </div>
        </div>
      )}

      {/* Zoom Controls */}
      <div style={{ position: 'absolute', bottom: 24, left: 24, display: 'flex', flexDirection: 'column', gap: 8, zIndex: 10 }}>
        {[
          { label: '+', fn: () => setViewState(v => ({ ...v, zoom: v.zoom + 1, transitionDuration: 300, transitionInterpolator: new FlyToInterpolator() })) },
          { label: '−', fn: () => setViewState(v => ({ ...v, zoom: v.zoom - 1, transitionDuration: 300, transitionInterpolator: new FlyToInterpolator() })) },
          { label: '↺', fn: () => setViewState({ ...INITIAL_VIEW_STATE }) },
        ].map(({ label, fn }) => (
          <button key={label} onClick={fn} style={{
            width: 40, height: 40, background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(12px)',
            border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, cursor: 'pointer',
            boxShadow: '0 4px 16px rgba(0,0,0,0.08)', fontSize: label === '↺' ? 16 : 20,
            fontWeight: 500, color: '#334155', transition: 'all 150ms',
          }}
            onMouseEnter={e => e.currentTarget.style.background = '#F0FDF4'}
            onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.92)'}
          >{label}</button>
        ))}
      </div>
    </div>
  );
}
