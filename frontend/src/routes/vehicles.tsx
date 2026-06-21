import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { useRepeatOffenders, useVehicleHistory } from "@/lib/api-hooks";
import { timeAgo } from "@/lib/mock-data";
import { Eyebrow, Panel, PlateChip, SectionTitle, SeverityBadge } from "@/components/ui-bits";
import { Search, Car, Loader2, TrendingUp, AlertTriangle, Shield, Clock, MapPin, Filter } from "lucide-react";
import type { Severity } from "@/lib/mock-data";

export const Route = createFileRoute("/vehicles")({
  head: () => ({ meta: [{ title: "Vehicle Intelligence · GuardianEye" }] }),
  component: VehiclesPage,
});

// ── Rich fake vehicle registry ──────────────────────────────────────────────
const now = Date.now();
const ago = (h: number) => new Date(now - h * 3_600_000).toISOString();

type VehicleRecord = {
  plate: string;
  type: string;
  color: string;
  model: string;
  owner: string;
  risk: number;
  violations: number;
  top: string;
  lastSeen: string;
  firstFlagged: string;
  zone: string;
  status: "watchlist" | "challan_pending" | "repeat" | "cleared";
  history: { date: string; type: string; location: string; severity: Severity; fine: number }[];
};

const FAKE_VEHICLES: VehicleRecord[] = [
  {
    plate: "KA 03 HX 4412", type: "2-Wheeler", color: "Black", model: "Honda CB Shine",
    owner: "Rajesh Kumar", risk: 94, violations: 14, top: "Overspeeding",
    lastSeen: "Hebbal Flyover", firstFlagged: "12 Jan 2026", zone: "North", status: "watchlist",
    history: [
      { date: ago(1),   type: "Overspeeding",       location: "Hebbal Flyover",    severity: "high",   fine: 2000 },
      { date: ago(48),  type: "Red Light Jump",      location: "MG Road",           severity: "high",   fine: 1000 },
      { date: ago(120), type: "No Helmet",           location: "ORR Outer",         severity: "medium", fine: 500  },
      { date: ago(300), type: "Wrong-Side Driving",  location: "KR Puram",          severity: "high",   fine: 1000 },
      { date: ago(500), type: "Overspeeding",        location: "Silk Board Junction", severity: "high", fine: 2000 },
      { date: ago(900), type: "Triple Riding",       location: "Whitefield",        severity: "medium", fine: 500  },
    ],
  },
  {
    plate: "KA 05 MJ 7821", type: "4-Wheeler", color: "Silver", model: "Maruti Swift",
    owner: "Priya Sharma", risk: 81, violations: 9, top: "Red Light Jump",
    lastSeen: "MG Road × Brigade", firstFlagged: "3 Mar 2026", zone: "Central", status: "challan_pending",
    history: [
      { date: ago(8),   type: "Red Light Jump",   location: "MG Road × Brigade", severity: "high",   fine: 1000 },
      { date: ago(72),  type: "Overspeeding",     location: "Outer Ring Road",   severity: "medium", fine: 2000 },
      { date: ago(200), type: "Seatbelt Missing", location: "Koramangala",       severity: "low",    fine: 500  },
      { date: ago(400), type: "Red Light Jump",   location: "Indiranagar",       severity: "high",   fine: 1000 },
      { date: ago(650), type: "Red Light Jump",   location: "Shivajinagar",      severity: "high",   fine: 1000 },
    ],
  },
  {
    plate: "TN 22 AL 6610", type: "4-Wheeler", color: "White", model: "Toyota Innova",
    owner: "Suresh Babu", risk: 72, violations: 7, top: "Seatbelt Missing",
    lastSeen: "Electronic City Toll", firstFlagged: "28 Feb 2026", zone: "South", status: "repeat",
    history: [
      { date: ago(24),  type: "Seatbelt Missing",  location: "Electronic City",  severity: "low",    fine: 500  },
      { date: ago(96),  type: "Overspeeding",      location: "Hosur Road",       severity: "medium", fine: 2000 },
      { date: ago(180), type: "Seatbelt Missing",  location: "Bannerghatta Rd",  severity: "low",    fine: 500  },
      { date: ago(360), type: "Seatbelt Missing",  location: "NICE Road",        severity: "low",    fine: 500  },
    ],
  },
  {
    plate: "MH 12 EF 9012", type: "2-Wheeler", color: "Red", model: "Bajaj Pulsar 150",
    owner: "Amit Patel", risk: 88, violations: 11, top: "No Helmet",
    lastSeen: "Marathahalli Bridge", firstFlagged: "15 Feb 2026", zone: "East", status: "watchlist",
    history: [
      { date: ago(3),   type: "No Helmet",          location: "Marathahalli",    severity: "medium", fine: 500  },
      { date: ago(36),  type: "Triple Riding",       location: "Whitefield",      severity: "medium", fine: 500  },
      { date: ago(80),  type: "No Helmet",           location: "Varthur",         severity: "medium", fine: 500  },
      { date: ago(160), type: "Overspeeding",        location: "ORR East",        severity: "high",   fine: 2000 },
      { date: ago(310), type: "No Helmet",           location: "KR Puram",        severity: "medium", fine: 500  },
    ],
  },
  {
    plate: "KL 07 BG 2334", type: "Auto-Rickshaw", color: "Yellow", model: "Bajaj RE",
    owner: "Mohan Das", risk: 65, violations: 6, top: "Wrong-Side Driving",
    lastSeen: "Rajajinagar", firstFlagged: "5 Apr 2026", zone: "West", status: "challan_pending",
    history: [
      { date: ago(12),  type: "Wrong-Side Driving",  location: "Rajajinagar",     severity: "high",   fine: 1000 },
      { date: ago(100), type: "Wrong-Side Driving",  location: "Magadi Road",     severity: "high",   fine: 1000 },
      { date: ago(220), type: "Pedestrian Risk",     location: "Yeshwanthpur",    severity: "medium", fine: 500  },
      { date: ago(450), type: "No Helmet",           location: "Rajajinagar",     severity: "medium", fine: 500  },
    ],
  },
  {
    plate: "AP 09 BL 7711", type: "4-Wheeler", color: "Grey", model: "Hyundai Creta",
    owner: "Kavitha Reddy", risk: 58, violations: 5, top: "Overspeeding",
    lastSeen: "Sarjapur ORR", firstFlagged: "10 May 2026", zone: "East", status: "repeat",
    history: [
      { date: ago(18),  type: "Overspeeding",   location: "Sarjapur ORR",   severity: "high",   fine: 2000 },
      { date: ago(150), type: "Overspeeding",   location: "Whitefield",     severity: "high",   fine: 2000 },
      { date: ago(400), type: "Red Light Jump", location: "Varthur",        severity: "high",   fine: 1000 },
    ],
  },
  {
    plate: "KA 09 BC 1188", type: "2-Wheeler", color: "Blue", model: "TVS Apache",
    owner: "Vikram Singh", risk: 52, violations: 4, top: "No Helmet",
    lastSeen: "Koramangala 6th Block", firstFlagged: "1 May 2026", zone: "Central", status: "cleared",
    history: [
      { date: ago(60),  type: "No Helmet",      location: "Koramangala",    severity: "medium", fine: 500 },
      { date: ago(240), type: "Triple Riding",  location: "Indiranagar",    severity: "medium", fine: 500 },
      { date: ago(600), type: "No Helmet",      location: "BTM Layout",     severity: "medium", fine: 500 },
    ],
  },
  {
    plate: "KA 14 ZZ 0099", type: "Truck", color: "Blue", model: "Tata 407",
    owner: "Freight Star Logistics", risk: 79, violations: 8, top: "Overspeeding",
    lastSeen: "Hosur Road Bommasandra", firstFlagged: "20 Jan 2026", zone: "South", status: "repeat",
    history: [
      { date: ago(6),   type: "Overspeeding",       location: "Hosur Road",     severity: "high",   fine: 2000 },
      { date: ago(50),  type: "Wrong-Side Driving",  location: "Electronic City", severity: "high",  fine: 1000 },
      { date: ago(120), type: "Overspeeding",       location: "Sarjapur ORR",   severity: "high",   fine: 2000 },
      { date: ago(350), type: "Emergency Vehicle Blocked", location: "Silk Board", severity: "critical", fine: 5000 },
      { date: ago(700), type: "Overspeeding",       location: "Hosur Road",     severity: "high",   fine: 2000 },
    ],
  },
  {
    plate: "KA 51 PQ 9007", type: "2-Wheeler", color: "Green", model: "Ather 450X",
    owner: "Sneha Nair", risk: 34, violations: 3, top: "Red Light Jump",
    lastSeen: "Indiranagar 100ft Rd", firstFlagged: "15 May 2026", zone: "Central", status: "cleared",
    history: [
      { date: ago(80),  type: "Red Light Jump",  location: "Indiranagar", severity: "high",   fine: 1000 },
      { date: ago(300), type: "Red Light Jump",  location: "MG Road",     severity: "high",   fine: 1000 },
    ],
  },
  {
    plate: "DL 01 AB 2233", type: "4-Wheeler", color: "Black", model: "BMW 3 Series",
    owner: "Arjun Mehta", risk: 91, violations: 13, top: "Overspeeding",
    lastSeen: "Outer Ring Road E", firstFlagged: "8 Dec 2025", zone: "East", status: "watchlist",
    history: [
      { date: ago(2),   type: "Overspeeding",   location: "ORR East",      severity: "high",   fine: 2000 },
      { date: ago(24),  type: "Overspeeding",   location: "ORR East",      severity: "high",   fine: 2000 },
      { date: ago(72),  type: "Overspeeding",   location: "Marathahalli",  severity: "high",   fine: 2000 },
      { date: ago(144), type: "Red Light Jump", location: "KR Puram",      severity: "high",   fine: 1000 },
      { date: ago(288), type: "Accident Detected", location: "ORR East",   severity: "critical", fine: 5000 },
    ],
  },

  // ── Additional vehicles for rich search demo ─────────────────────────────
  {
    plate: "KA 19 MN 3344", type: "4-Wheeler", color: "White", model: "Mahindra Scorpio",
    owner: "Deepak Gowda", risk: 76, violations: 8, top: "Overspeeding",
    lastSeen: "Mysore Road Toll", firstFlagged: "22 Feb 2026", zone: "West", status: "repeat",
    history: [
      { date: ago(5),   type: "Overspeeding",      location: "Mysore Road",      severity: "high",   fine: 2000 },
      { date: ago(48),  type: "Overspeeding",      location: "NICE Road",        severity: "high",   fine: 2000 },
      { date: ago(120), type: "Seatbelt Missing",  location: "Bannerghatta Rd",  severity: "low",    fine: 500  },
      { date: ago(300), type: "Red Light Jump",    location: "Mysore Road",      severity: "high",   fine: 1000 },
    ],
  },
  {
    plate: "MH 01 CD 8899", type: "4-Wheeler", color: "Black", model: "Toyota Fortuner",
    owner: "Rajan Thakur", risk: 83, violations: 10, top: "Overspeeding",
    lastSeen: "Outer Ring Road E", firstFlagged: "10 Jan 2026", zone: "East", status: "watchlist",
    history: [
      { date: ago(2),   type: "Overspeeding",          location: "ORR East",       severity: "high",     fine: 2000 },
      { date: ago(30),  type: "Emergency Vehicle Blocked", location: "KR Puram",  severity: "critical", fine: 5000 },
      { date: ago(80),  type: "Overspeeding",          location: "Marathahalli",   severity: "high",     fine: 2000 },
      { date: ago(200), type: "Wrong-Side Driving",    location: "Whitefield",     severity: "high",     fine: 1000 },
      { date: ago(400), type: "Overspeeding",          location: "ORR East",       severity: "high",     fine: 2000 },
    ],
  },
  {
    plate: "DL 08 GH 5566", type: "4-Wheeler", color: "Silver", model: "Honda City",
    owner: "Anita Kapoor", risk: 47, violations: 4, top: "Seatbelt Missing",
    lastSeen: "MG Road", firstFlagged: "5 May 2026", zone: "Central", status: "challan_pending",
    history: [
      { date: ago(40),  type: "Seatbelt Missing",  location: "MG Road",      severity: "low",  fine: 500 },
      { date: ago(200), type: "Seatbelt Missing",  location: "Brigade Road",  severity: "low",  fine: 500 },
      { date: ago(500), type: "Red Light Jump",    location: "Indiranagar",  severity: "high", fine: 1000 },
    ],
  },
  {
    plate: "TN 09 PQ 1122", type: "2-Wheeler", color: "Blue", model: "Hero Splendor",
    owner: "Murugan S", risk: 61, violations: 6, top: "No Helmet",
    lastSeen: "Electronic City Phase 1", firstFlagged: "1 Mar 2026", zone: "South", status: "repeat",
    history: [
      { date: ago(10),  type: "No Helmet",    location: "Electronic City",  severity: "medium", fine: 500 },
      { date: ago(72),  type: "Triple Riding", location: "Hosur Road",      severity: "medium", fine: 500 },
      { date: ago(180), type: "No Helmet",    location: "Silk Board",       severity: "medium", fine: 500 },
      { date: ago(360), type: "No Helmet",    location: "Bommasandra",      severity: "medium", fine: 500 },
    ],
  },
  {
    plate: "RJ 14 WX 7788", type: "4-Wheeler", color: "White", model: "Tata Nexon",
    owner: "Sunita Joshi", risk: 38, violations: 3, top: "Overspeeding",
    lastSeen: "Bellary Road Corridor", firstFlagged: "18 May 2026", zone: "North", status: "cleared",
    history: [
      { date: ago(90),  type: "Overspeeding",   location: "Bellary Road",  severity: "medium", fine: 2000 },
      { date: ago(400), type: "Seatbelt Missing", location: "Yelahanka",   severity: "low",    fine: 500  },
    ],
  },
  {
    plate: "GJ 01 AB 4455", type: "4-Wheeler", color: "Red", model: "Kia Seltos",
    owner: "Nikhil Shah", risk: 55, violations: 5, top: "Red Light Jump",
    lastSeen: "Yeshwanthpur Junction", firstFlagged: "14 Apr 2026", zone: "North", status: "challan_pending",
    history: [
      { date: ago(14),  type: "Red Light Jump",    location: "Yeshwanthpur",  severity: "high",   fine: 1000 },
      { date: ago(72),  type: "Red Light Jump",    location: "Rajajinagar",   severity: "high",   fine: 1000 },
      { date: ago(200), type: "Overspeeding",      location: "Yeshwanthpur",  severity: "medium", fine: 2000 },
    ],
  },
  {
    plate: "KA 55 EF 6677", type: "2-Wheeler", color: "Orange", model: "Royal Enfield Bullet 350",
    owner: "Karthik Rao", risk: 70, violations: 7, top: "Overspeeding",
    lastSeen: "Indiranagar 100ft Rd", firstFlagged: "2 Mar 2026", zone: "Central", status: "repeat",
    history: [
      { date: ago(8),   type: "Overspeeding",     location: "Indiranagar",    severity: "high",   fine: 2000 },
      { date: ago(48),  type: "No Helmet",         location: "Koramangala",   severity: "medium", fine: 500  },
      { date: ago(120), type: "Overspeeding",     location: "Whitefield",     severity: "high",   fine: 2000 },
      { date: ago(300), type: "Wrong-Side Driving", location: "Indiranagar",  severity: "high",   fine: 1000 },
    ],
  },
  {
    plate: "UP 32 KL 9900", type: "Truck", color: "Blue", model: "Ashok Leyland Dost",
    owner: "Ram Prasad Yadav", risk: 85, violations: 9, top: "Overspeeding",
    lastSeen: "Hosur Road Bommasandra", firstFlagged: "5 Nov 2025", zone: "South", status: "watchlist",
    history: [
      { date: ago(3),   type: "Overspeeding",      location: "Hosur Road",    severity: "high",     fine: 2000 },
      { date: ago(36),  type: "Wrong-Side Driving", location: "Electronic City", severity: "high",  fine: 1000 },
      { date: ago(96),  type: "Emergency Vehicle Blocked", location: "Silk Board", severity: "critical", fine: 5000 },
      { date: ago(240), type: "Overspeeding",      location: "Hosur Road",    severity: "high",     fine: 2000 },
    ],
  },
  {
    plate: "HR 26 MN 2211", type: "4-Wheeler", color: "Grey", model: "Maruti Ertiga",
    owner: "Pooja Malhotra", risk: 42, violations: 3, top: "Seatbelt Missing",
    lastSeen: "Shivajinagar Bus Stand", firstFlagged: "20 May 2026", zone: "Central", status: "cleared",
    history: [
      { date: ago(60),  type: "Seatbelt Missing",  location: "Shivajinagar",  severity: "low",  fine: 500 },
      { date: ago(300), type: "Seatbelt Missing",  location: "MG Road",       severity: "low",  fine: 500 },
    ],
  },
  {
    plate: "WB 02 RS 3322", type: "4-Wheeler", color: "White", model: "Hyundai Venue",
    owner: "Aritra Dey", risk: 63, violations: 6, top: "Red Light Jump",
    lastSeen: "Hebbal Flyover", firstFlagged: "8 Mar 2026", zone: "North", status: "repeat",
    history: [
      { date: ago(20),  type: "Red Light Jump",   location: "Hebbal Flyover",   severity: "high",   fine: 1000 },
      { date: ago(80),  type: "Overspeeding",     location: "Bellary Road",     severity: "medium", fine: 2000 },
      { date: ago(200), type: "Red Light Jump",   location: "Yelahanka",        severity: "high",   fine: 1000 },
      { date: ago(450), type: "Pedestrian Risk",  location: "Thanisandra",      severity: "medium", fine: 500  },
    ],
  },
  {
    plate: "KA 41 UV 8833", type: "2-Wheeler", color: "White", model: "Honda Activa 6G",
    owner: "Lakshmi Devi", risk: 29, violations: 2, top: "No Helmet",
    lastSeen: "BTM Layout", firstFlagged: "10 Jun 2026", zone: "South", status: "cleared",
    history: [
      { date: ago(100), type: "No Helmet",  location: "BTM Layout",     severity: "medium", fine: 500 },
      { date: ago(500), type: "No Helmet",  location: "Jayanagar",      severity: "medium", fine: 500 },
    ],
  },
  {
    plate: "MH 43 ZA 6655", type: "Auto-Rickshaw", color: "Yellow", model: "Piaggio Ape",
    owner: "Santosh Kamble", risk: 68, violations: 7, top: "Wrong-Side Driving",
    lastSeen: "Koramangala 6th Block", firstFlagged: "15 Jan 2026", zone: "Central", status: "challan_pending",
    history: [
      { date: ago(15),  type: "Wrong-Side Driving", location: "Koramangala",   severity: "high",   fine: 1000 },
      { date: ago(60),  type: "Pedestrian Risk",    location: "BTM Layout",    severity: "medium", fine: 500  },
      { date: ago(150), type: "Wrong-Side Driving", location: "HSR Layout",    severity: "high",   fine: 1000 },
      { date: ago(350), type: "Red Light Jump",     location: "Koramangala",   severity: "high",   fine: 1000 },
    ],
  },
  {
    plate: "KA 02 XY 4499", type: "4-Wheeler", color: "Blue", model: "Ford EcoSport",
    owner: "Vinod Hegde", risk: 56, violations: 5, top: "Overspeeding",
    lastSeen: "Varthur Junction", firstFlagged: "20 Mar 2026", zone: "East", status: "repeat",
    history: [
      { date: ago(25),  type: "Overspeeding",     location: "Varthur",         severity: "medium", fine: 2000 },
      { date: ago(100), type: "Overspeeding",     location: "Sarjapur ORR",    severity: "medium", fine: 2000 },
      { date: ago(250), type: "Seatbelt Missing", location: "Whitefield",      severity: "low",    fine: 500  },
    ],
  },
  {
    plate: "DL 12 PQ 7711", type: "4-Wheeler", color: "Silver", model: "Suzuki Brezza",
    owner: "Rahul Verma", risk: 74, violations: 8, top: "Red Light Jump",
    lastSeen: "Airport Road Hebbal", firstFlagged: "5 Feb 2026", zone: "North", status: "watchlist",
    history: [
      { date: ago(6),   type: "Red Light Jump",  location: "Airport Road",    severity: "high",   fine: 1000 },
      { date: ago(40),  type: "Overspeeding",    location: "Hebbal Flyover",  severity: "high",   fine: 2000 },
      { date: ago(100), type: "Red Light Jump",  location: "Yelahanka",       severity: "high",   fine: 1000 },
      { date: ago(250), type: "Red Light Jump",  location: "Thanisandra",     severity: "high",   fine: 1000 },
      { date: ago(500), type: "Wrong-Side Driving", location: "Bellary Road", severity: "high",   fine: 1000 },
    ],
  },
  {
    plate: "KA 50 ST 1155", type: "4-Wheeler", color: "Black", model: "Tata Harrier",
    owner: "Shruthi Nambiar", risk: 89, violations: 12, top: "Overspeeding",
    lastSeen: "Sarjapur ORR Junction", firstFlagged: "20 Dec 2025", zone: "East", status: "watchlist",
    history: [
      { date: ago(1),   type: "Overspeeding",       location: "Sarjapur ORR",   severity: "high",     fine: 2000 },
      { date: ago(20),  type: "Accident Detected",  location: "Sarjapur ORR",   severity: "critical", fine: 5000 },
      { date: ago(96),  type: "Overspeeding",       location: "Varthur",         severity: "high",     fine: 2000 },
      { date: ago(200), type: "Wrong-Side Driving", location: "Marathahalli",    severity: "high",     fine: 1000 },
      { date: ago(400), type: "Overspeeding",       location: "ORR East",        severity: "high",     fine: 2000 },
      { date: ago(700), type: "Red Light Jump",     location: "Sarjapur",        severity: "high",     fine: 1000 },
    ],
  },
];


const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  watchlist:       { label: "🔴 Watchlist",       cls: "bg-rust/10 text-rust border-rust/25" },
  challan_pending: { label: "🟡 Challan Pending", cls: "bg-amber-flag/10 text-amber-flag border-amber-flag/25" },
  repeat:          { label: "🟠 Repeat Offender", cls: "bg-orange-500/10 text-orange-600 border-orange-400/25" },
  cleared:         { label: "🟢 Cleared",         cls: "bg-moss/10 text-moss border-moss/25" },
};

const VIOLATION_FINE: Record<string, number> = {
  "Overspeeding": 2000, "Red Light Jump": 1000, "No Helmet": 500,
  "Triple Riding": 500, "Seatbelt Missing": 500, "Wrong-Side Driving": 1000,
  "Pedestrian Risk": 500, "Emergency Vehicle Blocked": 5000, "Accident Detected": 5000,
};

const FILTERS = ["All", "Watchlist", "Repeat", "Challan Pending", "Cleared"] as const;

function VehiclesPage() {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<string>("All");
  const [selectedPlate, setSelectedPlate] = useState<string>(FAKE_VEHICLES[0].plate);

  // Try real API
  const { data: offendersData } = useRepeatOffenders(3, 50);
  const { data: historyData } = useVehicleHistory(q.length > 5 ? q : "");

  const dbOffenders: any[] = (offendersData as any)?.offenders ?? [];

  // Merge: DB offenders not already in fake list
  const allVehicles: VehicleRecord[] = useMemo(() => {
    const extra = dbOffenders
      .filter((o: any) => !FAKE_VEHICLES.find(f => f.plate === o.plate))
      .map((o: any) => ({
        plate: o.plate,
        type: "4-Wheeler",
        color: "Unknown",
        model: "Unknown",
        owner: "—",
        risk: o.risk ?? 50,
        violations: o.violations ?? 3,
        top: o.top ?? "Unknown",
        lastSeen: o.lastSeen ?? "—",
        firstFlagged: "—",
        zone: "—",
        status: "repeat" as const,
        history: [],
      }));
    return [...FAKE_VEHICLES, ...extra];
  }, [dbOffenders.length]);

  // Filter + search
  const filtered = useMemo(() => {
    let list = allVehicles;
    if (filter !== "All") {
      const key = filter.toLowerCase().replace(" ", "_");
      list = list.filter(v => v.status === key || (filter === "Repeat" && v.status === "repeat"));
    }
    if (q.length > 2) {
      const lower = q.toLowerCase();
      list = list.filter(v =>
        v.plate.toLowerCase().includes(lower) ||
        v.owner.toLowerCase().includes(lower) ||
        v.model.toLowerCase().includes(lower)
      );
    }
    return list.sort((a, b) => b.risk - a.risk);
  }, [q, filter, allVehicles]);

  const selected: VehicleRecord | undefined =
    filtered.find(v => v.plate === selectedPlate) ?? filtered[0];

  const totalFines = selected?.history.reduce((s, h) => s + (h.fine ?? 0), 0) ?? 0;

  return (
    <div className="p-5 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between flex-wrap gap-4">
        <SectionTitle
          eyebrow="Repeat offender intelligence"
          title="Vehicle lookup"
          sub="Search by plate, owner, or model. Click any row to view full profile."
        />
        {/* Summary badges */}
        <div className="flex gap-2 flex-wrap">
          {[
            { label: "Total tracked", val: allVehicles.length, cls: "bg-muted text-ink" },
            { label: "On watchlist",  val: allVehicles.filter(v => v.status === "watchlist").length, cls: "bg-rust/10 text-rust" },
            { label: "Pending challan", val: allVehicles.filter(v => v.status === "challan_pending").length, cls: "bg-amber-flag/10 text-amber-flag" },
          ].map(b => (
            <div key={b.label} className={`px-3 py-1.5 rounded-full text-[12px] font-medium ${b.cls} border border-current/20`}>
              <span className="font-display text-[16px] mr-1">{b.val}</span>{b.label}
            </div>
          ))}
        </div>
      </div>

      {/* Search + filter bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[220px] max-w-md">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search plate, owner, model…"
            className="w-full h-11 pl-11 pr-4 rounded-md border border-border bg-card text-[14px] font-mono tracking-wider focus:outline-none focus:ring-2 focus:ring-ring/30"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <Filter className="size-3.5 text-muted-foreground" />
          {FILTERS.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 h-9 rounded-md text-[12px] font-medium border transition-colors ${
                filter === f
                  ? "bg-ink text-paper border-ink"
                  : "bg-card border-border hover:bg-muted/50"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Vehicle profile (left) */}
        <div className="col-span-12 lg:col-span-8 space-y-5">
          {selected ? (
            <>
              {/* Profile card */}
              <Panel>
                <div className="flex items-start justify-between flex-wrap gap-4">
                  <div>
                    <Eyebrow>Subject vehicle</Eyebrow>
                    <div className="mt-3"><PlateChip plate={selected.plate} /></div>
                    <h2 className="font-display text-[34px] leading-tight mt-2 flex items-center gap-2">
                      <Car className="size-7 text-graphite" />
                      {selected.model}
                    </h2>
                    <p className="text-[13px] text-muted-foreground mt-1">
                      {selected.type} · {selected.color} · Owner: {selected.owner}
                    </p>
                    <div className={`mt-2 inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium border ${STATUS_BADGE[selected.status].cls}`}>
                      {STATUS_BADGE[selected.status].label}
                    </div>
                  </div>
                  <div className="text-right">
                    <Eyebrow>Risk score</Eyebrow>
                    <div className={`font-display text-[72px] leading-none mt-1 ${selected.risk >= 80 ? "text-rust" : selected.risk >= 60 ? "text-amber-flag" : "text-moss"}`}>
                      {selected.risk}
                    </div>
                    <div className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground">
                      {selected.risk >= 80 ? "high risk" : selected.risk >= 60 ? "medium risk" : "low risk"}
                    </div>
                  </div>
                </div>

                {/* Risk bar */}
                <div className="mt-4">
                  <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
                    <span>Risk level</span>
                    <span>{selected.risk}/100</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${selected.risk >= 80 ? "bg-rust" : selected.risk >= 60 ? "bg-amber-flag" : "bg-moss"}`}
                      style={{ width: `${selected.risk}%` }}
                    />
                  </div>
                </div>

                {/* Stats grid */}
                <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 pt-5 border-t border-border">
                  <Stat label="Total violations" value={String(selected.violations)} icon={<AlertTriangle className="size-3.5" />} />
                  <Stat label="Most common" value={selected.top} icon={<TrendingUp className="size-3.5" />} />
                  <Stat label="Last seen" value={selected.lastSeen} icon={<MapPin className="size-3.5" />} />
                  <Stat label="Total fines" value={`₹${totalFines.toLocaleString()}`} icon={<Shield className="size-3.5" />} />
                </div>
              </Panel>

              {/* Incident timeline */}
              <Panel inset={false}>
                <div className="p-5 pb-3 border-b border-border">
                  <SectionTitle eyebrow="History · timeline" title="Violation record" />
                  <p className="text-[12.5px] text-muted-foreground mt-1">
                    First flagged: {selected.firstFlagged} · Zone: {selected.zone}
                  </p>
                </div>
                <ol className="p-5 space-y-4">
                  {selected.history.length > 0 ? selected.history.map((h, i) => (
                    <li key={i} className="flex gap-4 pb-4 border-b border-border last:border-0 last:pb-0">
                      <div className="text-right shrink-0 w-28">
                        <div className="font-mono text-[11px] text-muted-foreground">{timeAgo(h.date)}</div>
                        <div className="font-mono text-[10px] text-muted-foreground">{new Date(h.date).toLocaleDateString("en-IN")}</div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <SeverityBadge severity={h.severity} />
                          <span className="font-display text-[15px]">{h.type}</span>
                          <span className="ml-auto font-mono text-[11px] text-rust">₹{h.fine?.toLocaleString()}</span>
                        </div>
                        <div className="text-[12px] text-muted-foreground mt-0.5 flex items-center gap-1">
                          <MapPin className="size-3" />{h.location}
                        </div>
                      </div>
                    </li>
                  )) : (
                    <li className="text-center py-8 text-muted-foreground text-[13px]">No violation history recorded</li>
                  )}
                </ol>
              </Panel>
            </>
          ) : (
            <Panel>
              <div className="p-12 text-center text-muted-foreground">
                <Car className="size-16 mx-auto mb-4 opacity-30" />
                <p className="text-[15px] font-medium">No results found</p>
                <p className="text-[12px] mt-1">Try a different search term or filter</p>
              </div>
            </Panel>
          )}
        </div>

        {/* Watchlist sidebar */}
        <div className="col-span-12 lg:col-span-4">
          <Panel inset={false}>
            <div className="p-4 pb-2 flex items-center justify-between">
              <Eyebrow>Vehicle roster</Eyebrow>
              <span className="font-mono text-[10.5px] text-muted-foreground">{filtered.length} records</span>
            </div>
            <div className="max-h-[700px] overflow-y-auto">
              {filtered.map(v => (
                <button
                  key={v.plate}
                  onClick={() => { setSelectedPlate(v.plate); }}
                  className={`w-full text-left px-4 py-3 border-t border-border hover:bg-muted/40 transition-colors ${
                    v.plate === selected?.plate ? "bg-muted/60 border-l-2 border-l-rust" : ""
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <PlateChip plate={v.plate} />
                    <span className={`font-display text-[18px] ${v.risk >= 80 ? "text-rust" : v.risk >= 60 ? "text-amber-flag" : "text-moss"}`}>
                      {v.risk}
                    </span>
                  </div>
                  <div className="mt-1 text-[11.5px] text-muted-foreground">{v.model} · {v.color}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[11px] text-muted-foreground">{v.violations} violations · {v.top}</span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-1 text-[10px] text-muted-foreground">
                    <Clock className="size-2.5" />
                    {timeAgo(v.history[0]?.date ?? new Date().toISOString())}
                  </div>
                  {/* Risk mini bar */}
                  <div className="mt-1.5 h-1 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${v.risk >= 80 ? "bg-rust" : v.risk >= 60 ? "bg-amber-flag" : "bg-moss"}`}
                      style={{ width: `${v.risk}%` }}
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

function Stat({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div>
      <Eyebrow className="flex items-center gap-1">
        {icon && <span className="text-muted-foreground">{icon}</span>}
        {label}
      </Eyebrow>
      <div className="font-display text-[18px] mt-1 leading-tight">{value}</div>
    </div>
  );
}
