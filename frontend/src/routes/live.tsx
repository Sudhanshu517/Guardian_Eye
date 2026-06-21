import { createFileRoute } from "@tanstack/react-router";
import { useState, useRef, useEffect } from "react";
import { useCameras } from "@/lib/api-hooks";
import { Btn, Eyebrow, Panel, SectionTitle } from "@/components/ui-bits";
import { Maximize2, ShieldAlert, Send, FileText, Radio, Camera } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/live")({
  head: () => ({ meta: [{ title: "Live Feeds · GuardianEye" }] }),
  component: LivePage,
});

const BACKEND = "http://localhost:8000";

// 4 video-backed camera feeds
const VIDEO_FEEDS = [
  {
    id: "CAM-NE-01",
    name: "Silk Board Junction",
    zone: "South",
    status: "active",
    video: `${BACKEND}/videos/vid1.mp4`,
    detection: { type: "No Helmet", plate: "KA-01-AB-1234", confidence: 0.93, severity: "high",   vehicles: 3 },
  },
  {
    id: "CAM-NE-02",
    name: "Marathahalli Bridge",
    zone: "East",
    status: "active",
    video: `${BACKEND}/videos/vid2.mp4`,
    detection: { type: "Red Light Jump", plate: "KA-05-CD-5678", confidence: 0.87, severity: "high",   vehicles: 5 },
  },
  {
    id: "CAM-SW-03",
    name: "Hebbal Flyover",
    zone: "North",
    status: "warning",
    video: `${BACKEND}/videos/vid3.mp4`,
    detection: { type: "Overspeeding",   plate: "MH-12-EF-9012", confidence: 0.81, severity: "medium", vehicles: 2 },
  },
  {
    id: "CAM-SW-04",
    name: "Electronic City Ph-1",
    zone: "South",
    status: "active",
    video: `${BACKEND}/videos/vid4.mp4`,
    detection: { type: "Wrong Lane",     plate: "KA-03-GH-3456", confidence: 0.76, severity: "medium", vehicles: 4 },
  },
];

const STATUS_DOT: Record<string, string> = {
  active:  "bg-moss",
  warning: "bg-amber-flag",
  offline: "bg-rust",
};

const SEV_COLOR: Record<string, string> = {
  high:   "text-rust bg-rust/10 border-rust/25",
  medium: "text-amber-flag bg-amber-flag/10 border-amber-flag/25",
  low:    "text-moss bg-moss/10 border-moss/25",
};

function LivePage() {
  const [selectedId, setSelectedId] = useState(VIDEO_FEEDS[0].id);
  const mainVideoRef = useRef<HTMLVideoElement>(null);
  const { data: camerasData } = useCameras();

  const selected = VIDEO_FEEDS.find(f => f.id === selectedId)!;

  // When selected feed changes, reload and play the video
  useEffect(() => {
    if (mainVideoRef.current) {
      mainVideoRef.current.load();
      mainVideoRef.current.play().catch(() => {});
    }
  }, [selectedId]);

  return (
    <div className="p-5 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <Eyebrow>Camera grid · {VIDEO_FEEDS.length} feeds active</Eyebrow>
          <h1 className="font-display text-[40px] leading-tight mt-1.5">Live monitoring</h1>
          <p className="text-[13.5px] text-muted-foreground mt-1 max-w-lg">
            Real-time footage from deployed cameras. AI violations are flagged within 200ms of detection at the edge.
          </p>
        </div>
        <div className="flex items-center gap-4 font-mono text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-moss animate-pulse" />active</span>
          <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-amber-flag" />warning</span>
          <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-rust" />offline</span>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Main feed */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          <div className="relative rounded-xl overflow-hidden border border-border bg-black shadow-lg">
            {/* Live badge */}
            <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
              <span className="flex items-center gap-1.5 bg-rust text-white text-[10px] font-bold px-2.5 py-1 rounded-full tracking-wider">
                <span className="size-1.5 rounded-full bg-white animate-pulse" />
                LIVE
              </span>
              <span className="bg-black/60 text-white text-[11px] px-2.5 py-1 rounded-full font-mono backdrop-blur-sm">
                {selected.id} · {selected.name}
              </span>
            </div>

            {/* Fullscreen button */}
            <div className="absolute top-3 right-3 z-10">
              <button
                onClick={() => mainVideoRef.current?.requestFullscreen()}
                className="bg-black/60 hover:bg-black/80 text-white rounded-lg p-2 backdrop-blur-sm transition-colors"
              >
                <Maximize2 className="size-4" />
              </button>
            </div>

            {/* Detection overlay badge */}
            <div className="absolute bottom-3 left-3 z-10">
              <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-full border backdrop-blur-sm ${SEV_COLOR[selected.detection.severity]}`}>
                <Radio className="size-3 animate-pulse" />
                {selected.detection.type} · {Math.round(selected.detection.confidence * 100)}% conf.
              </span>
            </div>

            {/* Timestamp */}
            <div className="absolute bottom-3 right-3 z-10">
              <span className="bg-black/60 text-white/70 text-[10px] font-mono px-2 py-1 rounded backdrop-blur-sm">
                <LiveClock />
              </span>
            </div>

            {/* VIDEO ELEMENT */}
            <video
              ref={mainVideoRef}
              key={selected.video}   /* force re-mount on src change */
              src={selected.video}
              autoPlay
              loop
              muted
              playsInline
              className="w-full aspect-video object-cover"
              style={{ maxHeight: 520 }}
            />
          </div>

          {/* Thumbnail strip */}
          <div className="grid grid-cols-4 gap-3">
            {VIDEO_FEEDS.map(feed => (
              <button
                key={feed.id}
                onClick={() => setSelectedId(feed.id)}
                className={`relative rounded-lg overflow-hidden border transition-all ${
                  selectedId === feed.id
                    ? "border-rust ring-2 ring-rust/30 shadow-md"
                    : "border-border hover:border-graphite/60"
                }`}
              >
                <video
                  src={feed.video}
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="w-full aspect-video object-cover"
                />
                {/* Status dot */}
                <div className="absolute top-1.5 left-1.5">
                  <span className={`size-2 rounded-full ${STATUS_DOT[feed.status]} block ${feed.status === 'active' ? 'animate-pulse' : ''}`} />
                </div>
                {/* Camera name overlay */}
                <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent px-2 py-1.5">
                  <p className="text-white text-[9px] font-mono truncate">{feed.id}</p>
                  <p className="text-white/70 text-[9px] truncate">{feed.name}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Side panel */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          {/* Detection card */}
          <Panel>
            <Eyebrow>Active detection</Eyebrow>
            <h3 className="font-display text-[22px] mt-1 leading-tight">{selected.detection.type}</h3>
            <div className="mt-2 flex items-center gap-2">
              <span className={`text-[11px] font-medium px-2 py-0.5 rounded border ${SEV_COLOR[selected.detection.severity]}`}>
                {selected.detection.severity.toUpperCase()}
              </span>
              <span className="font-mono text-[11px] text-muted-foreground">
                {Math.round(selected.detection.confidence * 100)}% confidence
              </span>
            </div>

            <dl className="mt-4 space-y-2.5 text-[13px]">
              <Row label="Vehicles">{selected.detection.vehicles} detected</Row>
              <Row label="Number Plate">
                <span className="font-mono text-[11.5px] bg-muted px-2 py-0.5 rounded border border-border">
                  {selected.detection.plate}
                </span>
              </Row>
              <Row label="Camera">{selected.id}</Row>
              <Row label="Zone">{selected.zone}</Row>
              <Row label="Frame ID">
                <span className="font-mono text-[11px]">F-{Math.floor(Math.random() * 9e6 + 1e6)}</span>
              </Row>
            </dl>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <Btn
                variant="primary"
                onClick={() => toast.success("Police alert dispatched", {
                  description: `${selected.detection.type} at ${selected.name}`
                })}
              >
                <Send className="size-3.5" /> Send Alert
              </Btn>
              <Btn variant="outline">
                <FileText className="size-3.5" /> Open Case
              </Btn>
            </div>
          </Panel>

          {/* Recommended action */}
          <Panel>
            <SectionTitle eyebrow="Recommendation" title="Suggested action" />
            <div className="flex gap-3 text-[13px] mt-2">
              <ShieldAlert className="size-4 text-rust mt-0.5 shrink-0" />
              <p className="text-graphite leading-relaxed">
                Issue e-challan to{" "}
                <span className="font-medium">{selected.detection.plate}</span>{" "}
                under section 194D MV Act. Dispatch nearest patrol unit (PCR-12, ETA 3 min).
              </p>
            </div>
          </Panel>

          {/* Camera roster */}
          <Panel inset={false}>
            <div className="p-4 pb-2 flex items-center gap-2">
              <Camera className="size-3.5 text-muted-foreground" />
              <Eyebrow>Camera roster</Eyebrow>
            </div>
            <div>
              {VIDEO_FEEDS.map(feed => (
                <button
                  key={feed.id}
                  onClick={() => setSelectedId(feed.id)}
                  className={`w-full px-4 py-2.5 border-t border-border text-left flex items-center gap-3 hover:bg-muted/50 transition-colors ${
                    selectedId === feed.id ? "bg-muted" : ""
                  }`}
                >
                  <span className={`size-1.5 rounded-full ${STATUS_DOT[feed.status]} shrink-0 ${feed.status === 'active' ? 'animate-pulse' : ''}`} />
                  <span className="font-mono text-[11px] text-muted-foreground w-20 shrink-0">{feed.id}</span>
                  <span className="flex-1 text-[12.5px] truncate">{feed.name}</span>
                  <span className="font-mono text-[10.5px] text-muted-foreground">{feed.zone}</span>
                </button>
              ))}
              {/* Extra cameras from DB (offline) */}
              {camerasData?.cameras?.filter(c => !VIDEO_FEEDS.find(f => f.id === c.camera_id)).slice(0, 4).map(c => (
                <div
                  key={c.camera_id}
                  className="w-full px-4 py-2.5 border-t border-border flex items-center gap-3 opacity-50"
                >
                  <span className="size-1.5 rounded-full bg-rust shrink-0" />
                  <span className="font-mono text-[11px] text-muted-foreground w-20 shrink-0">{c.camera_id}</span>
                  <span className="flex-1 text-[12.5px] truncate">{c.name}</span>
                  <span className="font-mono text-[10.5px] text-muted-foreground">offline</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

/** Ticking real-time clock for the HUD overlay */
function LiveClock() {
  const [time, setTime] = useState(() => new Date().toLocaleTimeString());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(id);
  }, []);
  return <>{time}</>;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 border-b border-border last:border-0">
      <dt className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground shrink-0">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}
