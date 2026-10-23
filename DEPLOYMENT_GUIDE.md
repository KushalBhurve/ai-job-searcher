# 🚀 Google Cloud Run & Groq API Deployment Guide
## Deploying AI Job Radar to the Cloud ($0 – $1 / Month)

This guide walks you through deploying your **AI Job Radar** to **Google Cloud Run** using **Groq's Free Tier API** for LLM evaluations, and linking it to your custom domain hosted on **Hostinger**.

---

## 🏗️ Architecture & Monthly Cost Breakdown

| Component | Service | Tier / Plan | Monthly Cost |
| :--- | :--- | :--- | :--- |
| **Compute / Backend** | Google Cloud Run | Free Tier (2M requests, 360k GB-sec/mo) | **$0.00 / month** |
| **Container Build** | Google Cloud Build | Free Tier (120 build-mins/day free) | **$0.00 / month** |
| **LLM Inference** | Groq Cloud API | Free Tier (14,400 calls/day on Llama 3.3 70B) | **$0.00 / month** |
| **SSL / HTTPS** | Google-Managed SSL | Included free with Cloud Run | **$0.00 / month** |
| **Domain** | Your Hostinger Domain | Existing purchase | **$0.00 extra** |
| **Total Estimated Cost** | | | **$0.00 – $1.00 / month** |

---

## 📋 Prerequisites
1. A **Google Cloud Platform (GCP)** account ([console.cloud.google.com](https://console.cloud.google.com/)).
2. A free **Groq Cloud** account ([console.groq.com](https://console.groq.com/)).
3. A **GitHub** account with `git` installed on your machine.
4. Your **Hostinger** account where your domain DNS is managed.

---

## Step 1: Obtain a Free Groq Cloud API Key (30 Seconds)

1. Go to **[https://console.groq.com/](https://console.groq.com/)** and sign in.
2. In the left sidebar, click **API Keys**.
3. Click **Create API Key**.
4. Name the key (e.g., `ai-job-radar`) and copy the generated key (`gsk_...`).
5. Keep this key safe; you will paste it into Cloud Run as an environment variable.

> [!NOTE]
> Groq's free tier provides **14,400 requests/day** on `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` at ~300 tokens/sec. This eliminates the need for expensive cloud GPUs ($30–$60/mo).

---

## Step 2: Push Your Project to GitHub

Open PowerShell in your project directory (`c:\Users\kusha\OneDrive\Desktop\AI Job Searcher\V1`):

```powershell
# 1. Initialize git if not already initialized
git init

# 2. Stage all project files (Dockerfile and .dockerignore are already configured)
git add .

# 3. Commit the changes
git commit -m "feat: configure cloud run deployment with groq api"

# 4. Create a new repository on github.com (e.g. named 'ai-job-radar')
# 5. Link and push to your GitHub repo:
git remote add origin https://github.com/<your-username>/ai-job-radar.git
git branch -M main
git push -u origin main
```

---

## Step 3: Deploy to Google Cloud Run

### Method A: Automated GitHub Deployment via GCP Console (Recommended)

1. Open the **[Google Cloud Run Console](https://console.cloud.google.com/run)**.
2. Select or create your GCP project (e.g., `ai-job-radar`).
3. Click **Create Service** at the top.
4. Under **Deployment type**, choose **"Continuously deploy from a repository"**.
5. Click **Set up with Cloud Build**:
   - Provider: **GitHub**.
   - Authenticate and select your repository: `<your-username>/ai-job-radar`.
   - Branch: `^main$`.
   - Build Type: **Dockerfile** (Source location: `/Dockerfile`).
   - Click **Save**.
6. **Service Settings**:
   - **Service name**: `ai-job-radar`
   - **Region**: `asia-south1` (Mumbai) or `us-central1`.
   - **Authentication**: Select **"Allow unauthenticated invocations"** (allows web browser access).
7. **Scaling & Resources** (Expand *Container, Networking, Security*):
   - **Container port**: `8080` (or leave default `$PORT`).
   - **Memory**: `512 MiB` (or `1 GiB`).
   - **CPU**: `1 vCPU`.
   - **Minimum instances**: `0` *(Critical: allows service to scale to zero when idle for $0 cost)*.
   - **Maximum instances**: `1` (or `2`).
8. **Environment Variables**:
   Under the **Variables & Secrets** tab, click **Add Variable**:
   | Name | Value |
   | :--- | :--- |
   | `GROQ_API_KEY` | `gsk_your_actual_groq_key_here` |
   | `AI_PROVIDER` | `free_api` |
9. Click **Create**.
   - Google Cloud Build will automatically build your Docker container and deploy it.
   - Within 2–3 minutes, you will receive a live URL (e.g., `https://ai-job-radar-xxxxxx.a.run.app`).

---

### Method B: Deploy via Google Cloud Shell (No Local Tools Required)

If you prefer using the browser terminal without configuring GitHub:
1. Open **[Google Cloud Shell](https://shell.cloud.google.com/)**.
2. Clone your repo:
   ```bash
   git clone https://github.com/<your-username>/ai-job-radar.git
   cd ai-job-radar
   ```
3. Run the one-line deployment command:
   ```bash
   gcloud run deploy ai-job-radar \
     --source . \
     --region asia-south1 \
     --allow-unauthenticated \
     --memory 512Mi \
     --min-instances 0 \
     --max-instances 1 \
     --set-env-vars GROQ_API_KEY="gsk_your_key_here",AI_PROVIDER="free_api"
   ```

---

## Step 4: Connect Your Hostinger Domain

Connect your Hostinger domain (e.g., `jobs.yourdomain.com`) to Google Cloud Run:

### 1. In Google Cloud Run Console:
1. In Cloud Run, click **Manage Custom Domains** (or go to **Domain Mappings**).
2. Click **Add Mapping**.
3. Select service: `ai-job-radar`.
4. Domain: Select your domain or enter a subdomain (e.g. `jobs.yourdomain.com`).
5. Click **Continue**.
6. Google will provide DNS records to add to your registrar (typically a `CNAME` pointing to `ghs.googlehosted.com`).

### 2. In Hostinger Control Panel:
1. Log in to **[Hostinger](https://hpanel.hostinger.com/)** → **Domains** → select your domain.
2. Click **DNS / Nameservers** in the left sidebar.
3. Under **Manage DNS records**, create a new record:
   - **Type**: `CNAME`
   - **Name**: `jobs` (or your chosen subdomain prefix)
   - **Target / Value**: `ghs.googlehosted.com`
   - **TTL**: `300` (or default `14400`)
4. Click **Add Record**.

> [!TIP]
> Google Cloud automatically issues and provisions a **free Google-Managed SSL/TLS certificate (HTTPS)**. DNS propagation and certificate verification usually take between 15 to 30 minutes.

---

## Step 5: SQLite Database Persistence in Cloud Run

Cloud Run instances are stateless (ephemeral containers). When an instance scales to 0 and restarts, any newly created files in the container are reset unless stored persistently.

You have two simple options to handle database state:

### Option 1: On-Demand Refresh (Simplest / Default)
- Because scraping takes only 15–20 seconds, you can simply click **"🔄 Refresh 24H Jobs"** whenever you visit the dashboard.
- The pre-seeded `jobs.db` committed in your repository is packaged directly into the container image, so your existing jobs are always available on startup.

### Option 2: Cloud Storage FUSE Volume Mount (Persistent Storage)
If you want newly scraped jobs to persist permanently across container restarts:
1. In GCP Console, create a free Cloud Storage bucket (e.g., `kushal-jobs-db`).
2. In Cloud Run service edit settings → **Volumes**:
   - Add Volume: Type **Cloud Storage bucket** → select `kushal-jobs-db`.
   - Mount path: `/data`.
3. In Cloud Run **Environment variables**:
   - Add variable: `DB_PATH = /data/jobs.db`.
- Cloud Run natively mounts the GCS bucket as a local disk, keeping `jobs.db` permanently saved for free.

---

## Step 6: Testing & Production Checklist

1. Open your custom URL: `https://jobs.yourdomain.com`.
2. Confirm the 475 existing jobs load with scores.
3. Click **"🤖 Batch Analyze All (AI)"** to verify that Groq processes remaining unassessed jobs in batches of 10.
4. Click **"🔄 Refresh 24H Jobs"** to verify that multi-portal scraping runs cleanly in the cloud.
