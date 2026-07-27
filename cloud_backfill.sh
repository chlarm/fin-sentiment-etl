#!/bin/bash
PROJECT_ID="project-sentiment-etl"
REGION="asia-southeast1"
JOB_NAME="fin-etl-job"

DATES=("2026-03-27" "2026-03-28" "2026-03-29" "2026-03-30" "2026-03-31" "2026-04-01" "2026-04-02" "2026-04-03" "2026-04-04" "2026-04-05" "2026-04-06" "2026-04-07" "2026-04-08" "2026-04-09")

echo "Starting Cloud Backfill for ${#DATES[@]} days..."

for d in "${DATES[@]}"; do
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] Executing cloud job for date: $d"
  gcloud run jobs execute $JOB_NAME --region=$REGION --args="--date=$d" --wait
  if [ $? -eq 0 ]; then
    echo "✅ Success for $d"
  else
    echo "❌ Failed for $d"
  fi
  sleep 5
done

echo "Cloud Backfill complete!"
