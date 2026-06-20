# GuardianEye - System Diagrams & Flow

Visual representation of how GuardianEye works.

---

## 🏗️ **High-Level Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                        GUARDIANEYE SYSTEM                        │
└─────────────────────────────────────────────────────────────────┘

                            INPUT LAYER
    ┌────────────────────────────────────────────────────┐
    │         📹 Traffic Cameras (8 locations)           │
    │    Capturing images/video at traffic junctions    │
    └─────────────────┬──────────────────────────────────┘
                      │
                      │ Image/Video Stream
                      ▼
                 AI/ML LAYER
    ┌────────────────────────────────────────────────────┐
    │           YOLOv8 Detection Models                  │
    │  ─────────────────────────────────────────────     │
    │  • Helmet Detection Model                          │
    │  • Red Light Detection Model                       │
    │  • License Plate OCR Model                         │
    │  • Wrong Way Detection Model                       │
    │  • Accident Detection Model.                       │
    │  • Severity Scoring Algorithm                      │
    └─────────────────┬──────────────────────────────────┘
                      │
                      │ JSON Output
                      ▼
               BACKEND LAYER
    ┌────────────────────────────────────────────────────┐
    │         ⚙️ FastAPI + MongoDB Backend               │
    │  ─────────────────────────────────────────────    │
    │  Services:                                        │
    │  • Incident Management                            │
    │  • Alert Dispatch                                 │
    │  • Analytics Calculation                          │
    │  • Offender Tracking                              │
    │  • Camera Monitoring                              │
    │                                                    │
    │  Storage:                                         │
    │  • MongoDB (incidents, alerts, cameras)           │
    │  • File System (evidence images)                  │
    └─────────────────┬──────────────────────────────────┘
                      │
                      │ REST API
                      ▼
              FRONTEND LAYER
    ┌────────────────────────────────────────────────────┐
    │         🎨 React Dashboard                         │
    │  ─────────────────────────────────────────────    │
    │  Pages:                                           │
    │  • Overview Dashboard                             │
    │  • Violations Management                          │
    │  • Alert Center                                   │
    │  • Heatmap Visualization                          │
    │  • Vehicle Search                                 │
    │  • Incident Details                               │
    └─────────────────┬──────────────────────────────────┘
                      │
                      │ Alert Dispatch.
                      ▼
               OUTPUT LAYER
    ┌────────────────────────────────────────────────────┐
    │         📤 Alert Distribution                      │
    │  ─────────────────────────────────────────────    │
    │  • 🚔 Police Stations (SMS/WhatsApp)              │
    │  • 🏥 Hospital Emergency (Alert System)           │
    │  • 🚑 Ambulance Service (GPS Routing)             │
    │  • 📧 Admin Notifications                         │
    └────────────────────────────────────────────────────┘
```

---

## 🔄 **Data Flow - Normal Violation**

```
Step 1: DETECTION
┌─────────────┐
│   Camera    │  Captures image of traffic violation
│   📹 CAM001 │  (e.g., rider without helmet)
└──────┬──────┘
       │ Image Frame
       ▼
┌─────────────┐
│  AI Model   │  Detects: Helmet violation
│   🤖 YOLO   │  Confidence: 91%
└──────┬──────┘  Class: driver (no helmet)
       │
       │ JSON Output
       ▼

Step 2: BACKEND PROCESSING
┌────────────────────────────────────────────┐
│  POST /api/incidents/                      │
│  {                                         │
│    "camera_id": "CAM001",                  │
│    "timestamp": "2026-06-18 06:48:46",     │
│    "violations": [{                        │
│      "type": "helmet",                     │
│      "confidence": 0.91,                   │
│      "score": 5                            │
│    }],                                     │
│    "license_plates": ["DL3C1234"]          │
│  }                                         │
└────────┬───────────────────────────────────┘
         │
         ▼
    ┌────────┐
    │MongoDB │  Creates incident: INC-20260618-1234
    │        │  Status: new
    └────┬───┘  Severity: medium
         │
         ├─→ Updates camera last_seen
         ├─→ Tracks offender (DL3C1234)
         └─→ Calculates statistics
         │
         ▼

Step 3: FRONTEND DISPLAY
┌─────────────────────────────────────────────┐
│  Dashboard (Real-time update)               │
│  ┌───────────────────────────────────────┐ │
│  │ 📊 Violations Today: 1,285 (+1)       │ │
│  │ 🚨 High Severity: 47                  │ │
│  │ 📈 Trend: ↑ 12% vs yesterday         │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  Recent Incidents:                          │
│  ┌───────────────────────────────────────┐ │
│  │ INC-1234 | Helmet | DL3C1234 | 🟡 Med│ │
│  │ 2 seconds ago | Delhi, Rajiv Chowk   │ │
│  │ [Alert] [View] [Resolve]             │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘

Step 4: OPERATOR ACTION
┌─────────────────┐
│ Operator clicks │  POST /api/alerts/send-police
│  "Send Alert"   │  ?incident_id=INC-1234
└────────┬────────┘
         │
         ▼
    ┌────────┐
    │Backend │  Creates alert: ALR-20260618-5678
    │   ⚙️   │  Generates message
    └────┬───┘  Marks incident: alert_sent
         │
         ▼
┌────────────────────────────────────────────┐
│  📱 SMS to Police                          │
│  ─────────────────────────────────────    │
│  🚨 GUARDIANEYE ALERT - MEDIUM             │
│                                            │
│  Violation: Helmet non-compliance          │
│  Location: Rajiv Chowk, Delhi              │
│  Vehicle: DL3C1234                         │
│  Time: 2026-06-18 06:48:46                │
│                                            │
│  Action: Issue challan                     │
│  Evidence: [Link to image]                 │
│  ID: INC-1234                              │
└────────────────────────────────────────────┘
```

---

## 🚑 **Data Flow - Accident (Life-Saving)**

```
Step 1: CRITICAL DETECTION
┌─────────────┐
│   Camera    │  Detects accident scene
│   📹 CAM003 │  Multiple vehicles stopped
└──────┬──────┘  Debris visible
       │
       ▼
┌─────────────┐
│  AI Model   │  Detects: ACCIDENT
│   🤖 YOLO   │  Severity: CRITICAL ⚠️
└──────┬──────┘  Confidence: 95%
       │
       │ < 1 second
       ▼

Step 2: INSTANT PROCESSING
┌────────────────────────────────────────────┐
│  Backend receives JSON                     │
│  ─────────────────────────────────────     │
│  • Identifies: violation_type = "accident" │
│  • Severity: CRITICAL                      │
│  • Score: 50+ (triggers auto-alert)        │
│  • Location: MG Road Junction              │
└────────┬───────────────────────────────────┘
         │
         │ < 1 second
         ▼
    ┌────────┐
    │Backend │  Creates incident: INC-ACC-1234
    │  ⚡    │  Status: new
    └────┬───┘  AUTO-TRIGGERS ALERTS
         │
         │ < 1 second
         ▼

Step 3: AUTOMATIC MULTI-ALERT DISPATCH
         ┌────────────┐
         │  Backend   │
         │ Calculates │
         │  Nearest   │
         └─────┬──────┘
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│ POLICE │ │HOSPITAL│ │AMBULANCE│
│  🚔    │ │  🏥    │ │  🚑    │
└────────┘ └────────┘ └────────┘

Alert 1: POLICE
┌────────────────────────────────────────────┐
│  📱 SMS to Delhi Traffic Police            │
│  ─────────────────────────────────────    │
│  🚨 CRITICAL ACCIDENT ALERT                │
│                                            │
│  Type: Road Accident                       │
│  Location: MG Road Junction                │
│  Coordinates: 28.6139, 77.2090             │
│  Time: 2026-06-18 10:30:15                │
│                                            │
│  Action Required:                          │
│  • Dispatch patrol immediately             │
│  • Secure accident site                    │
│  • Clear traffic for ambulance             │
│                                            │
│  ID: INC-ACC-1234                          │
└────────────────────────────────────────────┘

Alert 2: HOSPITAL
┌────────────────────────────────────────────┐
│  🏥 Alert to AIIMS Emergency               │
│  ─────────────────────────────────────    │
│  🚑 ACCIDENT - EMERGENCY RESPONSE          │
│                                            │
│  Location: MG Road Junction                │
│  Distance: 3.2 km from your location       │
│  ETA: 8 minutes                            │
│                                            │
│  IMMEDIATE ACTION REQUIRED:                │
│  • Prepare emergency room                  │
│  • Alert trauma team                       │
│  • Ready OR if needed                      │
│                                            │
│  Visual confirmation attached              │
│  ID: INC-ACC-1234                          │
└────────────────────────────────────────────┘

Alert 3: AMBULANCE
┌────────────────────────────────────────────┐
│  🚑 108 Ambulance Dispatch                 │
│  ─────────────────────────────────────    │
│  EMERGENCY DISPATCH REQUEST                │
│                                            │
│  Incident: Road Accident                   │
│  Location: MG Road Junction                │
│  Coordinates: 28.6139, 77.2090             │
│                                            │
│  Route: Optimized (7.2 km, 8 min)         │
│  Nearest Hospital: AIIMS Emergency         │
│                                            │
│  Navigate Now → [GPS Link]                 │
│  ID: INC-ACC-1234                          │
└────────────────────────────────────────────┘

🎯 TOTAL TIME: < 5 SECONDS
   Detection → Processing → Alerts Sent

🕐 TRADITIONAL METHOD: 5-15 MINUTES
   Witness → Call 112 → Explain → Wait → Dispatch

⏱️ TIME SAVED: 5-15 MINUTES
💪 LIVES SAVED: PRICELESS
```

---

## 🗺️ **Heatmap Generation**

```
Database Query:
┌────────────────────────────────────────────┐
│  SELECT location, COUNT(*) as violations  │
│  FROM incidents                            │
│  WHERE timestamp > last_7_days             │
│  GROUP BY location                         │
└────────┬───────────────────────────────────┘
         │
         ▼
Results:
┌────────────────────────────────────────────┐
│  Rajiv Chowk:    145 violations (CRITICAL) │
│  India Gate:      89 violations (HIGH)     │
│  Connaught Place: 67 violations (MEDIUM)   │
│  Red Fort:        34 violations (LOW)      │
└────────┬───────────────────────────────────┘
         │
         ▼
Frontend Map:
┌────────────────────────────────────────────┐
│  🗺️ Delhi City Map                        │
│  ─────────────────────────────────────    │
│                                            │
│        🔴 Rajiv Chowk (145)                │
│          ↑ HOTSPOT                         │
│                                            │
│    🟠 Connaught Place (67)                 │
│                                            │
│            🟡 Red Fort (34)                │
│                                            │
│  🟢 India Gate (89)                        │
│                                            │
│  Legend:                                   │
│  🔴 Critical (>100)  🟠 High (50-100)      │
│  🟡 Medium (20-50)   🟢 Low (<20)          │
└────────────────────────────────────────────┘
```

---

## 👮 **Repeat Offender Tracking**

```
License Plate Detected: DL3C1234
         │
         ▼
Database Lookup:
┌────────────────────────────────────────────┐
│  offenders collection                      │
│  ─────────────────────────────────────    │
│  {                                         │
│    "license_plate": "DL3C1234",            │
│    "total_violations": 52,                 │
│    "is_repeat_offender": true,             │
│    "violations": [                         │
│      {"type": "helmet", "date": "..."},    │
│      {"type": "redlight", "date": "..."},  │
│      ...                                   │
│    ]                                       │
│  }                                         │
└────────┬───────────────────────────────────┘
         │
         ▼
Frontend Display:
┌────────────────────────────────────────────┐
│  🚨 REPEAT OFFENDER ALERT                  │
│  ─────────────────────────────────────    │
│  Vehicle: DL3C1234                         │
│  Total Violations: 52                      │
│                                            │
│  Violation History:                        │
│  • Helmet: 23 times                        │
│  • Red Light: 15 times                     │
│  • Wrong Way: 8 times                      │
│  • Others: 6 times                         │
│                                            │
│  First Seen: May 1, 2026                   │
│  Last Seen: Today, 10:30 AM                │
│                                            │
│  Recommended Action:                       │
│  ⚡ High Priority Enforcement               │
│  💰 Cumulative Fine: ₹26,000               │
│  🚫 Consider License Suspension            │
│                                            │
│  [View Full History] [Generate Report]     │
└────────────────────────────────────────────┘
```

---

## 📊 **Dashboard Statistics Calculation**

```
Real-time Queries:
┌────────────────────────────────────────────┐
│  Query 1: Violations Today                 │
│  ─────────────────────────────────────    │
│  SELECT COUNT(*) FROM incidents            │
│  WHERE date(timestamp) = TODAY             │
│  Result: 1,284                             │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│  Query 2: Active Accidents                 │
│  ─────────────────────────────────────    │
│  SELECT COUNT(*) FROM incidents            │
│  WHERE type = 'accident'                   │
│  AND status IN ('new', 'alert_sent')       │
│  Result: 3                                 │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│  Query 3: Pending Alerts                   │
│  ─────────────────────────────────────    │
│  SELECT COUNT(*) FROM alerts               │
│  WHERE status = 'sent'                     │
│  AND type = 'police'                       │
│  Result: 18                                │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│  Query 4: City Safety Score                │
│  ─────────────────────────────────────    │
│  Algorithm:                                │
│  score = 100 - (critical×10 + high×5 +    │
│                  medium×2 + low×0.5) / 10  │
│  Result: 78/100 (Moderate Risk)            │
└────────────────────────────────────────────┘

Combined Dashboard:
┌────────────────────────────────────────────┐
│  📊 GuardianEye Dashboard                  │
│  ─────────────────────────────────────    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │Violations│ │ Accidents│ │  Alerts  │  │
│  │  1,284   │ │    3     │ │    47    │  │
│  │  +12% ↑  │ │ 2 CRIT ⚠️│ │  18 ⏳   │  │
│  └──────────┘ └──────────┘ └──────────┘  │
│                                            │
│  City Safety Score: 78/100 🟡              │
│  ████████░░ Moderate Risk                  │
│                                            │
│  📈 24h Trend:         🎯 Top Violations:  │
│  [Chart showing        • Helmet: 456       │
│   hourly violations]   • Red Light: 234    │
│                        • Wrong Way: 123    │
└────────────────────────────────────────────┘
```

---

## 🔐 **Security & Privacy Flow**

```
┌────────────────────────────────────────────┐
│  Image Capture                             │
│  ─────────────────────────────────────    │
│  • Raw image from camera                   │
│  • Contains faces, plates, etc.            │
└────────┬───────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│  AI Processing (Privacy Layer)             │
│  ─────────────────────────────────────    │
│  1. Detect violations                      │
│  2. Extract license plates                 │
│  3. ❌ Blur faces (privacy)                │
│  4. ❌ Remove metadata                     │
│  5. Create annotated image                 │
└────────┬───────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│  Storage (Secure)                          │
│  ─────────────────────────────────────    │
│  • Encrypted at rest                       │
│  • Access logged                           │
│  • Auto-delete after 90 days               │
│  • Only violation data kept                │
└────────┬───────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│  Access Control                            │
│  ─────────────────────────────────────    │
│  • Role-based access                       │
│  • Police: View violations only            │
│  • Admin: Full access                      │
│  • Hospital: Accident data only            │
│  • All access logged                       │
└────────────────────────────────────────────┘
```

---

## 🌐 **Future: City-Wide Deployment**

```
Current (Demo): Single Junction
┌────────────┐
│  1 Camera  │ → Backend → Dashboard
└────────────┘

Phase 1: Multiple Junctions (10 cameras)
┌────┐ ┌────┐ ┌────┐
│CAM1│ │CAM2│ │CAM3│ → Backend → Dashboard
└────┘ └────┘ └────┘
┌────┐ ┌────┐ ┌────┐
│CAM4│ │CAM5│ │CAM6│ → Backend → Dashboard
└────┘ └────┘ └────┘

Phase 2: City-Wide (100+ cameras)
┌─────────────────────────────────────────┐
│         Edge Computing Layer            │
│  ─────────────────────────────────────  │
│  IoT Device on each camera:             │
│  • Local AI processing                  │
│  • Reduced bandwidth                    │
│  • Faster response                      │
│  • Offline capability                   │
└───────┬─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│         Cloud Backend (AWS/Azure)       │
│  ─────────────────────────────────────  │
│  • Load balancer                        │
│  • Multiple API servers                 │
│  • Distributed database                 │
│  • Auto-scaling                         │
└───────┬─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│    Multiple Control Rooms               │
│  ─────────────────────────────────────  │
│  • Police HQ                            │
│  • Hospital ERs                         │
│  • Traffic Control Center               │
│  • Admin Dashboard                      │
└─────────────────────────────────────────┘
```

---

## 📱 **Mobile App Architecture (Future)**

```
┌────────────────────────────────────────────┐
│         Police Officer's Device            │
│  ─────────────────────────────────────    │
│  📱 Mobile App Features:                   │
│  • Real-time alerts                        │
│  • Navigate to incident                    │
│  • View evidence                           │
│  • Update status                           │
│  • Issue e-challan                         │
│  • Offline mode                            │
└────────┬───────────────────────────────────┘
         │
         │ 4G/5G
         ▼
┌────────────────────────────────────────────┐
│         Backend API                        │
│  ─────────────────────────────────────    │
│  • JWT Authentication                      │
│  • Real-time sync                          │
│  • Geolocation tracking                    │
│  • Push notifications                      │
└────────────────────────────────────────────┘
```

---

**Visual summary complete! Use these diagrams in your presentation. 🎨**
