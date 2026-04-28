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

export default function HeatMap({ points, deserts = [], volunteerLocations = [], showVolunteers, onHotspotClick }: Props) {
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  const [hoverInfo, setHoverInfo] = useState<any>(null);
  const [selectedVol, setSelectedVol] = useState<VolunteerLocation | null>(null);
  const [volCardPos, setVolCardPos] = useState({ x: 0, y: 0 });

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
    onHover: (info) => setHoverInfo(info),
    onClick: (info) => {
      if (info.object) {
        setSelectedVol(null); // close volunteer card
        setViewState({
          ...viewState,
          longitude: info.object.longitude,
          latitude: info.object.latitude,
          zoom: 7,
          transitionDuration: 800,
          transitionInterpolator: new FlyToInterpolator()
        });
        if (onHotspotClick) onHotspotClick(info.object as HeatmapPoint);
      }
    },
    transitions: { getRadius: { duration: 500, enter: () => [0] } }
  });

  // Volunteer layer - bigger colorful dots like proper pins
  const volLayer = new ScatterplotLayer({
    id: 'vol-layer',
    data: volunteerLocations,
    visible: showVolunteers,
    pickable: true,
    opacity: 1,
    stroked: true,
    filled: true,
    radiusScale: 1000,
    radiusMinPixels: 6,
    radiusMaxPixels: 14,
    lineWidthMinPixels: 2.5,
    getPosition: (d) => [d.longitude, d.latitude],
    getFillColor: [37, 99, 235, 240],   // vibrant blue
    getLineColor: [255, 255, 255, 255],
    getRadius: 8,
    onHover: (info) => {
      if (info.object) {
        setHoverInfo({ ...info, isVol: true });
      } else {
        setHoverInfo(null);
      }
    },
    onClick: (info) => {
      if (info.object) {
        setSelectedVol(info.object as VolunteerLocation);
        setVolCardPos({ x: info.x, y: info.y });
        // Fly to volunteer
        setViewState(v => ({
          ...v,
          longitude: info.object.longitude,
          latitude: info.object.latitude,
          zoom: 7,
          transitionDuration: 600,
          transitionInterpolator: new FlyToInterpolator()
        }));
      }
    },
    transitions: { getRadius: { duration: 500, enter: () => [0] } }
  });

  // Pulse animation layer for critical/high urgency needs
  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    let animationFrame: number;
    const start = Date.now();
    const animate = () => {
      const progress = ((Date.now() - start) % 2000) / 2000;
      setPulse(progress);
      animationFrame = requestAnimationFrame(animate);
    };
    animate();
    return () => cancelAnimationFrame(animationFrame);
  }, []);

  const criticalPoints = useMemo(() => points.filter(p => (p.urgency ?? 0) >= 0.7), [points]);

  const pulseLayer = new ScatterplotLayer({
    id: 'pulse-layer',
    data: criticalPoints,
    pickable: false,
    opacity: (1 - pulse) * 0.6,
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
      const baseR = d.affected_count ? Math.max(15, Math.log2(d.affected_count) * 9) : 15;
      return baseR + pulse * 35;
    },
    updateTriggers: { getRadius: [pulse], getLineColor: [pulse], opacity: [pulse] }
  });

  // Volunteer pulse layer (blue rings)
  const volPulseLayer = new ScatterplotLayer({
    id: 'vol-pulse-layer',
    data: showVolunteers ? volunteerLocations : [],
    pickable: false,
    opacity: (1 - pulse) * 0.5,
    stroked: true,
    filled: false,
    radiusScale: 1000,
    radiusMinPixels: 3,
    lineWidthMinPixels: 1.5,
    getPosition: (d) => [d.longitude, d.latitude],
    getLineColor: [37, 99, 235, Math.floor(255 * (1 - pulse))],
    getRadius: () => 8 + pulse * 20,
    updateTriggers: { getRadius: [pulse], getLineColor: [pulse], opacity: [pulse] }
  });

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState }) => setViewState(viewState as typeof INITIAL_VIEW_STATE)}
        controller={{ doubleClickZoom: false }}
        layers={[needsLayer, volLayer, pulseLayer, volPulseLayer]}
        getCursor={({ isHovering }) => isHovering ? 'pointer' : 'grab'}
        onClick={() => { if (selectedVol) setSelectedVol(null); }}
      >
        <Map mapStyle={MAP_STYLE} />
      </DeckGL>

      {/* Need hover tooltip */}
      {hoverInfo?.object && (
        <div style={{
          position: 'absolute', zIndex: 5, pointerEvents: 'none',
          left: hoverInfo.x, top: hoverInfo.y, transform: 'translate(-50%, -120%)',
          background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(20px)',
          padding: '12px 16px', borderRadius: 14,
          boxShadow: '0 12px 32px rgba(0,0,0,0.12)', border: '1px solid rgba(255,255,255,0.8)',
          fontFamily: 'var(--font-body)', minWidth: 190, maxWidth: 240
        }}>
          {hoverInfo.isVol ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#2563EB', flexShrink: 0 }} />
                <div style={{ fontSize: 13, fontWeight: 700 }}>{hoverInfo.object.name}</div>
              </div>
              <div style={{ fontSize: 11, color: '#64748B', lineHeight: 1.5 }}>{hoverInfo.object.skills?.join(' · ')}</div>
              <div style={{ fontSize: 10, color: '#94A3B8', marginTop: 4 }}>Click to see full profile</div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 10, fontWeight: 700, color: urgencyColor(hoverInfo.object.urgency ?? 0.5), textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
                {formatNeedType(hoverInfo.object.need_type)}
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#1C1917', marginBottom: 6, lineHeight: 1.3 }}>{hoverInfo.object.title}</div>
              <div style={{ fontSize: 12, color: '#64748B' }}>👥 {hoverInfo.object.affected_count || '?'} affected</div>
              <div style={{ fontSize: 10, color: '#94A3B8', marginTop: 4 }}>Click to see analytics</div>
            </>
          )}
          <div style={{ position: 'absolute', bottom: -7, left: '50%', transform: 'translateX(-50%) rotate(45deg)', width: 14, height: 14, background: 'rgba(255,255,255,0.92)', borderBottom: '1px solid rgba(0,0,0,0.05)', borderRight: '1px solid rgba(0,0,0,0.05)' }} />
        </div>
      )}

      {/* Volunteer Flashcard Popup */}
      {selectedVol && (
        <div style={{
          position: 'absolute', zIndex: 30,
          left: Math.min(volCardPos.x + 16, window ? window.innerWidth - 320 : volCardPos.x + 16),
          top: Math.max(volCardPos.y - 180, 16),
          width: 300,
          background: 'rgba(255,255,255,0.97)', backdropFilter: 'blur(24px)',
          borderRadius: 20, border: '1px solid rgba(255,255,255,0.8)',
          boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
          fontFamily: 'var(--font-body)',
          animation: 'volCardIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        }}>
          <style>{`@keyframes volCardIn { from { opacity:0; transform:scale(0.92) translateY(8px); } to { opacity:1; transform:scale(1) translateY(0); } }`}</style>
          
          {/* Header */}
          <div style={{ background: 'linear-gradient(135deg, #1E40AF, #2563EB)', padding: '20px 20px 16px', borderRadius: '20px 20px 0 0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ width: 48, height: 48, borderRadius: 14, background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 700, color: '#fff' }}>
                {selectedVol.name.charAt(0)}
              </div>
              <button onClick={() => setSelectedVol(null)} style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer', width: 28, height: 28, fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
            </div>
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>{selectedVol.name}</div>
              <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.75)', marginTop: 2 }}>
                {selectedVol.has_vehicle ? '🚗 Has vehicle · ' : ''}Volunteer
              </div>
            </div>
          </div>

          {/* Body */}
          <div style={{ padding: '16px 20px 20px' }}>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#94A3B8', marginBottom: 6 }}>Skills</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {selectedVol.skills?.map(skill => (
                  <span key={skill} style={{ background: '#EFF6FF', color: '#2563EB', fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 999 }}>{skill}</span>
                ))}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: selectedVol.status === 'available' ? '#10B981' : '#F59E0B', flexShrink: 0 }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#334155', textTransform: 'capitalize' }}>{selectedVol.status}</span>
            </div>
          </div>
        </div>
      )}
      
      {/* Zoom Controls */}
      <div style={{ position: 'absolute', bottom: 24, left: 24, display: 'flex', flexDirection: 'column', gap: 8, zIndex: 10 }}>
        {[
          { label: '+', action: () => setViewState(v => ({ ...v, zoom: v.zoom + 1, transitionDuration: 300, transitionInterpolator: new FlyToInterpolator() })) },
          { label: '−', action: () => setViewState(v => ({ ...v, zoom: v.zoom - 1, transitionDuration: 300, transitionInterpolator: new FlyToInterpolator() })) },
          { label: '↺', action: () => setViewState({ ...INITIAL_VIEW_STATE }) }
        ].map(({ label, action }) => (
          <button key={label} onClick={action}
            style={{ width: 40, height: 40, background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(12px)', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, cursor: 'pointer', boxShadow: '0 4px 16px rgba(0,0,0,0.08)', fontSize: label === '↺' ? 16 : 20, fontWeight: 500, color: '#334155', transition: 'all 150ms' }}
            onMouseEnter={e => e.currentTarget.style.background = '#F8FAFC'}
            onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.92)'}
          >{label}</button>
        ))}
      </div>
    </div>
  );
}
