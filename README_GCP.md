# GCP Deployment Instructions

These files are prepared to help you deploy the **Fin Sentiment** project to Google Cloud Platform.

## 1. Files Prepared
- `Dockerfile.web`: For the Web Dashboard
- `Dockerfile.etl`: For the daily data ingestion
- `docker-compose.gcp.yml`: A template for running containers with external DB connections

## 2. Deployment Steps

### Step A: Database (Cloud SQL)
1. Create a **Cloud SQL (PostgreSQL)** instance on GCP.
2. In your `.env.gcp` (copy from `.env`), change `POSTGRES_HOST` to the IP of your Cloud SQL instance.

### Step B: Build & Push Images
Install the [Google Cloud SDK](https://cloud.google.com/sdk) and run:
```bash
# 1. Authenticate
gcloud auth login
gcloud auth configure-docker

# 2. Build and tag (Replace YOUR_PROJECT_ID)
docker build -t gcr.io/YOUR_PROJECT_ID/fin-web -f Dockerfile.web .
docker build -t gcr.io/YOUR_PROJECT_ID/fin-etl -f Dockerfile.etl .

# 3. Push to Registry
docker push gcr.io/YOUR_PROJECT_ID/fin-web
docker push gcr.io/YOUR_PROJECT_ID/fin-etl
```

### Step C: Deploy Web Dashboard (Cloud Run)
1. Go to **Cloud Run** in the GCP Console.
2. Create a new service using the `fin-web` image.
3. Set **Container Port** to `8000`.
4. Connect to Cloud SQL via the **Connections** tab.

### Step D: Setup ETL Job (Cloud Run Jobs)
1. Go to **Cloud Run** -> **Jobs**.
2. Create a Job using the `fin-etl` image.
3. Set a **Schedule** (e.g., `0 8 * * *` for 8:00 AM daily).

---

## Tips for Cost Saving
- **Database**: Use the smallest instance (Shared core, 1 vCPU, 0.6 GB RAM).
- **Cloud Run**: Use the "CPU only allocated during request processing" setting to stay in the Free Tier.
