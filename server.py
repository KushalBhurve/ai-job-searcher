import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import db
from engine import engine
from config import load_config
from matcher import evaluate_single_job
from notifier import notify_job_match
from models import JobPost, MatchAnalysis

app = FastAPI(title="AI Job Searcher API", version="2.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

@app.on_event("startup")
def on_startup():
    db.init_db()

@app.get("/api/jobs")
def get_jobs_api(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    search: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    remote_only: bool = Query(False),
    platform: Optional[str] = Query(None),
    sort_by: str = Query("score")
):
    """Paginated jobs API for infinite scrolling and dynamic filtering."""
    result = db.get_jobs(
        page=page,
        limit=limit,
        search=search,
        min_score=min_score,
        remote_only=remote_only,
        platform=platform,
        sort_by=sort_by
    )
    return result

@app.get("/api/stats")
def get_stats_api():
    """Aggregate statistics for match scores, platforms, and totals."""
    return db.get_stats()

@app.get("/api/status")
def get_status_api():
    """Real-time progress of background scraper and LLM evaluator."""
    return engine.get_status()

@app.post("/api/refresh")
def trigger_refresh_api(limit_eval: int = Query(30), continuous: bool = Query(True)):
    """Triggers background scraping and progressive Ollama matching."""
    started = engine.start_refresh_async(limit_evaluations=limit_eval, continuous_batch=continuous)
    if started:
        return {"success": True, "message": "Scrape and AI evaluation started in background"}
    else:
        return {"success": False, "message": "Scraper or evaluator is already running"}

@app.post("/api/analyze-all")
def trigger_batch_analysis_api(batch_size: int = Query(10, ge=1, le=50)):
    """Triggers background batch LLM evaluation on all remaining unassessed jobs."""
    started = engine.start_batch_evaluator_async(batch_size=batch_size)
    if started:
        return {"success": True, "message": "Batch AI evaluation started in background"}
    else:
        return {"success": False, "message": "Scraper or evaluator is already in progress"}

@app.post("/api/stop")
def stop_engine_api():
    """Pauses or stops current background scraping or batch evaluation."""
    stopped = engine.stop()
    return {"success": stopped, "message": "Stop signal sent to background task" if stopped else "No background task running"}

@app.post("/api/reset")
def reset_database_api(clear_files: bool = Query(False)):
    """Wipes the SQLite database and optionally clears exported results files."""
    db.clear_db()
    if clear_files:
        results_dir = Path(__file__).parent / "results"
        if results_dir.exists():
            for f in results_dir.glob("jobs_*.*"):
                try:
                    f.unlink()
                except Exception:
                    pass
    return {"success": True, "message": "Database and records reset successfully"}

@app.post("/api/jobs/{job_id}/analyze")
def analyze_single_job_api(job_id: str, force_notify: bool = Query(False)):
    """Deep analyze an individual job on demand and notify if match score >= 60%."""
    cfg = load_config()
    job = db.get_job_by_id(job_id)
    if not job:
        return JSONResponse({"success": False, "message": "Job not found in database"}, status_code=404)

    try:
        analysis = evaluate_single_job(job, cfg.candidate_profile, cfg.ai_matcher)
        job.match_analysis = analysis
        db.update_job_analysis(job.id, analysis)

        notification_sent = False
        channels_sent = {}
        threshold = cfg.notifications.min_score

        if (cfg.notifications.enabled and analysis.match_score >= threshold) or force_notify:
            channels_sent = notify_job_match(job, analysis, cfg.notifications, force=force_notify)
            notification_sent = any(channels_sent.values())

        return {
            "success": True,
            "job_id": job.id,
            "match_score": analysis.match_score,
            "decision": analysis.decision,
            "summary_reason": analysis.summary_reason,
            "matching_skills": analysis.key_matching_skills,
            "missing_skills": analysis.missing_skills_or_gaps,
            "recommended_action": analysis.recommended_action,
            "notification_sent": notification_sent,
            "channels": channels_sent
        }
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@app.post("/api/notifications/test")
def test_notification_api(channel: str = Query("all")):
    """Send a sample notification to verify WhatsApp and/or Email setup."""
    cfg = load_config()
    test_job = JobPost(
        id="test-notification-sample",
        title="AI Engineer (GenAI / Python)",
        company="Antigravity AI Labs",
        location="Bengaluru / Remote",
        site="linkedin",
        job_url="https://www.linkedin.com/jobs/view/sample",
        date_posted="Just now",
        is_remote=True,
        salary="₹18 - ₹24 LPA",
        description="We are seeking an AI Engineer with 1-2 years experience in Python, LangGraph, RAG pipelines, FastAPI, and Vertex AI/GCP. You will develop multimodal agents and automated pipelines."
    )
    test_analysis = MatchAnalysis(
        match_score=88,
        decision="STRONG_MATCH",
        key_matching_skills=["Python", "LangGraph", "RAG", "FastAPI", "Vertex AI"],
        missing_skills_or_gaps=["Kafka"],
        summary_reason="Excellent alignment with Kushal's GenAI background, LangGraph and GCP experience.",
        recommended_action="High priority recommendation. Apply immediately."
    )

    test_cfg = cfg.notifications.model_copy(deep=True)
    test_cfg.enabled = True
    if channel == "whatsapp":
        test_cfg.channels.whatsapp.enabled = True
        test_cfg.channels.email.enabled = False
    elif channel == "email":
        test_cfg.channels.email.enabled = True
        test_cfg.channels.whatsapp.enabled = False

    res = notify_job_match(test_job, test_analysis, test_cfg, force=True)
    sent = any(res.values())
    return {
        "success": sent,
        "channels": res,
        "message": "Test notification sent! Check your WhatsApp or Email inbox." if sent else "Failed to send. Please check your credentials in profile.yaml or .env"
    }

@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse({"status": "Frontend loading", "message": "index.html not created yet"})
    return FileResponse(index_file)

# Mount remaining static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
