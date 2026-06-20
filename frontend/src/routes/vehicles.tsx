import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { timeAgo } from "@/lib/mock-data";
import { useRepeatOffenders, useVehicleHistory } from "@/lib/api-hooks";
import { Eyebrow, Panel, PlateChip, SectionTitle, SeverityBadge } from "@/components/ui-bits";
import { Search, Car, Loader2 } from "lucide-react";

export const Route = createFileRoute("/vehicles")({
  head: () => ({ meta: [{ title: "Vehicle Lookup · GuardianEye" }] }),
  component: VehiclesPage,
});

function VehiclesPage() {
  const [q, setQ] = useState("");

  const { data: offendersData, isLoading: offendersLoading } = useRepeatOffenders(3, 50);
  const { data: historyData, isLoading: historyLoading } = useVehicleHistory(q);

  const repeatOffenders = offendersData?.offenders || [];
  const v = q && historyData?.vehicle ? historyData.vehicle : (repeatOffenders[0] || null);

  if (offendersLoading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <Loader2 className="size-8 animate-spin text-rust mx-auto" />
          <p className="text-muted-foreground">Loading vehicle data...</p>
        </div>
      </div>
    );
  }

  // If no vehicle data, show empty state
  if (!v) {
    return (
      <div className="p-5 lg:p-8 space-y-6">
        <SectionTitle eyebrow="Repeat offender intelligence" title="Vehicle lookup" sub="Type a plate or pick from the watchlist." />
        
        <div className="relative max-w-2xl">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <input value={q} onChange={e => setQ(e.target.value)}
            placeholder="KA 05 MJ 7821"
            className="w-full h-12 pl-11 pr-4 rounded-md border border-border bg-card text-[15px] font-mono tracking-wider focus:outline-none focus:ring-2 focus:ring-ring/30" />
        </div>

        <Panel>
          <div className="p-12 text-center text-muted-foreground">
            <Car className="size-16 mx-auto mb-4 opacity-50" />
            <p className="text-[14px]">No vehicle data available</p>
            <p className="text-[12px] mt-1">Search for a license plate or add some violations to populate the watchlist</p>
          </div>
        </Panel>
      </div>
    );
  }

  return (
    <div className="p-5 lg:p-8 space-y-6">
      <SectionTitle eyebrow="Repeat offender intelligence" title="Vehicle lookup" sub="Type a plate or pick from the watchlist." />

      <div className="relative max-w-2xl">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <input value={q} onChange={e => setQ(e.target.value)}
          placeholder="KA 05 MJ 7821"
          className="w-full h-12 pl-11 pr-4 rounded-md border border-border bg-card text-[15px] font-mono tracking-wider focus:outline-none focus:ring-2 focus:ring-ring/30" />
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Profile */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          <Panel>
            <div className="flex items-start justify-between flex-wrap gap-4">
              <div>
                <Eyebrow>Subject vehicle</Eyebrow>
                <div className="mt-3"><PlateChip plate={v?.plate || 'UNKNOWN'} /></div>
                <h2 className="font-display text-[36px] leading-tight mt-3 flex items-center gap-2">
                  <Car className="size-7 text-graphite" /> {v?.plate || 'N/A'}
                </h2>
                <p className="text-[13px] text-muted-foreground mt-1">Type: 4-wheeler · Sedan (inferred) · Color: black</p>
              </div>
              <div className="text-right">
                <Eyebrow>Risk score</Eyebrow>
                <div className="font-display text-[68px] leading-none text-rust mt-1">{v?.risk || 0}</div>
                <div className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-rust">high risk · watchlist</div>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 pt-5 border-t border-border">
              <Stat label="Total violations" value={String(v?.violations || 0)} />
              <Stat label="Most common" value={v?.top || 'N/A'} />
              <Stat label="Last seen" value={v?.lastSeen || 'N/A'} />
              <Stat label="First flagged" value="14 May 2026" />
            </div>
          </Panel>

          <Panel inset={false}>
            <div className="p-5 pb-3 border-b border-border"><SectionTitle eyebrow="History · timeline" title="Previous incidents" /></div>
            <ol className="p-5 space-y-4">
              {(v?.history?.length ? v.history : Array.from({ length: 4 }).map((_, i) => ({
                date: new Date(Date.now() - (i + 1) * 86400000 * 3).toISOString(),
                type: ["Red Light Jump","Overspeeding","No Helmet","Wrong-Side Driving"][i],
                location: ["MG Road","ORR Outer","Hebbal Flyover","KR Puram"][i],
                severity: (["high","medium","high","medium"] as const)[i],
              }))).map((h: any, i: number) => (
                <li key={i} className="flex gap-4 pb-4 border-b border-border last:border-0 last:pb-0">
                  <div className="text-right shrink-0 w-24">
                    <div className="font-mono text-[11px] text-muted-foreground">{timeAgo(h.date)}</div>
                    <div className="font-mono text-[10.5px] text-muted-foreground">{new Date(h.date).toLocaleDateString("en-IN")}</div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2"><SeverityBadge severity={h.severity} /><span className="font-display text-[16px]">{h.type}</span></div>
                    <div className="text-[12.5px] text-muted-foreground mt-0.5">{h.location}</div>
                  </div>
                </li>
              ))}
            </ol>
          </Panel>
        </div>

        {/* Watchlist */}
        <div className="col-span-12 lg:col-span-4">
          <Panel inset={false}>
            <div className="p-4 pb-2"><Eyebrow>Watchlist · top offenders</Eyebrow></div>
            {repeatOffenders.length > 0 ? repeatOffenders.map((o: any) => (
              <button key={o.plate} onClick={() => setQ(o.plate)}
                className={`w-full text-left px-4 py-3 border-t border-border hover:bg-muted/40 ${o.plate === v?.plate ? "bg-muted/60" : ""}`}>
                <div className="flex items-center justify-between">
                  <PlateChip plate={o.plate} />
                  <span className="font-display text-[18px] text-rust">{o.risk}</span>
                </div>
                <div className="mt-1 text-[12px] text-muted-foreground">{o.violations} violations · {o.top}</div>
                <div className="font-mono text-[10.5px] text-muted-foreground mt-0.5">Last: {o.lastSeen}</div>
              </button>
            )) : (
              <div className="p-4 text-center text-muted-foreground text-[13px]">
                No repeat offenders yet
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <Eyebrow>{label}</Eyebrow>
      <div className="font-display text-[18px] mt-1 leading-tight">{value}</div>
    </div>
  );
}
