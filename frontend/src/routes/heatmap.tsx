import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useRef } from "react";
import { useCameras } from "@/lib/api-hooks";

import { Eyebrow, Panel, SectionTitle } from "@/components/ui-bits";
import { MapPin, AlertTriangle } from "lucide-react";


export const Route = createFileRoute("/heatmap")({
  head: () => ({ meta: [{ title: "Risk Map · GuardianEye" }] }),
  component: HeatmapPage,
});

// Declare Leaflet global types
declare global {
  interface Window {
    L: any;
  }
}

// Comprehensive risk zones across all of Bengaluru
const RISK_ZONES = [
  // === SOUTH BENGALURU ===
  { id: 1,  name: "Silk Board Junction",      lat: 12.9179, lng: 77.6229, risk: 94, violations: 412, color: '#CC0000', radius: 600 },
  { id: 2,  name: "BTM Layout",               lat: 12.9165, lng: 77.6101, risk: 81, violations: 310, color: '#FF1A1A', radius: 450 },
  { id: 3,  name: "Electronic City Phase 1",  lat: 12.8406, lng: 77.6771, risk: 72, violations: 238, color: '#FF4500', radius: 500 },
  { id: 4,  name: "Bannerghatta Road",        lat: 12.8916, lng: 77.5966, risk: 68, violations: 198, color: '#FF6600', radius: 420 },
  { id: 5,  name: "Jayanagar 4th Block",      lat: 12.9299, lng: 77.5827, risk: 55, violations: 145, color: '#FF8C00', radius: 350 },

  // === EAST BENGALURU ===
  { id: 6,  name: "Marathahalli Bridge",      lat: 12.9591, lng: 77.6974, risk: 89, violations: 376, color: '#CC0000', radius: 550 },
  { id: 7,  name: "Whitefield Main Road",     lat: 12.9698, lng: 77.7499, risk: 76, violations: 267, color: '#FF4500', radius: 480 },
  { id: 8,  name: "KR Puram Junction",        lat: 13.0050, lng: 77.6934, risk: 82, violations: 302, color: '#FF1A1A', radius: 500 },
  { id: 9,  name: "Outer Ring Road (ORR) E",  lat: 12.9762, lng: 77.7110, risk: 78, violations: 285, color: '#FF4500', radius: 520 },
  { id: 10, name: "Varthur Junction",         lat: 12.9352, lng: 77.7471, risk: 63, violations: 178, color: '#FF8C00', radius: 380 },

  // === NORTH BENGALURU ===
  { id: 11, name: "Hebbal Flyover",           lat: 13.0358, lng: 77.5970, risk: 88, violations: 361, color: '#CC0000', radius: 560 },
  { id: 12, name: "Yeshwanthpur Junction",    lat: 13.0228, lng: 77.5512, risk: 74, violations: 242, color: '#FF4500', radius: 440 },
  { id: 13, name: "Bellary Road Corridor",    lat: 13.0580, lng: 77.5971, risk: 67, violations: 193, color: '#FF6600', radius: 430 },
  { id: 14, name: "Yelahanka New Town",       lat: 13.1007, lng: 77.5963, risk: 58, violations: 162, color: '#FF8C00', radius: 390 },
  { id: 15, name: "Thanisandra Main Rd",      lat: 13.0590, lng: 77.6300, risk: 71, violations: 221, color: '#FF4500', radius: 410 },

  // === WEST BENGALURU ===
  { id: 16, name: "Rajajinagar Junction",     lat: 12.9921, lng: 77.5530, risk: 79, violations: 288, color: '#FF1A1A', radius: 460 },
  { id: 17, name: "Mysore Road Toll",         lat: 12.9523, lng: 77.5135, risk: 66, violations: 187, color: '#FF6600', radius: 420 },
  { id: 18, name: "Magadi Road",              lat: 12.9745, lng: 77.5287, risk: 61, violations: 171, color: '#FF8C00', radius: 390 },

  // === CENTRAL BENGALURU ===
  { id: 19, name: "Koramangala 6th Block",    lat: 12.9352, lng: 77.6245, risk: 73, violations: 234, color: '#FF4500', radius: 400 },
  { id: 20, name: "Indiranagar 100ft Rd",     lat: 12.9784, lng: 77.6408, risk: 65, violations: 189, color: '#FF8C00', radius: 370 },
  { id: 21, name: "MG Road",                  lat: 12.9757, lng: 77.6095, risk: 83, violations: 314, color: '#FF1A1A', radius: 480 },
  { id: 22, name: "Shivajinagar Bus Stand",   lat: 12.9870, lng: 77.6028, risk: 77, violations: 271, color: '#FF4500', radius: 430 },

  // === RING ROAD / PERIIPHERY ===
  { id: 23, name: "Sarjapur ORR Junction",    lat: 12.9010, lng: 77.6854, risk: 85, violations: 329, color: '#FF1A1A', radius: 530 },
  { id: 24, name: "Hosur Road Bommasandra",   lat: 12.8152, lng: 77.6887, risk: 69, violations: 204, color: '#FF6600', radius: 410 },
  { id: 25, name: "Airport Road Hebbal",      lat: 13.0428, lng: 77.6161, risk: 80, violations: 295, color: '#FF1A1A', radius: 490 },
];

// Top 5 for sidebar (sorted by risk)
const TOP_ZONES = [...RISK_ZONES].sort((a, b) => b.risk - a.risk).slice(0, 5);



function HeatmapPage() {
  const [selected, setSelected] = useState<any | null>(null);
  const [type, setType] = useState("all");
  const [range, setRange] = useState("24h");
  const [mapReady, setMapReady] = useState(false);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layersRef = useRef<any[]>([]);

  const { data: camerasData } = useCameras();

  const cameras = camerasData?.cameras || [];

  useEffect(() => {
    // Load Leaflet CSS
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(link);

    // Load Leaflet JS
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.async = true;
    script.onload = () => {
      if (!mapContainerRef.current || mapRef.current) return;
      initLeafletMap();
    };
    document.head.appendChild(script);

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  const initLeafletMap = () => {
    const L = window.L;
    if (!L || !mapContainerRef.current) return;

    // Create map centered on Bengaluru city
    const map = L.map(mapContainerRef.current, {
      center: [12.9716, 77.6200], // Bengaluru city centre
      zoom: 11,
      zoomControl: true,
      minZoom: 10,
    });

    mapRef.current = map;

    // OpenStreetMap tiles — no API key needed
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    // Collect all latlngs to fit bounds after adding all zones
    const allLatLngs: any[] = [];

    // Add risk zones
    RISK_ZONES.forEach(zone => {
      // Risk radius circle
      const circle = L.circle([zone.lat, zone.lng], {
        radius: zone.radius,
        color: zone.color,
        fillColor: zone.color,
        fillOpacity: 0.25,
        weight: 2,
        opacity: 0.8,
      }).addTo(map);

      // Custom marker SVG
      const markerIcon = L.divIcon({
        html: `
          <div style="
            width: 36px; height: 36px;
            background: ${zone.color};
            border: 3px solid white;
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-weight: 800; font-size: 13px; color: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.35);
            font-family: system-ui, sans-serif;
          ">${zone.risk}</div>`,
        className: '',
        iconSize: [36, 36],
        iconAnchor: [18, 18],
      });

      const marker = L.marker([zone.lat, zone.lng], { icon: markerIcon })
        .addTo(map)
        .on('click', () => setSelected(zone));

      // Tooltip on hover
      marker.bindTooltip(`
        <div style="font-family: system-ui, sans-serif; padding: 2px 4px;">
          <strong>${zone.name}</strong><br/>
          Risk: <strong>${zone.risk}/100</strong> · ${zone.violations} violations
        </div>
      `, { direction: 'top', offset: [0, -20] });

      allLatLngs.push([zone.lat, zone.lng]);
      layersRef.current.push(circle, marker);
    });

    // Fit map to encompass all risk zones with padding
    if (allLatLngs.length) {
      map.fitBounds(L.latLngBounds(allLatLngs), { padding: [40, 40], maxZoom: 12 });
    }

    setMapReady(true);
  };

  // NOTE: heatmap data is static (RISK_ZONES), don't block on backend loading

  return (
    <div className="p-5 lg:p-8 space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <Eyebrow>Spatial intelligence · Bengaluru pilot zone</Eyebrow>
          <h1 className="font-display text-[40px] leading-tight mt-1.5">Risk map</h1>
          <p className="text-[13.5px] text-muted-foreground mt-1 max-w-lg">
            Interactive map showing real-time risk zones based on violation density and severity across Bangalore.
          </p>
        </div>
        <div className="flex gap-2">
          <Select label="Type" value={type} onChange={setType} options={["all","No Helmet","Red Light","Overspeeding","Accident"]} />
          <Select label="Range" value={range} onChange={setRange} options={["1h","24h","7d","30d"]} />
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <Panel inset={false} className="col-span-12 lg:col-span-9 overflow-hidden">
          {/* Map loads into this div via Leaflet */}
          <div
            ref={mapContainerRef}
            id="leaflet-risk-map"
            style={{ width: '100%', height: '600px' }}
            className="rounded-lg overflow-hidden bg-bone"
          />
          {!mapReady && (
            <div className="absolute inset-0 flex items-center justify-center bg-bone/80 rounded-lg">
              <div className="text-center space-y-2">
                <div className="size-6 border-2 border-rust border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-[13px] text-muted-foreground">Loading map tiles…</p>
              </div>
            </div>
          )}
        </Panel>

        <div className="col-span-12 lg:col-span-3 space-y-4">
          <Panel>
            <SectionTitle eyebrow="Top 5 zones" title="Highest risk" />
            <div className="mt-4 space-y-3">
              {TOP_ZONES.map((zone, idx) => (
                <button
                  key={zone.id}
                  onClick={() => {
                    setSelected(zone);
                    // Fly to zone on map
                    if (mapRef.current) {
                      mapRef.current.flyTo([zone.lat, zone.lng], 14, { duration: 1 });
                    }
                  }}
                  className={`w-full text-left p-3 rounded-md border transition-colors ${
                    selected?.id === zone.id
                      ? 'border-rust bg-rust/5'
                      : 'border-border hover:bg-muted/40'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-display text-[18px]">{idx + 1}</span>
                      <MapPin className="size-3.5 text-rust" />
                      <span className="text-[13px] font-medium">{zone.name}</span>
                    </div>
                    <div
                      className="font-display text-[20px]"
                      style={{ color: zone.color }}
                    >
                      {zone.risk}
                    </div>
                  </div>
                  <div className="mt-1 ml-8 text-[11px] text-muted-foreground">
                    {zone.violations} violations · {range}
                  </div>
                  {/* mini risk bar */}
                  <div className="mt-2 ml-8 h-1 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${zone.risk}%`, background: zone.color }}
                    />
                  </div>
                </button>
              ))}
            </div>
          </Panel>

          {selected && (
            <Panel>
              <div className="flex items-center gap-2">
                <AlertTriangle className="size-4 text-rust" />
                <Eyebrow>Selected zone</Eyebrow>
              </div>
              <h3 className="font-display text-[20px] mt-2">{selected.name}</h3>
              <dl className="mt-3 space-y-2 text-[13px]">
                <Row label="Risk Score">
                  <div className="flex items-center gap-2">
                    <span className="font-display text-[18px]" style={{ color: selected.color }}>{selected.risk}</span>
                    <span className="text-[10px] text-muted-foreground">/ 100</span>
                  </div>
                </Row>
                <Row label="Violations">{selected.violations}</Row>
                <Row label="Radius">{selected.radius}m</Row>
                <Row label="Coordinates">
                  <span className="font-mono text-[10px]">
                    {selected.lat.toFixed(4)}, {selected.lng.toFixed(4)}
                  </span>
                </Row>
              </dl>

              <div className="mt-4 p-3 bg-rust/5 rounded-md border border-rust/20">
                <div className="text-[11px] font-medium text-rust mb-1">⚠️ Recommended Actions</div>
                <ul className="text-[11px] text-graphite space-y-1 ml-4">
                  <li>• Increase police patrol frequency</li>
                  <li>• Deploy speed cameras</li>
                  <li>• Enhanced signage required</li>
                </ul>
              </div>
            </Panel>
          )}

          <Panel>
            <Eyebrow>Coverage</Eyebrow>
            <div className="mt-2 font-display text-[28px] leading-tight">42<span className="text-muted-foreground text-[18px]"> km²</span></div>
            <div className="text-[12px] text-muted-foreground">{cameras.length || 5} cameras · 5 zones · 7d uptime 98.4%</div>

            <div className="mt-4 pt-3 border-t border-border">
              <div className="text-[11px] text-muted-foreground mb-2">Avg Risk by Time</div>
              <div className="space-y-1.5">
                <TimeRiskBar label="Morning (6-12)" risk={62} />
                <TimeRiskBar label="Afternoon (12-18)" risk={78} />
                <TimeRiskBar label="Evening (18-24)" risk={85} />
                <TimeRiskBar label="Night (0-6)" risk={45} />
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <label className="flex items-center gap-1.5">
      <span className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground">{label}</span>
      <select value={value} onChange={e => onChange(e.target.value)} className="h-9 px-2.5 rounded-md border border-border bg-card text-[12.5px]">
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

function Row({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
      <dt className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground">{label}</dt>
      <dd className={`capitalize ${className}`}>{children}</dd>
    </div>
  );
}

function TimeRiskBar({ label, risk }: { label: string; risk: number }) {
  const color = risk > 75 ? 'bg-rust' : risk > 60 ? 'bg-amber-flag' : 'bg-moss';
  return (
    <div>
      <div className="flex items-center justify-between text-[10px] mb-1">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono">{risk}</span>
      </div>
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${risk}%` }} />
      </div>
    </div>
  );
}
