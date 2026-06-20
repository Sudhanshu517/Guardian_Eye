#!/bin/bash

# Create Demo Data for GuardianEye
# Populates the system with test incidents for demo

echo "🎬 Creating Demo Data for GuardianEye"
echo "======================================"
echo ""

BACKEND_URL="http://localhost:8000"

# Check if backend is running
if ! curl -s "$BACKEND_URL/health" > /dev/null; then
    echo "❌ Backend is not running!"
    echo "   Start it with: cd backend && uvicorn app.main:app --reload"
    exit 1
fi

echo "✅ Backend is running"
echo ""

# Violation types
violations=(
    "red_light:Red Light Jump:high"
    "no_helmet:No Helmet:medium"
    "overspeeding:Overspeeding:high"
    "wrong_way:Wrong Way Driving:critical"
    "no_seatbelt:No Seatbelt:medium"
    "triple_riding:Triple Riding:medium"
    "accident:Accident:critical"
    "illegal_parking:Illegal Parking:low"
    "stopline:Stop Line Violation:medium"
)

# Camera IDs
cameras=("CAM-001" "CAM-002" "CAM-003" "CAM-004" "CAM-005")

echo "📊 Creating 15 test incidents..."
echo ""

count=0
for i in {1..15}; do
    # Pick random violation and camera
    violation_data=${violations[$RANDOM % ${#violations[@]}]}
    camera=${cameras[$RANDOM % ${#cameras[@]}]}
    
    # Parse violation data
    IFS=':' read -r vtype vname severity <<< "$violation_data"
    
    # Create incident
    response=$(curl -s -X POST "$BACKEND_URL/api/process/simulate" \
        -F "camera_id=$camera" \
        -F "violation_type=$vtype")
    
    if echo "$response" | grep -q "success"; then
        incident_id=$(echo "$response" | grep -o '"incident_id":"[^"]*"' | cut -d'"' -f4)
        count=$((count + 1))
        echo "  ✅ Created: $vname [$severity] - $incident_id"
    else
        echo "  ⚠️  Failed to create incident"
    fi
    
    sleep 0.3
done

echo ""
echo "======================================"
echo "✅ Created $count test incidents"
echo ""
echo "📱 View them in the frontend:"
echo "   Dashboard:  http://localhost:5173"
echo "   Violations: http://localhost:5173/violations"
echo "   Alerts:     http://localhost:5173/alerts"
echo ""
echo "🎬 Ready for demo!"
