import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useIncidents, useSendPoliceAlert, useSendHospitalAlert, useUpdateIncidentStatus } from "@/lib/api-hooks";
import { incidents as MOCK_INCIDENTS, timeAgo } from "@/lib/mock-data";
import { Btn, Eyebrow, Panel, PlateChip, SectionTitle, SeverityBadge } from "@/components/ui-bits";
import {
  Siren, MapPin, Building2, Phone, ChevronRight, CheckCircle2,
  Loader2, AlertTriangle, Clock, Users, Car, Radio
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

export const Route = createFileRoute("/accidents")({
  head: () => ({ meta: [{ title: "Emergency Response · GuardianEye" }] }),
  component: AccidentsPage,
});

const STAGES = [
  "Accident Detected",
  "Police Alert Sent",
  "Hospital Alert Sent",
  "Ambulance Assigned",
  "Help Dispatched",
  "Resolved",
] as const;

// Nearby emergency services keyed by general zone
const NEARBY: Record<string, { ps: string; psKm: string; hospital: string; hospKm: string; amb: string }> = {
  default:   { ps: "Madiwala PS",        psKm: "1.2 km",  hospital: "Apollo Hospitals",       hospKm: "2.8 km", amb: "KA-04-AMB-118" },
  South:     { ps: "Madiwala PS",        psKm: "1.2 km",  hospital: "Apollo Hospitals",       hospKm: "2.8 km", amb: "KA-04-AMB-118" },
  North:     { ps: "Hebbal PS",          psKm: "0.9 km",  hospital: "Columbia Asia Hebbal",   hospKm: "1.6 km", amb: "KA-09-AMB-212" },
  East:      { ps: "KR Puram PS",        psKm: "1.5 km",  hospital: "Manipal Whitefield",     hospKm: "3.2 km", amb: "KA-03-AMB-344" },
  Central:   { ps: "Cubbon Park PS",     psKm: "0.7 km",  hospital: "Bowring Hospital",       hospKm: "1.1 km", amb: "KA-01-AMB-077" },
};

function AccidentsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [stages, setStages] = useState<Record<string, number>>({});
  const [elapsed, setElapsed] = useState<Record<string, number>>({});

  // Try to fetch real accidents from DB
  const { data: incidentsData, isLoading } = useIncidents({ limit: 100 });
  const sendPolice = useSendPoliceAlert();
  const sendHospital = useSendHospitalAlert();
  const updateStatus = useUpdateIncidentStatus();

  // Pull real accident incidents OR fall back to mock
  const dbIncidents: any[] = (incidentsData as any)?.incidents ?? [];
  const dbAccidents = dbIncidents.filter(
    (i: any) => i.violation_type?.toLowerCase().includes("accident") || i.severity === "critical"
  );

  // Build unified accident list — real DB data first, then mock padding
  const mockAccidents = MOCK_INCIDENTS.filter(
    i => i.type === "Accident Detected" || i.severity === "critical"
  );

  // Merge: shape DB items to match display shape
  const accidents: any[] = [
    ...dbAccidents.map((i: any) => ({
      id: i.incident_id,
      _dbId: i.incident_id,
      type: i.violation_type?.replace(/_/g, " ") ?? "Accident Detected",
      severity: i.severity ?? "high",
      status: i.status ?? "new",
      location: i.location?.name ?? "Unknown",
      zone: "South",
      cameraId: i.camera_id,
      timestamp: i.timestamp,
      plate: i.license_plate ?? "KA-XX-XXXX",
      confidence: i.confidence ?? 0.85,
      vehicles: i.total_score ? Math.max(1, Math.round(i.total_score / 30)) : 2,
      people: 2,
      thumbnail: i.evidence_image
        ? api.getEvidenceUrl(i.evidence_image)
        : "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=70",
    })),
    ...mockAccidents.map(i => ({ ...i, _dbId: null })),
  ];

  const primary = accidents.find(a => a.id === selectedId) ?? accidents[0];

  // Auto-select first
  useEffect(() => {
    if (accidents.length && !selectedId) setSelectedId(accidents[0].id);
  }, [accidents.length]);

  // Initialize stage tracker for each case
  useEffect(() => {
    accidents.forEach(a => {
      if (!(a.id in stages)) {
        const initStage =
          a.status === "resolved" ? 5
          : a.status === "alert_sent" ? 2
          : a.status === "in_review" ? 3
          : 1;
        setStages(s => ({ ...s, [a.id]: initStage }));
        setElapsed(e => ({ ...e, [a.id]: Math.floor(Math.random() * 480 + 60) }));
      }
    });
  }, [accidents.length]);

  // Live clock for elapsed time
  useEffect(() => {
    const id = setInterval(() => {
      setElapsed(prev => {
        const next = { ...prev };
        Object.keys(next).forEach(k => { next[k] = (next[k] ?? 0) + 1; });
        return next;
      });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <Loader2 className="size-8 animate-spin text-rust mx-auto" />
          <p className="text-muted-foreground">Loading emergency incidents…</p>
        </div>
      </div>
    );
  }

  if (!primary) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <CheckCircle2 className="size-10 text-moss mx-auto" />
          <p className="text-[18px] font-display">No active accidents</p>
          <p className="text-muted-foreground text-[13px]">All clear — no accident incidents detected in the past 24 hours.</p>
        </div>
      </div>
    );
  }

  const stage = stages[primary.id] ?? 1;
  const secs = elapsed[primary.id] ?? 0;
  const mins = Math.floor(secs / 60);
  const ss = String(secs % 60).padStart(2, "0");
  const nearby = NEARBY[primary.zone] ?? NEARBY.default;

  return (
    <div className="p-5 lg:p-8 space-y-6">
      {/* Alert banner */}
      <div className="rounded-xl border border-rust/40 bg-rust/8 p-5 flex items-start gap-4 shadow-sm">
        <div className="size-11 rounded-full bg-rust text-paper grid place-items-center shrink-0 animate-pulse">
          <Siren className="size-5" />
        </div>
        <div className="flex-1 min-w-0">
          <Eyebrow className="text-rust">
            {accidents.length} active emergency {accidents.length === 1 ? "case" : "cases"}
            {dbAccidents.length > 0 && (
              <span className="ml-2 text-[10px] bg-rust/10 border border-rust/20 px-2 py-0.5 rounded-full">
                {dbAccidents.length} from AI detection
              </span>
            )}
          </Eyebrow>
          <h1 className="font-display text-[28px] lg:text-[32px] leading-tight mt-1 truncate">
            {primary.type} · {primary.location}
          </h1>
          <p className="text-[13px] text-graphite mt-1">
            Detected {timeAgo(primary.timestamp)} via camera {primary.cameraId}. {primary.people} people · {primary.vehicles} vehicles in frame.
          </p>
        </div>
        <div className="text-right shrink-0">
          <div className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground">Elapsed</div>
          <div className="font-display text-[36px] leading-none text-rust tabular-nums">
            {String(mins).padStart(2, "0")}:{ss}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Left: evidence + workflow */}
        <div className="col-span-12 lg:col-span-8 space-y-5">
          {/* Evidence image */}
          <Panel inset={false} className="overflow-hidden">
            <div className="relative aspect-video bg-black">
              <img
                src={primary.thumbnail}
                alt="Evidence"
                className="size-full object-cover"
                onError={e => {
                  (e.target as HTMLImageElement).src =
                    "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=70";
                }}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-ink/80 via-ink/20 to-transparent" />
              {/* HUD */}
              <div className="absolute top-4 left-4 flex items-center gap-2">
                <span className="size-1.5 rounded-full bg-rust animate-pulse" />
                <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-paper">LIVE · evidence frame</span>
              </div>
              <div className="absolute bottom-4 left-4 right-4 flex items-end justify-between text-paper">
                <div>
                  <SeverityBadge severity={primary.severity} label={primary.severity.toUpperCase()} />
                  <div className="font-display text-[24px] mt-2 leading-tight">{primary.type}</div>
                  <div className="font-mono text-[11px] text-paper/70 mt-0.5">{primary.id} · {primary.cameraId}</div>
                </div>
                <PlateChip plate={primary.plate} />
              </div>
            </div>

            {/* Stats row */}
            <div className="p-5 grid grid-cols-2 md:grid-cols-4 gap-4 border-t border-border">
              <Stat icon={<MapPin className="size-4" />} label="Location" value={primary.location} />
              <Stat icon={<Users className="size-4" />} label="People in frame" value={String(primary.people)} />
              <Stat icon={<Car className="size-4" />} label="Vehicles" value={String(primary.vehicles)} />
              <Stat icon={<Radio className="size-4" />} label="Confidence" value={`${Math.round((primary.confidence ?? 0.85) * 100)}%`} />
            </div>
          </Panel>

          {/* Response workflow */}
          <Panel>
            <SectionTitle eyebrow="Response workflow" title="Dispatch pipeline" />
            <ol className="relative mt-4">
              {STAGES.map((label, i) => {
                const done = i <= stage;
                const current = i === stage;
                return (
                  <li key={label} className="flex items-start gap-4 pb-5 last:pb-0 relative">
                    {i < STAGES.length - 1 && (
                      <span className={`absolute left-[11px] top-6 bottom-0 w-px transition-colors ${done ? "bg-rust" : "bg-border"}`} />
                    )}
                    <span className={`relative z-10 size-6 rounded-full border-2 grid place-items-center shrink-0 transition-all ${
                      done ? "bg-rust border-rust text-paper" : "border-border bg-paper"
                    }`}>
                      {done ? <CheckCircle2 className="size-3.5" /> : <span className="size-1.5 rounded-full bg-muted-foreground" />}
                    </span>
                    <div className="flex-1 pt-0.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className={`text-[14px] font-medium ${done ? "text-ink" : "text-muted-foreground"}`}>{label}</span>
                        {done && <span className="font-mono text-[10.5px] text-muted-foreground">{14 - i}:{String((i * 17) % 60).padStart(2, "0")} ago</span>}
                      </div>
                      {current && (
                        <p className="text-[12.5px] text-muted-foreground mt-1">Awaiting confirmation from dispatcher. ETA ~4 min.</p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
            <div className="mt-5 flex gap-2">
              <Btn variant="primary" onClick={() => {
                setStages(s => ({ ...s, [primary.id]: Math.min(STAGES.length - 1, (s[primary.id] ?? 1) + 1) }));
                if (primary._dbId) {
                  const nextStage = (stages[primary.id] ?? 1) + 1;
                  if (nextStage === 1) sendPolice.mutate(primary._dbId);
                  if (nextStage === 2) sendHospital.mutate(primary._dbId);
                }
                toast.success("Workflow advanced");
              }}>
                Advance stage <ChevronRight className="size-3.5" />
              </Btn>
              <Btn variant="outline" onClick={() => {
                setStages(s => ({ ...s, [primary.id]: STAGES.length - 1 }));
                if (primary._dbId) updateStatus.mutate({ id: primary._dbId, status: "resolved" });
                toast.success("Case marked resolved");
              }}>
                Mark Resolved
              </Btn>
            </div>
          </Panel>
        </div>

        {/* Right sidebar */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          {/* Nearest police */}
          <Panel>
            <Eyebrow>Nearest police station</Eyebrow>
            <div className="mt-3 flex items-start gap-3">
              <Building2 className="size-5 text-ink mt-0.5 shrink-0" />
              <div className="flex-1">
                <div className="font-display text-[18px] leading-tight">{nearby.ps}</div>
                <div className="text-[12.5px] text-muted-foreground">{nearby.psKm} · 4 patrol units active</div>
              </div>
              <Btn size="sm" variant="outline" onClick={() => toast.success(`Calling ${nearby.ps}…`)}>
                <Phone className="size-3" />
              </Btn>
            </div>
          </Panel>

          {/* Nearest hospital */}
          <Panel>
            <Eyebrow>Nearest hospital</Eyebrow>
            <div className="mt-3 flex items-start gap-3">
              <Building2 className="size-5 text-ink mt-0.5 shrink-0" />
              <div className="flex-1">
                <div className="font-display text-[18px] leading-tight">{nearby.hospital}</div>
                <div className="text-[12.5px] text-muted-foreground">{nearby.hospKm} · Trauma bay open</div>
              </div>
              <Btn size="sm" variant="outline" onClick={() => toast.success(`Calling ${nearby.hospital}…`)}>
                <Phone className="size-3" />
              </Btn>
            </div>
            <div className="mt-3 p-2.5 rounded bg-moss/10 border border-moss/20 text-[12px] text-moss">
              Ambulance {nearby.amb} dispatched · ETA ~4 min
            </div>
          </Panel>

          {/* All active cases */}
          <Panel inset={false}>
            <div className="p-4 pb-2 flex items-center justify-between">
              <Eyebrow>All active cases</Eyebrow>
              <span className="text-[11px] font-mono text-muted-foreground">{accidents.length} total</span>
            </div>
            <div className="max-h-[420px] overflow-y-auto">
              {accidents.map((a, idx) => (
                <button
                  key={a.id}
                  onClick={() => setSelectedId(a.id)}
                  className={`w-full text-left px-4 py-3 border-t border-border transition-colors hover:bg-muted/40 ${
                    selectedId === a.id ? "bg-rust/5 border-l-2 border-l-rust" : ""
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={a.severity} />
                    {a._dbId && (
                      <span className="text-[9px] font-mono bg-moss/10 text-moss border border-moss/20 px-1.5 py-0.5 rounded">AI</span>
                    )}
                    <span className="font-mono text-[10.5px] text-muted-foreground ml-auto">
                      {timeAgo(a.timestamp)}
                    </span>
                  </div>
                  <div className="text-[13px] font-medium mt-1.5 flex items-center gap-1.5">
                    <MapPin className="size-3 text-muted-foreground shrink-0" />
                    <span className="truncate">{a.location}</span>
                  </div>
                  <div className="font-mono text-[10.5px] text-muted-foreground mt-0.5">
                    {a.id} · {a.people} ppl · {a.vehicles} veh
                  </div>
                  {/* Workflow progress mini bar */}
                  <div className="mt-2 h-1 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-rust rounded-full transition-all"
                      style={{ width: `${((stages[a.id] ?? 1) / (STAGES.length - 1)) * 100}%` }}
                    />
                  </div>
                </button>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, icon }: { label: string; value: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div>
      <Eyebrow className="flex items-center gap-1">
        {icon && <span className="text-muted-foreground">{icon}</span>}
        {label}
      </Eyebrow>
      <div className="font-display text-[20px] mt-1 leading-tight">{value}</div>
    </div>
  );
}
