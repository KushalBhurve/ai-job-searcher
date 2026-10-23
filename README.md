# ⚡ AI Job Searcher (Last 24 Hours)

An intelligent, zero-cost job searcher and aggregator that scrapes the internet for job postings published within the last 24 hours, matches each job description against your candidate profile using a local LLM (**Ollama**), and delivers an interactive dashboard and exportable reports.

Built with **Python**, **python-jobspy**, **Ollama (`llama3.2`)**, and **Vanilla Glassmorphic HTML/CSS**.

---

## 🌟 Key Features

- **Multi-Portal Scraping (0 API Keys / 100% Free)**:
  - Scrapes **LinkedIn**, **Indeed**, **Glassdoor**, and **ZipRecruiter**.
  - Strict 24-hour filter (`hours_old: 24`) so you only see the freshest listings.
  - Automatic deduplication across portals.
- **AI-Powered Profile Matcher**:
  - Uses local **Ollama** (`llama3.2` or any model) or free cloud APIs (Groq, Gemini).
  - Scores jobs from `0` to `100%`.
  - Flags matching skills vs missing requirements and provides a 2-sentence rationale for why you should apply.
- **Multiple Output Formats**:
  - **Interactive HTML Dashboard**: Filter by match score, remote-only, or search by role/company with 1-click apply buttons.
  - **CSV Spreadsheet**: Perfect for importing into Notion, Excel, or Google Sheets to track your application pipeline.
  - **JSON Data**: Structured format for integrations and automations.
  - **Rich Terminal Table**: Instant color-coded CLI summary.
- **Notification-Ready (For Future Hosting)**:
  - **WhatsApp**: Free WhatsApp alerts via CallMeBot.
  - **Email**: Automated HTML digest sent to your inbox via Gmail / SMTP.
  - **Telegram**: Instant mobile push notification via Telegram Bot.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- [Ollama](https://ollama.com/) installed with `llama3.2` (or your preferred model):
  ```bash
  ollama pull llama3.2
  ```

### 2. Setup Virtual Environment & Dependencies
```bash
python -m venv venv
.\venv\Scripts\activate  # On Windows (or source venv/bin/activate on Linux/Mac)
pip install -r requirements.txt
```

### 3. Customize Your Profile
Open `profile.yaml` and edit:
- `search.keywords`: Job titles to search (e.g., `["Software Engineer", "Backend Developer"]`)
- `search.locations`: Preferred locations or `["Remote"]`
- `candidate_profile`: Your skills, years of experience, preferences, and bio summary.
- `ai_matcher.min_match_score`: Minimum threshold to flag as recommended (default: `65`).

### 4. Running the Pipeline & Web Dashboard

You have two ways to run the job search and evaluation pipeline:

#### Option A: Live Interactive Web App (Recommended)
```bash
# Starts the FastAPI server and opens http://127.0.0.1:8000
python main.py serve

# Or run on a custom port:
python main.py serve --port 8080
```

Once the web dashboard opens in your browser:
1. **🔄 Refresh 24H Jobs**:
   - Scrapes **LinkedIn**, **Indeed**, and **Glassdoor** for postings from the last 24 hours.
   - Instantly upserts all jobs into SQLite (`jobs.db`).
   - Evaluates the top candidate-relevant jobs first and **automatically continues in the background in batches of 10** until all jobs are analyzed.
2. **🤖 Batch Analyze All (AI)**:
   - Evaluates all unassessed jobs already in your database using local Ollama (`llama3.2`) in batches of 10.
   - Prioritizes high-value roles (`GenAI`, `AI Engineer`, `Python`, `SDE`) first so you see strong matches right away.
   - Non-blocking: You can search, filter, and apply to jobs while analysis runs in the background.
3. **⏸️ Pause Analysis**:
   - Click the pause button in the live status banner at any time to pause background AI analysis.
4. **🗑️ Reset Database & 1-Click Re-run**:
   - Click **Reset Database** to wipe stored jobs and clear statistics.
   - Once reset, a large **`[ 🚀 Run 24H Scraper & AI Matcher ]`** button appears in the center of the screen to re-run the pipeline with a single click.

---

#### Option B: Standalone Terminal CLI Pipeline
```bash
# Standard run: Scrapes 24H jobs, evaluates top 30 with Ollama, saves to jobs.db & exports CSV/HTML
python main.py run

# Evaluate all scraped non-senior jobs with AI (comprehensive run):
python main.py run --all

# Limit AI evaluations to top N most relevant postings:
python main.py run --limit 15

# Run headlessly without auto-opening the browser:
python main.py run --no-browser
```

---

### 5. Utility & Testing Commands
```bash
# Test local Ollama connection and scoring prompt on a dummy role:
python main.py test-ai

# Test scraper connectivity with a fast 2-job probe:
python main.py test-scrape

# View the latest generated static HTML report in your browser:
python main.py view

# Reset SQLite database directly from terminal:
python main.py reset
```

---

### 6. Troubleshooting & FAQs

- **Port Conflict (`[Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)`):**
  - This occurs if another process (or a previous server run) is already using port `8000`.
  - Fix: Specify a different port using `python main.py serve --port 8080` or close the existing process.
- **Frontend shows "0 jobs" or statistics don't load:**
  - Verify your server is running (`python main.py serve`).
  - Refresh the page at `http://127.0.0.1:8000`.
- **How does batch AI evaluation work?**
  - Scraping pulls 200–500 fresh listings in seconds. Ollama evaluates jobs individually to calculate match percentages, skills gaps, and application advice.
  - The server processes these in batches of 10 in the background without freezing your machine or locking the database. Real-time progress is visible in the **"AI Evaluated"** stats card (e.g. `45 / 475`).

---

## 📁 Project Structure

```
AI Job Searcher/V1/
├── server.py          # FastAPI backend (pagination API & background refresh)
├── db.py              # SQLite database storage (jobs.db) & indexing
├── engine.py          # Async background scrape & Ollama evaluator coordinator
├── static/
│   └── index.html     # Dynamic infinite-scroll frontend with real-time refresh
├── config.py          # Configuration parser & Pydantic models
├── profile.yaml       # Candidate profile (Kushal B R), keywords, & filters
├── scraper.py         # Multi-platform job scraper using python-jobspy
├── matcher.py         # Ollama LLM prompt & evaluation engine
├── reporter.py        # Terminal visualizer, JSON/CSV exporter, & static HTML
├── notifier.py        # WhatsApp, Email, & Telegram dispatcher
├── main.py            # Unified CLI entrypoint (serve, run, test-ai, test-scrape)
├── requirements.txt   # Python dependencies
└── results/           # Generated dashboards, CSVs, and JSON files
    ├── latest_jobs.html
    ├── latest_jobs.csv
    └── latest_jobs.json
```

---

## 📬 Automated Hosting & Notifications (WhatsApp / Email)

When you're ready to host this on a server, VPS, or run it daily on your PC:

### Option A: Windows Task Scheduler (Run daily on your machine)
1. Open Windows Task Scheduler.
2. Create a basic task triggered daily at 9:00 AM.
3. Action: Start a program:
   - Program: `C:\Users\<user>\OneDrive\Desktop\AI Job Searcher\V1\venv\Scripts\python.exe`
   - Arguments: `main.py run --no-browser`
   - Start in: `C:\Users\<user>\OneDrive\Desktop\AI Job Searcher\V1`

### Option B: Free WhatsApp Alerts via CallMeBot
1. Follow the 1-minute instructions at [CallMeBot WhatsApp](https://www.callmebot.com/blog/free-api-whatsapp-messages/) to get your free API key.
2. In `profile.yaml`:
   ```yaml
   notifications:
     enabled: true
     channels:
       whatsapp:
         enabled: true
         phone_number: "+919876543210"
         api_key: "YOUR_CALLMEBOT_APIKEY"
   ```

### Option C: Email Alerts (Gmail)
1. Generate a Google App Password in your Google Account security settings.
2. In `profile.yaml`:
   ```yaml
   notifications:
     enabled: true
     channels:
       email:
         enabled: true
         sender_email: "your-email@gmail.com"
         sender_password: "xxxx xxxx xxxx xxxx"
         recipient_email: "your-email@gmail.com"
   ```

---

## 🚀 Cloud Deployment (Google Cloud Run + Groq + Hostinger)

For complete zero-cost ($0 – $1/month) deployment instructions on **Google Cloud Run** using your **Hostinger domain** and **Groq Free API**, see:
👉 [**DEPLOYMENT_GUIDE.md**](file:///c:/Users/kusha/OneDrive/Desktop/AI%20Job%20Searcher/V1/DEPLOYMENT_GUIDE.md)
