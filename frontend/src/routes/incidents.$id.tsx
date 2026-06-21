import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import { useIncident, useUpdateIncidentStatus, useSendPoliceAlert, useSendHospitalAlert } from "@/lib/api-hooks";
import { api } from "@/lib/api-client";
import { Btn, Eyebrow, Panel, PlateChip, SectionTitle, SeverityBadge, StatusPill } from "@/components/ui-bits";
import { ArrowLeft, Download, Send, Ambulance, CheckCircle2, Loader2 } from "lucide-react";

export const Route = createFileRoute("/incidents/$id")({
  head: ({ params }) => ({ meta: [{ title: `${params.id} · GuardianEye` }] }),
  component: IncidentDetail,
  notFoundComponent: () => (
    <div className="p-12 text-center">
      <Eyebrow>404</Eyebrow>
      <h1 className="font-display text-[32px] mt-2">Incident not found</h1>
      <Link to="/violations" className="inline-block mt-4 text-rust underline">Back to violations</Link>
    </div>
  ),
});

const DETECTED_OBJECTS = [
  { label: "Vehicle · sedan", conf: 0.96 },
  { label: "Vehicle · 2-wheeler", conf: 0.89 },
  { label: "Person · rider", conf: 0.91 },
  { label: "Person · pedestrian", conf: 0.74 },
  { label: "Number plate", conf: 0.93 },
];

function IncidentDetail() {
  const { id } = Route.useParams();
  const { data: incidentData, isLoading } = useIncident(id);
  const updateStatusMutation = useUpdateIncidentStatus();
  const sendPoliceMutation = useSendPoliceAlert();
  const sendHospitalMutation = useSendHospitalAlert();
  const [note, setNote] = useState("");

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <Loader2 className="size-8 animate-spin text-rust mx-auto" />
          <p className="text-muted-foreground">Loading incident details...</p>
        </div>
      </div>
    );
  }

  const inc = incidentData?.incident;
  if (!inc) {
    throw notFound();
  }

  const handleDownloadEvidence = () => {
    // Prefer Cloudinary URL (full resolution, CDN-served)
    const cloudinaryUrl = inc.cloudinary_url;
    const localFilename = inc.evidence_image || inc.image;
    if (cloudinaryUrl) {
      window.open(cloudinaryUrl, '_blank');
    } else if (localFilename) {
      window.open(api.getEvidenceUrl(localFilename), '_blank');
    }
  };

  return (
    <div className="p-5 lg:p-8 space-y-6">
      <Link to="/violations" className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground hover:text-ink">
        <ArrowLeft className="size-3" /> Back to violations
      </Link>

      <header className="flex items-end justify-between gap-4 border-b border-border pb-5">
        <div>
          <Eyebrow>{inc.incident_id} · {inc.camera_id}</Eyebrow>
          <h1 className="font-display text-[42px] leading-tight mt-1">{inc.violation_type}</h1>
          <div className="mt-2 flex items-center gap-3 text-[13px] text-graphite">
            <SeverityBadge severity={inc.severity} />
            <StatusPill status={inc.status} />
            <span>{typeof inc.location === "object" ? inc.location?.name : inc.location}</span>
            <span>·</span>
            <span>{new Date(inc.timestamp).toLocaleString("en-IN")}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          <Btn variant="outline" onClick={handleDownloadEvidence} disabled={!inc.cloudinary_url && !inc.evidence_image && !inc.image}>
            <Download className="size-3.5" /> Evidence
          </Btn>
          <Btn variant="primary" onClick={() => sendPoliceMutation.mutate(inc.incident_id)} disabled={sendPoliceMutation.isPending}>
            <Send className="size-3.5" /> Police
          </Btn>
          <Btn variant="danger" onClick={() => sendHospitalMutation.mutate(inc.incident_id)} disabled={sendHospitalMutation.isPending}>
            <Ambulance className="size-3.5" /> Hospital
          </Btn>
          <Btn variant="outline" onClick={() => updateStatusMutation.mutate({ id: inc.incident_id, status: "resolved" })} disabled={updateStatusMutation.isPending}>
            <CheckCircle2 className="size-3.5" /> Resolve
          </Btn>
        </div>
      </header>

      <div className="grid grid-cols-12 gap-6">
        {/* Left main */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          <Panel inset={false} className="overflow-hidden">
            <div className="relative aspect-video bg-black flex items-center justify-center">
              <img
                src={
                  inc.cloudinary_url ||
                  (inc.evidence_image ? api.getEvidenceUrl(inc.evidence_image) : '/placeholder.svg')
                }
                className="size-full object-cover"
                alt="Evidence frame"
              />
              <div className="absolute inset-0 scanline opacity-30 pointer-events-none" />
              <div className="absolute bottom-3 left-3 flex items-center gap-2 font-mono text-[11px] text-paper bg-black/60 px-2 py-0.5 rounded">
                <span className="size-1.5 rounded-full bg-rust live-dot" />
                <span>EVIDENCE FRAME · {inc.incident_id}</span>
              </div>
            </div>
          </Panel>

          <Panel>
            <SectionTitle eyebrow="Forensics" title="Detected objects" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {DETECTED_OBJECTS.map(o => (
                <div key={o.label} className="flex items-center justify-between px-3 py-2 rounded border border-border bg-bone/40">
                  <span className="text-[13px]">{o.label}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1 rounded-full bg-muted overflow-hidden">
                      <div className="h-full bg-rust" style={{ width: `${o.conf * 100}%` }} />
                    </div>
                    <span className="font-mono text-[11px] text-muted-foreground w-9 text-right">{o.conf.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel>
            <SectionTitle eyebrow="Notes" title="Operator log" />
            <textarea value={note} onChange={e => setNote(e.target.value)}
              placeholder="Add an observation, link a case ID, attach an action…"
              className="w-full min-h-[100px] p-3 rounded border border-border bg-bone/40 text-[13px] resize-y focus:outline-none focus:ring-2 focus:ring-ring/30"/>
            <div className="mt-2 flex justify-between items-center">
              <span className="font-mono text-[10.5px] text-muted-foreground">Signed as A. Rao · Watch Commander</span>
              <Btn variant="primary" size="sm" onClick={() => { setNote(""); }}>Save note</Btn>
            </div>
          </Panel>
        </div>

        {/* Right rail */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <Panel>
            <Eyebrow>Vehicle</Eyebrow>
            <div className="mt-3 flex flex-col gap-3">
              <PlateChip plate={inc.license_plates?.[0] || "KA01AB1234"} />
              <Link to="/vehicles" className="text-[12.5px] text-rust hover:underline">Open vehicle history →</Link>
            </div>
          </Panel>

          <Panel>
            <Eyebrow>AI confidence</Eyebrow>
            <div className="mt-2 flex items-end gap-3">
              <div className="font-display text-[42px] leading-none">{Math.round((inc.confidence || 0.85) * 100)}<span className="text-muted-foreground text-[20px]">%</span></div>
              <div className="pb-2 font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground">model v2.3</div>
            </div>
            <div className="mt-3 h-1.5 rounded-full bg-muted overflow-hidden">
              <div className="h-full bg-ink" style={{ width: `${(inc.confidence || 0.85) * 100}%` }} />
            </div>
          </Panel>

          <Panel inset={false}>
            <div className="p-4 pb-2"><Eyebrow>Response timeline</Eyebrow></div>
            <ol>
              {["Detected on edge", "Verified · cloud", "Operator notified", "Alert dispatched", "Awaiting field"].map((s, i) => (
                <li key={s} className="px-4 py-2.5 border-t border-border flex items-center gap-3">
                  <span className={`size-1.5 rounded-full ${i < 3 ? "bg-rust" : "bg-muted"}`} />
                  <span className="text-[13px] flex-1">{s}</span>
                  <span className="font-mono text-[10.5px] text-muted-foreground">{i * 47}s</span>
                </li>
              ))}
            </ol>
          </Panel>

          <Panel>
            <Eyebrow>Status</Eyebrow>
            <select value={inc.status} onChange={e => updateStatusMutation.mutate({ id: inc.incident_id, status: e.target.value })}
              className="mt-2 w-full h-10 px-3 rounded border border-border bg-background text-[13px] capitalize">
              <option value="new">New</option>
              <option value="alert_sent">Alert sent</option>
              <option value="in_review">In review</option>
              <option value="resolved">Resolved</option>
            </select>
          </Panel>
        </div>
      </div>
    </div>
  );
}
