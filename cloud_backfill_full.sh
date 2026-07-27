#!/bin/bash
PROJECT_ID="project-sentiment-etl"
REGION="asia-southeast1"
JOB_NAME="fin-etl-job"

# Generate dates from 2026-03-27 to 2026-06-01
START="2026-03-27"
END="2026-06-01"

# Build date array
DATES=()
d="$START"
while [[ "$d" < "$END" || "$d" == "$END" ]]; do
  DATES+=("$d")
  d=$(date -j -f "%Y-%m-%d" -v+1d "$d" "+%Y-%m-%d" 2>/dev/null || date -d "$d + 1 day" "+%Y-%m-%d")
done

echo "=== Cloud Backfill: ${START} → ${END} (${#DATES[@]} days) ==="

SUCCESS=0
FAIL=0

for d in "${DATES[@]}"; do
  echo ""
  echo "[$(date +'%H:%M:%S')] ▶ Running ETL for: $d"
  gcloud run jobs execute $JOB_NAME \
    --region=$REGION \
    --args="--date=$d" \
    --wait \
    --project=$PROJECT_ID
  if [ $? -eq 0 ]; then
    echo "✅ SUCCESS: $d"
    ((SUCCESS++))
  else
    echo "❌ FAILED:  $d"
    ((FAIL++))
  fi
  sleep 3
done

echo ""
echo "=== Backfill Complete! ==="
echo "✅ Success: $SUCCESS days"
echo "❌ Failed:  $FAIL days"
