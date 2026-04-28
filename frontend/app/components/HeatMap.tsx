'use client';
import { useState, useMemo, useEffect } from 'react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer } from '@deck.gl/layers';
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

  const needsLayer = new ScatterplotLayer({
    id: 'needs-layer',
    data: points,
    pickable: true,
    opacity: 0.8,
    stroked: true,
    filled: true,
    radiusScale: 1000,
    radiusMinPixels: 4,
    radiusMaxPixels: 30,
    lineWidthMinPixels: 1,
    getPosition: (d) => [d.longitude, d.latitude],
    getFillColor: (d) => {
      const hex = urgencyColor(d.urgency ?? 0.5);
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return [r, g, b, 200];
    },
    getLineColor: (d) => [255, 255, 255, 255],
    getRadius: (d) => d.affected_count ? Math.max(15, Math.log2(d.affected_count) * 8) : 15,
    onHover: (info) => setHoverInfo(info),
    onClick: (info) => {
      if (info.object) {
        setViewState({
          ...viewState,
          longitude: info.object.longitude,
          latitude: info.object.latitude,
          zoom: 7,
          transitionDuration: 800,
          transitionInterpolator: new FlyToInterpolator()
        });
        if (onHotspotClick) {
          onHotspotClick(info.object as HeatmapPoint);
        }
      }
    },
    transitions: {
      getRadius: { duration: 500, enter: value => [0] }
    }
  });

  const volLayer = new ScatterplotLayer({
    id: 'vol-layer',
    data: volunteerLocations,
    visible: showVolunteers,
    pickable: true,
    opacity: 0.9,
    stroked: true,
    filled: true,
    radiusScale: 1000,
    radiusMinPixels: 2,
    radiusMaxPixels: 6,
    lineWidthMinPixels: 1,
    getPosition: (d) => [d.longitude, d.latitude],
    getFillColor: [37, 99, 235, 255], // #2563EB
    getLineColor: [255, 255, 255, 255],
    getRadius: 5,
    onHover: (info) => setHoverInfo({ ...info, isVol: true }),
    transitions: {
      getRadius: { duration: 500, enter: value => [0] }
    }
  });

  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    let animationFrame: number;
    let start = Date.now();
    const animate = () => {
      const now = Date.now();
      const progress = ((now - start) % 2000) / 2000;
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
    opacity: 1 - pulse,
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
      return [r, g, b, 255 * (1 - pulse)];
    },
    getRadius: (d) => {
      const baseR = d.affected_count ? Math.max(15, Math.log2(d.affected_count) * 8) : 15;
      return baseR + (pulse * 30);
    },
    updateTriggers: {
      getRadius: [pulse],
      getLineColor: [pulse],
      opacity: [pulse]
    }
  });

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState }) => setViewState(viewState)}
        controller={{ doubleClickZoom: false }}
        layers={[needsLayer, volLayer, pulseLayer]}
        getCursor={({ isHovering }) => isHovering ? 'pointer' : 'grab'}
      >
        <Map mapStyle={MAP_STYLE} />
      </DeckGL>

      {hoverInfo && hoverInfo.object && (
        <div style={{
          position: 'absolute', zIndex: 1, pointerEvents: 'none',
          left: hoverInfo.x, top: hoverInfo.y, transform: 'translate(-50%, -120%)',
          background: 'rgba(255, 255, 255, 0.85)', backdropFilter: 'blur(16px)',
          padding: '12px 16px', borderRadius: 12,
          boxShadow: '0 8px 32px rgba(0,0,0,0.1)', border: '1px solid rgba(255,255,255,0.6)',
          color: '#1C1917', fontFamily: 'var(--font-body)', minWidth: 180
        }}>
          {hoverInfo.isVol ? (
            <>
              <div style={{ fontSize: 13, fontWeight: 700 }}>{hoverInfo.object.name}</div>
              <div style={{ fontSize: 11, color: '#78716C', marginTop: 2 }}>{hoverInfo.object.skills.join(', ')}</div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 11, fontWeight: 700, color: urgencyColor(hoverInfo.object.urgency ?? 0.5), textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                {formatNeedType(hoverInfo.object.need_type)}
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>{hoverInfo.object.title}</div>
              <div style={{ fontSize: 12, color: '#57534E', display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ fontSize: 16 }}>👥</span> {hoverInfo.object.affected_count || 'Unknown'} affected
              </div>
            </>
          )}
          <div style={{
            position: 'absolute', bottom: -6, left: '50%', transform: 'translateX(-50%) rotate(45deg)',
            width: 12, height: 12, background: 'rgba(255, 255, 255, 0.85)',
            borderBottom: '1px solid rgba(255,255,255,0.6)', borderRight: '1px solid rgba(255,255,255,0.6)'
          }} />
        </div>
      )}
      
      {/* Zoom Controls */}
      <div style={{ position: 'absolute', bottom: 24, left: 24, display: 'flex', flexDirection: 'column', gap: 8, zIndex: 10 }}>
        <button onClick={() => setViewState(v => ({ ...v, zoom: v.zoom + 1, transitionDuration: 300, transitionInterpolator: new FlyToInterpolator() }))}
          style={{ width: 40, height: 40, background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,0.5)', borderRadius: 10, cursor: 'pointer', boxShadow: '0 4px 16px rgba(0,0,0,0.1)', fontSize: 18, fontWeight: 500 }}>+</button>
        <button onClick={() => setViewState(v => ({ ...v, zoom: v.zoom - 1, transitionDuration: 300, transitionInterpolator: new FlyToInterpolator() }))}
          style={{ width: 40, height: 40, background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,0.5)', borderRadius: 10, cursor: 'pointer', boxShadow: '0 4px 16px rgba(0,0,0,0.1)', fontSize: 18, fontWeight: 500 }}>-</button>
        <button onClick={() => setViewState({ ...INITIAL_VIEW_STATE })}
          style={{ width: 40, height: 40, background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,0.5)', borderRadius: 10, cursor: 'pointer', boxShadow: '0 4px 16px rgba(0,0,0,0.1)', fontSize: 16 }}>↺</button>
      </div>
    </div>
  );
}
