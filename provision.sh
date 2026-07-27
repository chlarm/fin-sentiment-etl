#!/bin/bash
set -e

PROJECT_ID="project-sentiment-etl"
REGION="asia-southeast1"

export PATH="/opt/homebrew/bin:$PATH"

echo "Enabling APIs..."
gcloud services enable sqladmin.googleapis.com run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com sql-component.googleapis.com

echo "Creating Artifact Registry..."
gcloud artifacts repositories create fin-repo --repository-format=docker --location=$REGION --description="Docker repository for FIN ETL project" || true

echo "Configuring Docker for Artifact Registry..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

echo "Creating Cloud SQL Instance..."
# This can take 5-10 minutes
gcloud sql instances create fin-sentiment-db --database-version=POSTGRES_16 --tier=db-f1-micro --region=$REGION --project=$PROJECT_ID || true

echo "Setting password for postgres user..."
gcloud sql users set-password postgres --instance=fin-sentiment-db --password=fin || true

echo "Creating fin_dw database..."
gcloud sql databases create fin_dw --instance=fin-sentiment-db || true

echo "Building Web Dashboard Image..."
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/fin-repo/fin-web \
  -f Dockerfile.web .

echo "Building ETL Job Image..."
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/fin-repo/fin-etl \
  -f Dockerfile.etl .

echo "Pushing Web Dashboard Image..."
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/fin-repo/fin-web

echo "Pushing ETL Job Image..."
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/fin-repo/fin-etl

echo "=== All provisioning and building finished successfully! ==="
