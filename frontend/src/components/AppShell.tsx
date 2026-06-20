import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard, Video, ShieldAlert, Siren, Bell, Map,
  Car, Settings as SettingsIcon, Search, CircleDot, Upload,
} from "lucide-react";
import { useEffect, useState } from "react";

const nav = [
  { to: "/", label: "Overview", icon: LayoutDashboard, kbd: "1" },
  { to: "/demo", label: "Live Demo", icon: Upload, kbd: "2" },
  { to: "/live", label: "Live Feeds", icon: Video, kbd: "3" },
  { to: "/violations", label: "Violations", icon: ShieldAlert, kbd: "4" },
  { to: "/accidents", label: "Emergency", icon: Siren, kbd: "5" },
  { to: "/alerts", label: "Alert Center", icon: Bell, kbd: "6" },
  { to: "/heatmap", label: "Risk Map", icon: Map, kbd: "7" },
  { to: "/vehicles", label: "Vehicles", icon: Car, kbd: "8" },
  { to: "/settings", label: "Settings", icon: SettingsIcon, kbd: "9" },
] as const;

export function AppShell() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [clock, setClock] = useState("");

  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setClock(
        d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) +
        " IST"
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-bone/60 paper-grain">
        <div className="px-5 pt-6 pb-5 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="relative">
              <div className="size-7 rounded-sm bg-ink flex items-center justify-center">
                <CircleDot className="size-3.5 text-paper" strokeWidth={2.5} />
              </div>
              <span className="absolute -right-0.5 -bottom-0.5 size-2 rounded-full bg-rust live-dot" />
            </div>
            <div className="leading-tight">
              <div className="font-display text-[19px]">GuardianEye</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Civic Vision · v0.9
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5">
          <div className="px-2 pb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Command
          </div>
          {nav.map((item) => {
            const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`group flex items-center gap-3 px-2.5 py-2 rounded-md text-[13.5px] transition-colors ${
                  active
                    ? "bg-ink text-paper"
                    : "text-graphite hover:bg-muted hover:text-ink"
                }`}
              >
                <Icon className="size-4" strokeWidth={1.8} />
                <span className="flex-1">{item.label}</span>
                <span className={`font-mono text-[10px] ${active ? "text-paper/60" : "text-muted-foreground"}`}>
                  {item.kbd}
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="px-4 py-3 border-t border-border">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Operator</div>
          <div className="mt-1.5 flex items-center gap-2.5">
            <div className="size-8 rounded-full bg-ink text-paper grid place-items-center text-xs font-medium">AR</div>
            <div className="leading-tight">
              <div className="text-[13px] font-medium">A. Rao</div>
              <div className="font-mono text-[10.5px] text-muted-foreground">Watch Commander</div>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-border bg-background/80 backdrop-blur sticky top-0 z-30">
          <div className="h-full px-5 flex items-center gap-5">
            <div className="hidden md:flex items-center gap-2 text-[12px] text-muted-foreground font-mono">
              <span className="size-1.5 rounded-full bg-moss inline-block" />
              <span>SYSTEM NOMINAL</span>
              <span className="text-border">/</span>
              <span>{cameras_online()} / 8 CAMERAS</span>
              <span className="text-border">/</span>
              <span>{clock}</span>
            </div>

            <div className="flex-1 max-w-xl mx-auto relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
              <input
                className="w-full h-9 pl-9 pr-20 rounded-md border border-border bg-card text-[13px] placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/30"
                placeholder="Search plate, incident, camera, location…"
              />
              <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-[10px] text-muted-foreground border border-border rounded px-1.5 py-0.5 bg-muted">
                ⌘K
              </kbd>
            </div>

            <div className="hidden md:flex items-center gap-2">
              <span className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground">Shift</span>
              <span className="text-[12px] font-medium">14:00 — 22:00</span>
            </div>
          </div>
        </header>

        <main className="flex-1 min-w-0">
          <Outlet />
        </main>

        <footer className="border-t border-border px-5 py-2.5 flex items-center justify-between font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground">
          <span>GuardianEye Civic Vision · Karnataka Pilot</span>
          <span>Frame buffer 24fps · Inference 38ms · Edge ⇄ Cloud OK</span>
        </footer>
      </div>
    </div>
  );
}

function cameras_online() {
  return 7;
}
